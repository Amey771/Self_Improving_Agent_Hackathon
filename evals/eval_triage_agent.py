from datetime import datetime

from braintrust import Eval

from src.agents.triage_agent import TriageAgent
from src.core.models import Incident, LogEvent


TRIAGE_EVAL_DATA = [
    {
        "input": {
            "service": "billing",
            "messages": [
                "ValueError: division by zero in billing.py line 42",
                "ValueError: division by zero in billing.py line 42",
                "Unhandled exception in payment processor",
            ],
        },
        "expected": {
            "signature": "ValueError: division by zero in billing.py line 42",
            "summary_contains": "Detected recurring signature:",
        },
    },
    {
        "input": {
            "service": "orders",
            "messages": [
                "checkout.py line 118 failed request to upstream service",
                "checkout.py line 118 failed request to upstream service",
                "TimeoutError: request timed out after 5s",
            ],
        },
        "expected": {
            "signature": "checkout.py:line 118",
            "summary_contains": "Detected recurring signature:",
        },
    },
]


def run_triage(input_data):
    logs = [
        LogEvent(
            timestamp=datetime.utcnow().isoformat(),
            service=input_data["service"],
            message=msg,
            attributes={},
        )
        for msg in input_data["messages"]
    ]
    incident = Incident(
        id="eval",
        created_at=datetime.utcnow().isoformat(),
        service=input_data["service"],
        summary="",
        log_fingerprints=[],
        sample_logs=logs,
        severity="high",
    )
    enriched = TriageAgent().enrich_incident(incident)
    signature = enriched.log_fingerprints[0] if enriched.log_fingerprints else "unknown"
    return {"signature": signature, "summary": enriched.summary}


def signature_exact_match(input_data, output, expected):
    return 1.0 if output["signature"] == expected["signature"] else 0.0


def summary_prefix_present(input_data, output, expected):
    return 1.0 if expected["summary_contains"] in output["summary"] else 0.0


Eval(
    "VoiceOps Triage Agent",
    data=lambda: TRIAGE_EVAL_DATA,
    task=run_triage,
    scores=[signature_exact_match, summary_prefix_present],
    metadata={"component": "triage_agent", "suite": "deterministic_patterns"},
)
