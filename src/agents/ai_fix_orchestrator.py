from __future__ import annotations

import difflib
import json
import re
from pathlib import Path
from typing import Any, TypedDict

from src.agents.remediation_agent import RemediationAgent
from src.config import Settings
from src.core.models import Incident

try:  # Optional LangChain integration
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover - optional dependency
    ChatOpenAI = None

try:  # Optional LangGraph integration
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover - optional dependency
    END = None
    StateGraph = None


class AIFixState(TypedDict, total=False):
    incident: Incident
    repo_root: str
    max_attempts: int
    validation_command: str
    attempt: int
    diagnosis: str
    candidate_files: list[str]
    selected_file: str
    selected_line: int | None
    patch_text: str
    remediation_state: dict[str, Any]
    repo_validation: dict[str, Any]
    success: bool
    done: bool
    history: list[dict[str, Any]]
    error: str


class LLMClient:
    def __init__(self):
        self.provider = (Settings.LLM_PROVIDER or "").strip().lower()
        self.model = Settings.LLM_MODEL or "gpt-4o-mini"
        self.api_key = Settings.LLM_API_KEY
        self._client = self._init_client()

    def _init_client(self):
        if self.provider != "openai":
            return None
        if not self.api_key or ChatOpenAI is None:
            return None
        try:
            return ChatOpenAI(model=self.model, api_key=self.api_key, temperature=0)
        except Exception:
            return None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def invoke(self, system_prompt: str, user_prompt: str) -> str | None:
        if not self._client:
            return None
        try:
            response = self._client.invoke(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )
            content = getattr(response, "content", None)
            if isinstance(content, str):
                return content
            return str(content)
        except Exception:
            return None


class ErrorAnalysisAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, state: AIFixState) -> AIFixState:
        incident = state["incident"]
        logs_text = "\n".join([f"- {log.message}" for log in incident.sample_logs[:10]])
        fallback = incident.summary

        if not self.llm.enabled:
            state["diagnosis"] = fallback
            return state

        system_prompt = (
            "You are an incident diagnosis agent. "
            "Produce a concise root-cause hypothesis and likely failure mechanism."
        )
        user_prompt = (
            f"Incident summary: {incident.summary}\n"
            f"Fingerprint: {incident.log_fingerprints[:1]}\n"
            f"Sample logs:\n{logs_text}\n\n"
            "Return one concise paragraph."
        )
        diagnosis = self.llm.invoke(system_prompt, user_prompt)
        state["diagnosis"] = diagnosis.strip() if diagnosis else fallback
        return state


class CodebaseBacktrackingAgent:
    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root).resolve()

    def run(self, state: AIFixState) -> AIFixState:
        incident = state["incident"]
        candidate_files: list[str] = []

        for candidate in incident.trace_candidates:
            candidate_files.append(candidate.file_path)

        if not candidate_files:
            candidate_files = ["src/agents/triage_agent.py", "src/integrations/datadog_client.py"]

        expanded = set(candidate_files)
        for file_path in candidate_files[:3]:
            abs_path = self.repo_root / file_path
            if not abs_path.exists():
                continue
            try:
                text = abs_path.read_text(encoding="utf-8")
            except Exception:
                continue
            imports = re.findall(r"^\s*(?:from|import)\s+([a-zA-Z0-9_.]+)", text, flags=re.MULTILINE)
            for module in imports:
                rel = self._module_to_path(module)
                if rel:
                    expanded.add(rel)

        ranked = [p for p in expanded if p.endswith(".py")]
        ranked = sorted(ranked, key=lambda p: (0 if p.startswith("src/") else 1, p))
        state["candidate_files"] = ranked[:8]
        return state

    def _module_to_path(self, module: str) -> str | None:
        module_path = module.replace(".", "/")
        candidate_file = self.repo_root / f"{module_path}.py"
        if candidate_file.exists():
            return candidate_file.relative_to(self.repo_root).as_posix()
        candidate_init = self.repo_root / module_path / "__init__.py"
        if candidate_init.exists():
            return candidate_init.relative_to(self.repo_root).as_posix()
        return None


class FileNarrowingAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, state: AIFixState) -> AIFixState:
        candidates = state.get("candidate_files", [])
        incident = state["incident"]
        fallback_file = candidates[0] if candidates else "src/agents/triage_agent.py"
        fallback_line = incident.trace_candidates[0].line if incident.trace_candidates else None

        if not self.llm.enabled or not candidates:
            state["selected_file"] = fallback_file
            state["selected_line"] = fallback_line
            return state

        system_prompt = (
            "You are a file triage agent. Select the single most likely file for fix. "
            "Return strict JSON: {\"file_path\":\"...\"}."
        )
        user_prompt = (
            f"Diagnosis: {state.get('diagnosis')}\n"
            f"Incident summary: {incident.summary}\n"
            f"Candidate files: {candidates}\n"
            "Pick only one file from the list."
        )
        response = self.llm.invoke(system_prompt, user_prompt)
        chosen = fallback_file
        if response:
            parsed = _extract_json(response)
            candidate = str(parsed.get("file_path", "")).strip() if parsed else ""
            if candidate in candidates:
                chosen = candidate

        state["selected_file"] = chosen
        state["selected_line"] = fallback_line
        return state


class PatchGenerationAgent:
    def __init__(self, llm: LLMClient, repo_root: str):
        self.llm = llm
        self.repo_root = Path(repo_root).resolve()

    def run(self, state: AIFixState) -> AIFixState:
        target_rel = state.get("selected_file")
        if not target_rel:
            state["error"] = "No selected file for patch generation."
            return state
        target_abs = self.repo_root / target_rel
        if not target_abs.exists():
            state["error"] = f"Selected file does not exist: {target_rel}"
            return state

        text = target_abs.read_text(encoding="utf-8")
        lines = text.splitlines(keepends=True)
        line_no = state.get("selected_line") or 1
        idx = max(0, min(line_no - 1, len(lines) - 1))

        if not self.llm.enabled:
            original = lines[idx].strip() if lines else "pass"
            indent = re.match(r"^\s*", lines[idx]).group(0) if lines else ""
            patched = [
                f"{indent}try:\n",
                f"{indent}    {original}\n",
                f"{indent}except Exception as exc:\n",
                f"{indent}    raise RuntimeError('AI loop fallback guard') from exc\n",
            ]
            lines[idx : idx + 1] = patched
            patched_text = "".join(lines)
            state["patch_text"] = patched_text
            return state

        window_start = max(0, idx - 20)
        window_end = min(len(lines), idx + 20)
        context_window = "".join(lines[window_start:window_end])

        system_prompt = (
            "You are a Python patch generation agent. "
            "Return strict JSON with key `patched_code` containing complete updated file content. "
            "No markdown."
        )
        user_prompt = (
            f"File path: {target_rel}\n"
            f"Diagnosis: {state.get('diagnosis')}\n"
            f"Target line: {line_no}\n"
            f"Context window:\n{context_window}\n\n"
            "Generate safe minimal fix for the inferred error while preserving behavior."
        )
        response = self.llm.invoke(system_prompt, user_prompt)
        parsed = _extract_json(response or "")
        patched = str(parsed.get("patched_code", "")).strip() if parsed else ""
        if not patched:
            state["error"] = "LLM patch generation returned empty content."
            return state

        if not self._is_reasonable_patch(text, patched):
            state["error"] = "LLM patch rejected: patch scope too large or format unsafe."
            return state

        state["patch_text"] = patched
        return state

    def _is_reasonable_patch(self, original: str, patched: str) -> bool:
        original_lines = original.splitlines()
        patched_lines = patched.splitlines()
        if not patched_lines:
            return False
        if original_lines == patched_lines:
            return False

        diff = list(difflib.unified_diff(original_lines, patched_lines, lineterm=""))
        added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
        changed = added + removed
        max_allowed = max(20, int(len(original_lines) * 0.25))
        if changed > max_allowed:
            return False
        return True


class VerificationAgent:
    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root).resolve()
        self.remediator = RemediationAgent(repo_root=repo_root)

    def run(self, state: AIFixState) -> AIFixState:
        target_file = state.get("selected_file")
        patch_text = state.get("patch_text")
        if not target_file or not patch_text:
            state["success"] = False
            state["error"] = state.get("error", "Missing target file or patch text.")
            return state

        synthetic_state = {
            "status": "generated",
            "target_file": target_file,
            "target_line": state.get("selected_line"),
            "_patched_content": patch_text,
            "validation_passed": False,
            "applied": False,
            "backup_path": None,
        }
        synthetic_state = self.remediator.validate_patch_syntax(synthetic_state)
        if not synthetic_state.get("validation_passed"):
            synthetic_state["status"] = "validation_failed"
            state["remediation_state"] = synthetic_state
            state["repo_validation"] = {
                "ok": False,
                "returncode": -1,
                "command": "syntax-parse",
                "stderr_tail": synthetic_state.get("validation", {}).get("message", "syntax validation failed"),
                "stdout_tail": "",
            }
            state["success"] = False
            return state

        synthetic_state = self.remediator.apply_patch(synthetic_state)
        validation = self.remediator.run_repo_validation(state.get("validation_command"))
        state["repo_validation"] = validation
        if validation.get("ok"):
            state["success"] = True
            state["remediation_state"] = synthetic_state
            return state

        # Validation failed: rollback and continue loop.
        synthetic_state = self.remediator.rollback_patch(synthetic_state)
        state["success"] = False
        state["remediation_state"] = synthetic_state
        return state


class AIMultiAgentFixOrchestrator:
    def __init__(self, repo_root: str = ".", max_attempts: int = 3):
        self.repo_root = str(Path(repo_root).resolve())
        self.max_attempts = max(1, max_attempts)
        self.llm = LLMClient()
        self.error_agent = ErrorAnalysisAgent(self.llm)
        self.context_agent = CodebaseBacktrackingAgent(self.repo_root)
        self.narrow_agent = FileNarrowingAgent(self.llm)
        self.patch_agent = PatchGenerationAgent(self.llm, self.repo_root)
        self.verify_agent = VerificationAgent(self.repo_root)

    def run(self, incident: Incident, validation_command: str | None = None) -> dict[str, Any]:
        init_state: AIFixState = {
            "incident": incident,
            "repo_root": self.repo_root,
            "max_attempts": self.max_attempts,
            "validation_command": validation_command or Settings.REMEDIATION_VALIDATION_CMD,
            "attempt": 0,
            "history": [],
            "success": False,
            "done": False,
        }
        if StateGraph is not None and END is not None:
            try:
                return self._run_langgraph(init_state)
            except Exception:
                return self._run_loop(init_state)
        return self._run_loop(init_state)

    def _run_loop(self, state: AIFixState) -> dict[str, Any]:
        while not state.get("done"):
            state["attempt"] = int(state.get("attempt", 0)) + 1
            state = self.error_agent.run(state)
            state = self.context_agent.run(state)
            state = self.narrow_agent.run(state)
            state = self.patch_agent.run(state)
            state = self.verify_agent.run(state)

            self._append_history(state)

            if state.get("success"):
                state["done"] = True
                break
            if state.get("attempt", 0) >= state.get("max_attempts", self.max_attempts):
                state["done"] = True
                break

        return self._to_result(state)

    def _run_langgraph(self, init_state: AIFixState) -> dict[str, Any]:
        graph = StateGraph(dict)

        def node_error(state: dict) -> dict:
            return self.error_agent.run(state)  # type: ignore[arg-type]

        def node_context(state: dict) -> dict:
            return self.context_agent.run(state)  # type: ignore[arg-type]

        def node_narrow(state: dict) -> dict:
            return self.narrow_agent.run(state)  # type: ignore[arg-type]

        def node_patch(state: dict) -> dict:
            return self.patch_agent.run(state)  # type: ignore[arg-type]

        def node_verify(state: dict) -> dict:
            state["attempt"] = int(state.get("attempt", 0)) + 1
            state = self.verify_agent.run(state)  # type: ignore[arg-type]
            self._append_history(state)  # type: ignore[arg-type]
            if state.get("success"):
                state["done"] = True
            elif int(state.get("attempt", 0)) >= int(state.get("max_attempts", self.max_attempts)):
                state["done"] = True
            return state

        graph.add_node("error", node_error)
        graph.add_node("context", node_context)
        graph.add_node("narrow", node_narrow)
        graph.add_node("patch", node_patch)
        graph.add_node("verify", node_verify)
        graph.set_entry_point("error")
        graph.add_edge("error", "context")
        graph.add_edge("context", "narrow")
        graph.add_edge("narrow", "patch")
        graph.add_edge("patch", "verify")
        graph.add_conditional_edges(
            "verify",
            lambda st: END if st.get("done") else "error",
            {END: END, "error": "error"},
        )
        app = graph.compile()
        final_state = app.invoke(init_state)
        return self._to_result(final_state)  # type: ignore[arg-type]

    def _append_history(self, state: AIFixState):
        history = state.setdefault("history", [])
        history.append(
            {
                "attempt": state.get("attempt"),
                "diagnosis": state.get("diagnosis"),
                "selected_file": state.get("selected_file"),
                "selected_line": state.get("selected_line"),
                "success": state.get("success"),
                "repo_validation_ok": (state.get("repo_validation") or {}).get("ok"),
                "error": state.get("error"),
            }
        )

    def _to_result(self, state: AIFixState) -> dict[str, Any]:
        return {
            "success": bool(state.get("success")),
            "attempts": int(state.get("attempt", 0)),
            "max_attempts": int(state.get("max_attempts", self.max_attempts)),
            "selected_file": state.get("selected_file"),
            "selected_line": state.get("selected_line"),
            "diagnosis": state.get("diagnosis"),
            "history": state.get("history", []),
            "repo_validation": state.get("repo_validation"),
            "remediation_state": state.get("remediation_state"),
            "llm_enabled": self.llm.enabled,
            "llm_provider": self.llm.provider,
            "llm_model": self.llm.model,
        }


def _extract_json(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None
