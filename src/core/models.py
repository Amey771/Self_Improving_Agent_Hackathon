from pydantic import BaseModel, Field
from typing import List, Dict, Any


class LogEvent(BaseModel):
    timestamp: str
    service: str
    message: str
    attributes: Dict[str, Any] = Field(default_factory=dict)


class TraceCandidate(BaseModel):
    file_path: str
    line: int | None = None
    confidence: float
    reason: str


class FixProposal(BaseModel):
    file_path: str
    line: int | None = None
    title: str
    strategy: str
    patch_plan: str
    confidence: float
    risk: str
    reason: str


class Incident(BaseModel):
    id: str
    created_at: str
    service: str
    summary: str
    log_fingerprints: List[str]
    sample_logs: List[LogEvent]
    severity: str
    trace_candidates: List[TraceCandidate] = Field(default_factory=list)
    fix_proposals: List[FixProposal] = Field(default_factory=list)
