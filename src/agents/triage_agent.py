import re
from collections import Counter
from src.core.models import Incident

class TriageAgent:
    """
    Deterministic triage (no LLM yet):
    - extracts top error signature
    - creates a crisp summary
    - sets log_fingerprints for memory/self-improvement
    """

    def enrich_incident(self, incident: Incident) -> Incident:
        messages = [l.message for l in incident.sample_logs if l.message]

        signatures = []
        for m in messages:
            m = m.strip()

            # Extract common error patterns like: ValueError: something...
            match = re.search(r"(\w+Error|Exception):\s*(.*)", m)
            if match:
                err = match.group(1)
                detail = match.group(2)
                detail = re.sub(r"\s+", " ", detail)[:80]
                signatures.append(f"{err}: {detail}")
                continue

            # Extract file:line patterns if present
            file_match = re.search(r"(\w+\.py)\s+line\s+(\d+)", m)
            if file_match:
                signatures.append(f"{file_match.group(1)}:line {file_match.group(2)}")
                continue

            signatures.append(m[:100])

        top = Counter(signatures).most_common(1)[0][0] if signatures else "unknown"

        incident.log_fingerprints = [top]
        incident.summary = f"Detected recurring signature: {top}"
        return incident