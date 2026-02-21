from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from src.core.models import Incident, TraceCandidate


class TraceAgent:
    """
    First-pass trace agent:
    - extract file/line hints from logs/fingerprints
    - resolve hints against local repo Python files
    - rank and attach candidate code locations
    """

    FILE_LINE_PATTERNS = [
        re.compile(r'File\s+"([^"]+\.py)"\s*,\s*line\s+(\d+)', re.IGNORECASE),
        re.compile(r"([\w./\\-]+\.py)\s+line\s+(\d+)", re.IGNORECASE),
        re.compile(r"([\w./\\-]+\.py):(\d+)", re.IGNORECASE),
    ]
    FILE_ONLY_PATTERN = re.compile(r"([\w./\\-]+\.py)", re.IGNORECASE)

    def __init__(self, repo_root: str = "."):
        self.repo_root = Path(repo_root).resolve()
        self._python_files = self._index_python_files()

    def enrich_incident(self, incident: Incident) -> Incident:
        candidates: list[TraceCandidate] = []
        messages = [log.message for log in incident.sample_logs if log.message]
        messages.extend(incident.log_fingerprints)

        for message in messages:
            candidates.extend(self._candidates_from_message(message))

        if not candidates:
            candidates.extend(self._fallback_from_service(incident.service))

        incident.trace_candidates = self._dedupe_and_rank(candidates)
        return incident

    def _index_python_files(self) -> list[Path]:
        files: list[Path] = []
        for path in self.repo_root.rglob("*.py"):
            path_str = str(path)
            if "__pycache__" in path_str or ".venv" in path_str or "venv" in path_str:
                continue
            files.append(path)
        return files

    def _candidates_from_message(self, message: str) -> list[TraceCandidate]:
        found: list[TraceCandidate] = []

        for pattern in self.FILE_LINE_PATTERNS:
            for match in pattern.finditer(message):
                hint_path = match.group(1)
                line = int(match.group(2))
                for resolved in self._resolve_path_hint(hint_path):
                    found.append(
                        TraceCandidate(
                            file_path=resolved,
                            line=line,
                            confidence=0.95,
                            reason=f"matched '{hint_path}' with explicit line in logs",
                        )
                    )

        for file_match in self.FILE_ONLY_PATTERN.finditer(message):
            hint_path = file_match.group(1)
            if any(candidate.file_path.endswith(hint_path.split("/")[-1]) for candidate in found):
                continue
            for resolved in self._resolve_path_hint(hint_path):
                found.append(
                    TraceCandidate(
                        file_path=resolved,
                        line=None,
                        confidence=0.75,
                        reason=f"matched '{hint_path}' in logs",
                    )
                )

        return found

    def _resolve_path_hint(self, hint_path: str) -> list[str]:
        normalized_hint = hint_path.replace("\\", "/")
        hint_name = Path(normalized_hint).name.lower()

        direct = self.repo_root / normalized_hint
        if direct.exists() and direct.is_file():
            return [self._rel_path(direct)]

        matches = [
            self._rel_path(path)
            for path in self._python_files
            if path.name.lower() == hint_name or str(path).replace("\\", "/").endswith(normalized_hint)
        ]
        return sorted(set(matches))

    def _fallback_from_service(self, service: str) -> list[TraceCandidate]:
        service_token = service.strip().lower()
        if not service_token:
            return []

        scored: list[TraceCandidate] = []
        for path in self._python_files:
            rel = self._rel_path(path)
            path_text = rel.lower()
            if service_token in path_text:
                scored.append(
                    TraceCandidate(
                        file_path=rel,
                        line=None,
                        confidence=0.4,
                        reason=f"service token '{service_token}' matched file path",
                    )
                )
        return scored[:3]

    def _dedupe_and_rank(self, candidates: Iterable[TraceCandidate]) -> list[TraceCandidate]:
        best: dict[tuple[str, int | None], TraceCandidate] = {}
        for candidate in candidates:
            key = (candidate.file_path, candidate.line)
            if key not in best or candidate.confidence > best[key].confidence:
                best[key] = candidate

        ranked = sorted(
            best.values(),
            key=lambda item: item.confidence + self._priority_bonus(item.file_path),
            reverse=True,
        )
        return ranked[:5]

    def _rel_path(self, path: Path) -> str:
        try:
            return path.relative_to(self.repo_root).as_posix()
        except ValueError:
            return path.as_posix()

    def _priority_bonus(self, file_path: str) -> float:
        normalized = file_path.lower()
        if normalized.startswith("src/"):
            return 0.05
        if normalized.startswith("evals/") or normalized.startswith("tests/"):
            return -0.05
        return 0.0
