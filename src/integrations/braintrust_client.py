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
        voice_profile: dict[str, Any] | None = None,
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
                    "voice_profile": voice_profile,
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

    def log_remediation_event(
        self,
        incident: Incident,
        *,
        action: str,
        remediation_state: dict[str, Any],
        repo_validation: dict[str, Any] | None = None,
    ) -> bool:
        if not self._status["enabled"] or not self._logger:
            return False

        try:
            self._logger.log(
                input={
                    "incident_id": incident.id,
                    "service": incident.service,
                    "severity": incident.severity,
                    "action": action,
                },
                output={
                    "status": remediation_state.get("status"),
                    "target_file": remediation_state.get("target_file"),
                    "target_line": remediation_state.get("target_line"),
                    "strategy": remediation_state.get("strategy"),
                    "validation_passed": remediation_state.get("validation_passed", False),
                    "applied": remediation_state.get("applied", False),
                    "backup_path": remediation_state.get("backup_path"),
                    "repo_validation": repo_validation,
                },
                metadata={
                    "component": "voiceops_remediation",
                    "project": "self_improving_agent_hackathon",
                },
                scores={
                    "patch_generated": 1.0 if remediation_state.get("status") == "generated" else 0.0,
                    "patch_validation_passed": 1.0 if remediation_state.get("validation_passed") else 0.0,
                    "patch_applied": 1.0 if remediation_state.get("applied") else 0.0,
                    "repo_validation_passed": 1.0 if (repo_validation or {}).get("ok") else 0.0,
                },
                tags=["voiceops", "remediation", f"action:{action}", f"service:{incident.service}"],
            )
            self._logger.flush()
            return True
        except Exception:
            return False
