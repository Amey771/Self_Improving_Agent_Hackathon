from datetime import datetime

from braintrust import Eval

from src.agents.trace_agent import TraceAgent
from src.core.models import Incident, LogEvent


TRACE_EVAL_DATA = [
    {
        "input": {
            "service": "triage",
            "messages": [
                "ValueError: parse failure in triage_agent.py line 13",
                "triage_agent.py line 13 raised repeatedly",
            ],
        },
        "expected": {
            "file_suffix": "src/agents/triage_agent.py",
            "line": 13,
        },
    },
    {
        "input": {
            "service": "tts",
            "messages": [
                "RuntimeError in elevenlabs_tts.py:45 during synthesis",
            ],
        },
        "expected": {
            "file_suffix": "src/integrations/elevenlabs_tts.py",
            "line": 45,
        },
    },
]


def run_trace(input_data):
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
        id="trace-eval",
        created_at=datetime.utcnow().isoformat(),
        service=input_data["service"],
        summary="",
        log_fingerprints=[],
        sample_logs=logs,
        severity="high",
    )
    traced = TraceAgent(repo_root=".").enrich_incident(incident)
    top = traced.trace_candidates[0] if traced.trace_candidates else None
    return {
        "top_file": top.file_path if top else None,
        "top_line": top.line if top else None,
        "count": len(traced.trace_candidates),
    }


def top_file_match(input_data, output, expected):
    top_file = output["top_file"]
    if not top_file:
        return 0.0
    return 1.0 if top_file.endswith(expected["file_suffix"]) else 0.0


def top_line_match(input_data, output, expected):
    return 1.0 if output["top_line"] == expected["line"] else 0.0


def has_any_candidate(input_data, output, expected):
    return 1.0 if output["count"] > 0 else 0.0


Eval(
    "VoiceOps Trace Agent",
    data=lambda: TRACE_EVAL_DATA,
    task=run_trace,
    scores=[has_any_candidate, top_file_match, top_line_match],
    metadata={"component": "trace_agent", "suite": "file_line_resolution"},
)
