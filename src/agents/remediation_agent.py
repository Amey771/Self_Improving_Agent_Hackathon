from __future__ import annotations

import ast
import difflib
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.models import Incident


class RemediationAgent:
    """
    Remediation workflow helper:
    - generate concrete patch preview from top fix proposal
    - validate patch syntax
    - apply patch with backup
    - rollback patch
    - run repo validation command
    """

    def __init__(self, repo_root: str = "."):
        self.repo_root = Path(repo_root).resolve()
        self.patch_dir = self.repo_root / "data" / "runs" / "patches"
        self.backup_dir = self.repo_root / "data" / "runs" / "backups"
        self.patch_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def generate_patch_preview(self, incident: Incident, proposal_index: int = 0) -> dict[str, Any]:
        if not incident.fix_proposals:
            return {
                "status": "no_fix_proposals",
                "notes": "No fix proposals available for this incident.",
                "validation_passed": False,
                "applied": False,
            }

        idx = max(0, min(proposal_index, len(incident.fix_proposals) - 1))
        proposal = incident.fix_proposals[idx]
        target_rel = proposal.file_path
        target_path = self._resolve_target_file(target_rel)

        if not target_path:
            return {
                "status": "unavailable",
                "notes": f"Target file '{target_rel}' is not available in repository.",
                "incident_id": incident.id,
                "proposal_index": idx,
                "proposal_title": proposal.title,
                "strategy": proposal.strategy,
                "target_file": target_rel,
                "target_line": proposal.line,
                "diff": "",
                "validation_passed": False,
                "applied": False,
            }

        original_content = target_path.read_text(encoding="utf-8")
        original_lines = original_content.splitlines(keepends=True)
        if not original_lines:
            original_lines = ["\n"]

        line_idx = self._resolve_line_index(original_lines, proposal.line)
        original_line = original_lines[line_idx]
        patched_block = self._build_patch_block(proposal.strategy, original_line)
        patched_lines = original_lines[:line_idx] + patched_block + original_lines[line_idx + 1 :]
        patched_content = "".join(patched_lines)

        diff_text = "".join(
            difflib.unified_diff(
                original_lines,
                patched_lines,
                fromfile=f"a/{target_rel}",
                tofile=f"b/{target_rel}",
                lineterm="",
            )
        )
        if not diff_text.strip():
            diff_text = "No diff generated."

        patch_file = self.patch_dir / f"{incident.id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.diff"
        patch_file.write_text(diff_text, encoding="utf-8")

        return {
            "status": "generated",
            "notes": "Patch preview generated.",
            "incident_id": incident.id,
            "proposal_index": idx,
            "proposal_title": proposal.title,
            "strategy": proposal.strategy,
            "target_file": target_rel,
            "target_line": line_idx + 1,
            "diff": diff_text,
            "patch_file": self._rel_or_abs(patch_file),
            "validation_passed": False,
            "applied": False,
            "backup_path": None,
            "_original_content": original_content,
            "_patched_content": patched_content,
        }

    def validate_patch_syntax(self, remediation_state: dict[str, Any]) -> dict[str, Any]:
        patched_content = remediation_state.get("_patched_content")
        target_file = remediation_state.get("target_file")
        syntax_ok = True
        message = "Syntax validation skipped."

        if not patched_content or not target_file:
            syntax_ok = False
            message = "No generated patch content found for validation."
        elif str(target_file).endswith(".py"):
            try:
                ast.parse(str(patched_content))
                message = "Python syntax is valid for generated patch."
            except SyntaxError as exc:
                syntax_ok = False
                message = f"SyntaxError: {exc}"
        else:
            message = "Non-Python file: syntax validation skipped."

        remediation_state["validation"] = {
            "type": "syntax",
            "ok": syntax_ok,
            "message": message,
        }
        remediation_state["validation_passed"] = bool(syntax_ok)
        remediation_state["status"] = "validated" if syntax_ok else "validation_failed"
        return remediation_state

    def apply_patch(self, remediation_state: dict[str, Any]) -> dict[str, Any]:
        target_rel = remediation_state.get("target_file")
        patched_content = remediation_state.get("_patched_content")
        if not target_rel or patched_content is None:
            remediation_state["status"] = "apply_failed"
            remediation_state["apply_result"] = {"ok": False, "message": "No patch available to apply."}
            return remediation_state

        target_path = self._resolve_target_file(target_rel)
        if not target_path:
            remediation_state["status"] = "apply_failed"
            remediation_state["apply_result"] = {"ok": False, "message": f"Target file '{target_rel}' not found."}
            return remediation_state

        current_content = target_path.read_text(encoding="utf-8")
        backup_path = self.backup_dir / f"{Path(target_rel).name}.{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.bak"
        backup_path.write_text(current_content, encoding="utf-8")
        target_path.write_text(str(patched_content), encoding="utf-8")

        remediation_state["status"] = "applied"
        remediation_state["applied"] = True
        remediation_state["backup_path"] = self._rel_or_abs(backup_path)
        remediation_state["apply_result"] = {
            "ok": True,
            "message": "Patch applied.",
            "target_file": target_rel,
        }
        return remediation_state

    def rollback_patch(self, remediation_state: dict[str, Any]) -> dict[str, Any]:
        target_rel = remediation_state.get("target_file")
        backup_rel = remediation_state.get("backup_path")
        if not target_rel or not backup_rel:
            remediation_state["status"] = "rollback_failed"
            remediation_state["rollback_result"] = {"ok": False, "message": "No backup available for rollback."}
            return remediation_state

        target_path = self._resolve_target_file(target_rel)
        backup_path = self._resolve_rel_path(str(backup_rel))
        if not target_path or not backup_path or not backup_path.exists():
            remediation_state["status"] = "rollback_failed"
            remediation_state["rollback_result"] = {"ok": False, "message": "Backup path is invalid or missing."}
            return remediation_state

        restored_content = backup_path.read_text(encoding="utf-8")
        target_path.write_text(restored_content, encoding="utf-8")
        remediation_state["status"] = "rolled_back"
        remediation_state["applied"] = False
        remediation_state["rollback_result"] = {
            "ok": True,
            "message": "Rollback completed.",
            "target_file": target_rel,
        }
        return remediation_state

    def run_repo_validation(self, command: str | None = None) -> dict[str, Any]:
        """
        Strong default validation pipeline:
        1) compileall for app/src
        2) pytest -q when pytest is available and tests directory exists
        3) optional user command (safely tokenized, no shell operators)
        """
        steps: list[dict[str, Any]] = []

        compile_cmd = [sys.executable, "-m", "compileall", "app", "src"]
        steps.append(self._run_validation_step(compile_cmd))

        tests_dir = self.repo_root / "tests"
        pytest_available = shutil.which("pytest") is not None
        if tests_dir.exists() and pytest_available:
            steps.append(self._run_validation_step([sys.executable, "-m", "pytest", "-q"]))

        parsed_custom = self._parse_safe_command(command)
        if parsed_custom:
            steps.append(self._run_validation_step(parsed_custom))

        ok = all(step.get("ok", False) for step in steps) if steps else False
        failing_step = next((step for step in steps if not step.get("ok", False)), None)

        return {
            "command": "validation_pipeline",
            "ok": ok,
            "returncode": 0 if ok else int((failing_step or {}).get("returncode", -1)),
            "stdout_tail": self._tail("\n\n".join([step.get("stdout_tail", "") for step in steps if step.get("stdout_tail")])),
            "stderr_tail": self._tail("\n\n".join([step.get("stderr_tail", "") for step in steps if step.get("stderr_tail")])),
            "steps": steps,
        }

    def _resolve_target_file(self, file_path: str | None) -> Path | None:
        if not file_path or file_path == "unknown":
            return None
        candidate = self._resolve_rel_path(file_path)
        if not candidate or not candidate.exists() or not candidate.is_file():
            return None
        return candidate

    def _resolve_rel_path(self, rel_path: str) -> Path | None:
        candidate = (self.repo_root / rel_path).resolve()
        try:
            candidate.relative_to(self.repo_root)
        except ValueError:
            return None
        return candidate

    def _resolve_line_index(self, lines: list[str], line: int | None) -> int:
        if line is None:
            return 0
        return max(0, min(line - 1, len(lines) - 1))

    def _build_patch_block(self, strategy: str, original_line: str) -> list[str]:
        line_ending = "\r\n" if original_line.endswith("\r\n") else "\n"
        stripped = original_line.strip()
        indent_match = re.match(r"^\s*", original_line)
        indent = indent_match.group(0) if indent_match else ""
        if not stripped:
            stripped = "pass"

        if strategy == "guard_division_by_zero":
            return [
                f"{indent}try:{line_ending}",
                f"{indent}    {stripped}{line_ending}",
                f"{indent}except ZeroDivisionError:{line_ending}",
                f"{indent}    raise ValueError('division by zero prevented by VoiceOps remediation'){line_ending}",
            ]

        if strategy == "retry_timeout":
            return [
                f"{indent}for _voiceops_attempt in range(3):{line_ending}",
                f"{indent}    try:{line_ending}",
                f"{indent}        {stripped}{line_ending}",
                f"{indent}        break{line_ending}",
                f"{indent}    except TimeoutError:{line_ending}",
                f"{indent}        if _voiceops_attempt == 2:{line_ending}",
                f"{indent}            raise{line_ending}",
            ]

        if strategy == "safe_dict_access":
            replaced = re.sub(r"(\w+)\[['\"]([^'\"]+)['\"]\]", r"\1.get('\2')", stripped, count=1)
            if replaced != stripped:
                return [f"{indent}{replaced}{line_ending}"]

        if strategy == "input_validation":
            return [
                f"{indent}if any(v is None for v in locals().values()):{line_ending}",
                f"{indent}    raise ValueError('input validation failed by VoiceOps remediation'){line_ending}",
                f"{indent}{stripped}{line_ending}",
            ]

        return [
            f"{indent}try:{line_ending}",
            f"{indent}    {stripped}{line_ending}",
            f"{indent}except Exception as exc:{line_ending}",
            f"{indent}    raise RuntimeError('VoiceOps defensive boundary triggered') from exc{line_ending}",
        ]

    def _tail(self, text: str, max_chars: int = 2000) -> str:
        if not text:
            return ""
        if len(text) <= max_chars:
            return text
        return text[-max_chars:]

    def _rel_or_abs(self, path: Path) -> str:
        try:
            return path.relative_to(self.repo_root).as_posix()
        except ValueError:
            return path.as_posix()

    def _parse_safe_command(self, command: str | None) -> list[str] | None:
        if not command:
            return None
        cleaned = command.strip()
        if not cleaned:
            return None
        if re.search(r"[|&;><`$]", cleaned):
            return None
        try:
            parsed = shlex.split(cleaned, posix=False)
            return parsed if parsed else None
        except ValueError:
            return None

    def _run_validation_step(self, cmd: list[str]) -> dict[str, Any]:
        cmd_display = " ".join(cmd)
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                shell=False,
                capture_output=True,
                text=True,
                timeout=180,
            )
            return {
                "command": cmd_display,
                "ok": result.returncode == 0,
                "returncode": result.returncode,
                "stdout_tail": self._tail(result.stdout),
                "stderr_tail": self._tail(result.stderr),
            }
        except subprocess.TimeoutExpired:
            return {
                "command": cmd_display,
                "ok": False,
                "returncode": -1,
                "stdout_tail": "",
                "stderr_tail": "Validation step timed out after 180 seconds.",
            }
