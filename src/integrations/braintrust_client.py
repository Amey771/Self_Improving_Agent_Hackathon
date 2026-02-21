from __future__ import annotations

from typing import Any

from src.config import Settings
from src.core.models import Incident

try:
    from braintrust import init_logger
except Exception:  # pragma: no cover - optional dependency
    init_logger = None


class BraintrustClient:
    """
    Lightweight wrapper around Braintrust logging.
    The app should continue running even if Braintrust is not configured.
    """

    def __init__(self):
        self.api_key = Settings.BRAINTRUST_API_KEY
        self.project = Settings.BRAINTRUST_PROJECT
        self.api_url = Settings.BRAINTRUST_API_URL
        self._logger = None
        self._status = self._initialize()

    def _initialize(self) -> dict[str, Any]:
        if init_logger is None:
            return {"enabled": False, "reason": "braintrust_sdk_not_installed"}
        if not self.api_key:
            return {"enabled": False, "reason": "missing_api_key"}
        try:
            logger_kwargs: dict[str, Any] = {
                "project": self.project,
                "api_key": self.api_key,
            }
            if self.api_url:
                logger_kwargs["app_url"] = self.api_url

            self._logger = init_logger(**logger_kwargs)
            return {"enabled": True, "reason": "ok"}
        except Exception as exc:
            return {"enabled": False, "reason": f"init_failed:{exc.__class__.__name__}"}

    def status(self) -> dict[str, Any]:
        return dict(self._status)

    def log_incident_run(
        self,
        incident: Incident,
        *,
        service: str,
        minutes: int,
        source: str,
        voice_generated: bool,
    ) -> bool:
        if not self._status["enabled"] or not self._logger:
            return False

        signature = incident.log_fingerprints[0] if incident.log_fingerprints else "unknown"
        triage_quality = 1.0 if signature != "unknown" else 0.0
        trace_found = 1.0 if incident.trace_candidates else 0.0
        top_trace = incident.trace_candidates[0].model_dump() if incident.trace_candidates else None
        fix_found = 1.0 if incident.fix_proposals else 0.0
        top_fix = incident.fix_proposals[0].model_dump() if incident.fix_proposals else None

        try:
            self._logger.log(
                input={
                    "service": service,
                    "lookback_minutes": minutes,
                    "source": source,
                    "sample_logs": [log.model_dump() for log in incident.sample_logs],
                },
                output={
                    "incident_id": incident.id,
                    "summary": incident.summary,
                    "severity": incident.severity,
                    "signature": signature,
                    "top_trace": top_trace,
                    "trace_candidates": [candidate.model_dump() for candidate in incident.trace_candidates],
                    "top_fix": top_fix,
                    "fix_proposals": [proposal.model_dump() for proposal in incident.fix_proposals],
                    "voice_generated": voice_generated,
                },
                metadata={
                    "component": "voiceops_streamlit",
                    "project": "self_improving_agent_hackathon",
                },
                scores={
                    "triage_signature_detected": triage_quality,
                    "trace_candidate_found": trace_found,
                    "fix_proposal_generated": fix_found,
                    "voice_generation_success": 1.0 if voice_generated else 0.0,
                },
                tags=["voiceops", f"service:{service}", f"source:{source}"],
            )
            self._logger.flush()
            return True
        except Exception:
            return False
