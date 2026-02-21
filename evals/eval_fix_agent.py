from datetime import datetime

from braintrust import Eval

from src.agents.fix_agent import FixAgent
from src.agents.trace_agent import TraceAgent
from src.core.models import Incident, LogEvent


FIX_EVAL_DATA = [
    {
        "input": {
            "service": "billing",
            "messages": [
                "ValueError: division by zero in triage_agent.py line 13",
                "division by zero in triage_agent.py line 13",
            ],
            "fingerprints": ["ValueError: division by zero in triage_agent.py line 13"],
        },
        "expected": {
            "strategy": "guard_division_by_zero",
            "file_suffix": "src/agents/triage_agent.py",
        },
    },
    {
        "input": {
            "service": "tts",
            "messages": [
                "TimeoutError: request timed out in elevenlabs_tts.py line 45",
            ],
            "fingerprints": ["TimeoutError: request timed out in elevenlabs_tts.py line 45"],
        },
        "expected": {
            "strategy": "retry_timeout",
            "file_suffix": "src/integrations/elevenlabs_tts.py",
        },
    },
]


def run_fix(input_data):
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
        id="fix-eval",
        created_at=datetime.utcnow().isoformat(),
        service=input_data["service"],
        summary="",
        log_fingerprints=input_data["fingerprints"],
        sample_logs=logs,
        severity="high",
    )
    incident = TraceAgent(repo_root=".").enrich_incident(incident)
    incident = FixAgent().enrich_incident(incident)
    top = incident.fix_proposals[0] if incident.fix_proposals else None
    return {
        "count": len(incident.fix_proposals),
        "top_strategy": top.strategy if top else None,
        "top_file": top.file_path if top else None,
    }


def has_any_fix(input_data, output, expected):
    return 1.0 if output["count"] > 0 else 0.0


def top_strategy_match(input_data, output, expected):
    return 1.0 if output["top_strategy"] == expected["strategy"] else 0.0


def top_file_match(input_data, output, expected):
    top_file = output["top_file"]
    if not top_file:
        return 0.0
    return 1.0 if top_file.endswith(expected["file_suffix"]) else 0.0


Eval(
    "VoiceOps Fix Agent",
    data=lambda: FIX_EVAL_DATA,
    task=run_fix,
    scores=[has_any_fix, top_strategy_match, top_file_match],
    metadata={"component": "fix_agent", "suite": "strategy_selection"},
)
