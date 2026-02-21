from __future__ import annotations

from src.core.models import FixProposal, Incident


class FixAgent:
    """
    Deterministic patch proposal agent.
    Produces ranked fix proposals using triage signature + trace hints.
    """

    def enrich_incident(self, incident: Incident) -> Incident:
        signature = incident.log_fingerprints[0] if incident.log_fingerprints else incident.summary
        signature_l = signature.lower()
        top_trace = incident.trace_candidates[0] if incident.trace_candidates else None
        target_file = top_trace.file_path if top_trace else "unknown"
        target_line = top_trace.line if top_trace else None

        proposals: list[FixProposal] = []

        if "division by zero" in signature_l or "zerodivision" in signature_l:
            proposals.append(
                FixProposal(
                    file_path=target_file,
                    line=target_line,
                    title="Add denominator guard before division",
                    strategy="guard_division_by_zero",
                    patch_plan=(
                        "Before division, validate denominator is non-zero. "
                        "If zero, return a controlled error path and log structured context."
                    ),
                    confidence=0.86,
                    risk="low",
                    reason="Signature indicates repeated divide-by-zero failures.",
                )
            )

        if "timeout" in signature_l:
            proposals.append(
                FixProposal(
                    file_path=target_file,
                    line=target_line,
                    title="Add retry with bounded backoff for timeout paths",
                    strategy="retry_timeout",
                    patch_plan=(
                        "Wrap outbound call in retry policy with jittered exponential backoff, "
                        "max attempts, and explicit timeout budget."
                    ),
                    confidence=0.82,
                    risk="medium",
                    reason="Signature indicates timeout-related instability.",
                )
            )

        if "valueerror" in signature_l and not proposals:
            proposals.append(
                FixProposal(
                    file_path=target_file,
                    line=target_line,
                    title="Validate inputs before critical operation",
                    strategy="input_validation",
                    patch_plan=(
                        "Add explicit schema/type checks and fail fast with a clear validation "
                        "error before executing business logic."
                    ),
                    confidence=0.74,
                    risk="low",
                    reason="ValueError often indicates malformed input reaching business logic.",
                )
            )

        if "keyerror" in signature_l:
            proposals.append(
                FixProposal(
                    file_path=target_file,
                    line=target_line,
                    title="Harden dictionary access",
                    strategy="safe_dict_access",
                    patch_plan=(
                        "Replace direct key indexing with guarded access (`get`) and defaults. "
                        "Emit warning telemetry when required keys are absent."
                    ),
                    confidence=0.79,
                    risk="low",
                    reason="KeyError suggests missing field assumptions.",
                )
            )

        if not proposals:
            proposals.append(
                FixProposal(
                    file_path=target_file,
                    line=target_line,
                    title="Add defensive error boundary and observability",
                    strategy="defensive_error_boundary",
                    patch_plan=(
                        "Wrap the failing code region with targeted exception handling, "
                        "structured logs, and stable fallback behavior."
                    ),
                    confidence=0.6,
                    risk="medium",
                    reason="No strong signature-specific strategy matched.",
                )
            )

        incident.fix_proposals = sorted(proposals, key=lambda item: item.confidence, reverse=True)[:3]
        return incident
