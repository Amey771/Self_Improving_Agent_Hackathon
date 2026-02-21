import re
from dataclasses import dataclass, field
from typing import List
from src.core.models import Incident


@dataclass
class SourceTrace:
    file: str
    line: int | None
    snippet: str

    def format_location(self) -> str:
        return f"`{self.file}:{self.line}`" if self.line is not None else f"`{self.file}`"


@dataclass
class TraceResult:
    incident_id: str
    traces: List[SourceTrace] = field(default_factory=list)
    raw_fingerprints: List[str] = field(default_factory=list)


class TraceAgent:
    """
    Maps log fingerprints and sample log messages to source file locations.
    Extracts file:line references from error signatures.
    """

    _MAX_SNIPPET_LENGTH = 120

    # Patterns to extract file + line references from log messages
    _FILE_LINE_PATTERNS = [
        # "billing.py line 42"  or  "billing.py:42"
        re.compile(r"(\w[\w/.-]*\.py)[:\s]+(?:line\s+)?(\d+)", re.IGNORECASE),
        # "File \"billing.py\", line 42"  (Python traceback style)
        re.compile(r'File\s+"([^"]+\.py)",\s+line\s+(\d+)', re.IGNORECASE),
        # Generic: module.submodule (line 42)
        re.compile(r"([\w.]+)\s+\(line\s+(\d+)\)", re.IGNORECASE),
    ]

    def trace_incident(self, incident: Incident) -> TraceResult:
        """
        Inspect an incident's log messages and fingerprints to produce
        a list of SourceTrace objects pointing at the relevant source locations.
        """
        result = TraceResult(
            incident_id=incident.id,
            raw_fingerprints=list(incident.log_fingerprints),
        )

        seen: set = set()

        # Walk every sample log message
        for log in incident.sample_logs:
            self._extract_traces(log.message, result, seen)

        # Also scan the fingerprint strings themselves
        for fp in incident.log_fingerprints:
            self._extract_traces(fp, result, seen)

        # If nothing was resolved, surface a generic placeholder
        if not result.traces:
            result.traces.append(
                SourceTrace(
                    file="unknown",
                    line=None,
                    snippet="No explicit file reference found in logs.",
                )
            )

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_traces(self, text: str, result: TraceResult, seen: set) -> None:
        for pattern in self._FILE_LINE_PATTERNS:
            for match in pattern.finditer(text):
                file_name = match.group(1)
                line_num = int(match.group(2))
                key = (file_name, line_num)
                if key not in seen:
                    seen.add(key)
                    result.traces.append(
                        SourceTrace(
                            file=file_name,
                            line=line_num,
                            snippet=text[:self._MAX_SNIPPET_LENGTH].strip(),
                        )
                    )
