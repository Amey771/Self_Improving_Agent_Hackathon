import re
from pathlib import Path
from typing import List

from src.core.models import Incident, TraceResult


class TraceAgent:
    """
    Deterministic trace:
    - extracts filename + line number from the incident fingerprint
    - searches repo for that file
    - returns suspect file paths + nearby snippet
    """

    def trace(self, repo_path: str, incident: Incident) -> TraceResult:
        fingerprint = incident.log_fingerprints[0] if incident.log_fingerprints else ""
        filename, lineno = self._extract_file_and_line(fingerprint)

        suspected_files: List[str] = []
        matched_snippets: List[str] = []

        repo = Path(repo_path)
        if not repo.exists():
            return TraceResult(
                suspected_files=[],
                matched_snippets=[],
                hypothesis=f"Repo path not found: {repo_path}"
            )

        # If we got a filename, search for it in repo
        if filename:
            for p in repo.rglob(filename):
                suspected_files.append(str(p))
                if lineno:
                    snippet = self._read_snippet(p, lineno)
                    if snippet:
                        matched_snippets.append(snippet)

        hypothesis = self._build_hypothesis(fingerprint, suspected_files, lineno)

        return TraceResult(
            suspected_files=suspected_files,
            matched_snippets=matched_snippets,
            hypothesis=hypothesis
        )

    def _extract_file_and_line(self, text: str):
        # Match: billing.py line 42
        m = re.search(r"([A-Za-z0-9_\-]+\.py)\s+line\s+(\d+)", text)
        if m:
            return m.group(1), int(m.group(2))

        # Match: billing.py:42
        m = re.search(r"([A-Za-z0-9_\-]+\.py):(\d+)", text)
        if m:
            return m.group(1), int(m.group(2))

        # Just filename
        m = re.search(r"([A-Za-z0-9_\-]+\.py)", text)
        if m:
            return m.group(1), None

        return None, None

    def _read_snippet(self, path: Path, lineno: int, context: int = 3) -> str:
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            start = max(0, lineno - 1 - context)
            end = min(len(lines), lineno + context)
            block = lines[start:end]
            numbered = []
            for i, line in enumerate(block, start=start + 1):
                numbered.append(f"{i}: {line}")
            return f"--- {path} ---\n" + "\n".join(numbered)
        except Exception:
            return ""

    def _build_hypothesis(self, fingerprint: str, files: List[str], lineno: int | None) -> str:
        if not files:
            return "Could not locate referenced file in repo. Verify repo path or file name in logs."

        if "division by zero" in fingerprint.lower():
            if lineno:
                return f"Likely division by zero at line {lineno}. Add guard: if denominator == 0, handle safely."
            return "Likely division by zero. Add denominator checks / input validation."

        return "Log signature mapped to file(s). Next step: generate minimal patch + verify."