import requests
import random
from datetime import datetime, timedelta
from typing import List, Optional

from src.config import Settings
from src.core.models import Incident, LogEvent


class DatadogClient:
    def __init__(self):
        self.api_key = Settings.DD_API_KEY
        self.app_key = Settings.DD_APP_KEY
        self.site = Settings.DD_SITE

    def fetch_incident(self, service: str, minutes: int = 10, fallback_to_sim: bool = True) -> Incident:
        """
        Pull real logs from Datadog if keys exist.
        If keys are missing OR Datadog returns no logs (optional) -> simulate.
        """
        if not (self.api_key and self.app_key):
            return self._simulate_incident(service)

        incident = self._fetch_real(service, minutes)

        # Demo-safe: if no logs came back, fall back to simulated incident
        if fallback_to_sim and (not incident.sample_logs or len(incident.sample_logs) == 0):
            sim = self._simulate_incident(service)
            sim.summary = "Datadog returned no recent error logs. Using simulated incident for demo."
            return sim

        return incident

    def simulate_incident(self, service: str) -> Incident:
        """Public method so Streamlit can explicitly run demo mode."""
        return self._simulate_incident(service)

    def _fetch_real(self, service: str, minutes: int) -> Incident:
        url = f"https://api.{self.site}/api/v2/logs/events/search"

        now = datetime.utcnow()
        start = now - timedelta(minutes=minutes)

        # You can tweak query here if needed
        query = f"service:{service} (status:error OR @level:error OR @severity:error)"

        payload = {
            "filter": {
                "from": start.isoformat() + "Z",
                "to": now.isoformat() + "Z",
                "query": query
            },
            "sort": "timestamp",
            "page": {"limit": 10}
        }

        headers = {
            "DD-API-KEY": self.api_key,
            "DD-APPLICATION-KEY": self.app_key,
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers)

        # Handle Datadog errors cleanly
        if response.status_code != 200:
            # Fall back to simulated incident so demo doesn't break
            sim = self._simulate_incident(service)
            sim.summary = f"Datadog API error {response.status_code}. Using simulated incident for demo."
            return sim

        data = response.json()
        logs: List[LogEvent] = []

        for item in data.get("data", []):
            attrs = item.get("attributes", {}) or {}
            logs.append(
                LogEvent(
                    timestamp=str(attrs.get("timestamp", "")),
                    service=service,
                    message=str(attrs.get("message", "")),
                    attributes=attrs
                )
            )

        summary = "Error spike detected from Datadog logs." if logs else "No recent error logs found in Datadog."

        return Incident(
            id=str(random.randint(1000, 9999)),
            created_at=now.isoformat(),
            service=service,
            summary=summary,
            log_fingerprints=["error_spike"],
            sample_logs=logs,
            severity="high"
        )

    def _simulate_incident(self, service: str) -> Incident:
        now = datetime.utcnow()

        fake_logs = [
            LogEvent(
                timestamp=now.isoformat(),
                service=service,
                message="ValueError: division by zero in billing.py line 42",
                attributes={"source": "simulated"}
            ),
            LogEvent(
                timestamp=now.isoformat(),
                service=service,
                message="Unhandled exception in payment processor",
                attributes={"source": "simulated"}
            ),
        ]

        return Incident(
            id=str(random.randint(1000, 9999)),
            created_at=now.isoformat(),
            service=service,
            summary="Simulated error spike detected.",
            log_fingerprints=["division_by_zero"],
            sample_logs=fake_logs,
            severity="high"
        )