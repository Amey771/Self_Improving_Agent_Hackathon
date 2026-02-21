from pydantic import BaseModel
from typing import List, Dict, Any


class LogEvent(BaseModel):
    timestamp: str
    service: str
    message: str
    attributes: Dict[str, Any] = {}


class Incident(BaseModel):
    id: str
    created_at: str
    service: str
    summary: str
    log_fingerprints: List[str]
    sample_logs: List[LogEvent]
    severity: str