import requests
import random
from datetime import datetime, timedelta
from typing import List
from src.config import Settings
from src.core.models import Incident, LogEvent


class DatadogClient:
    def __init__(self):
        self.api_key = Settings.DD_API_KEY
        self.app_key = Settings.DD_APP_KEY
        self.site = Settings.DD_SITE

    def fetch_incident(self, service: str, minutes: int = 10) -> Incident:
        """
        If Datadog keys exist → pull real logs.
        Otherwise → simulate an incident.
        """
        if self.api_key and self.app_key:
            return self._fetch_real(service, minutes)
        else:
            return self._simulate_incident(service)

    def _fetch_real(self, service: str, minutes: int) -> Incident:
        url = f"https://api.{self.site}/api/v2/logs/events/search"

        now = datetime.utcnow()
        start = now - timedelta(minutes=minutes)

        payload = {
            "filter": {
                "from": start.isoformat() + "Z",
                "to": now.isoformat() + "Z",
                "query": f"service:{service} status:error"
            },
            "page": {"limit": 10}
        }

        headers = {
            "DD-API-KEY": self.api_key,
            "DD-APPLICATION-KEY": self.app_key,
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers)
        data = response.json()

        logs: List[LogEvent] = []

        for item in data.get("data", []):
            attrs = item.get("attributes", {})
            logs.append(
                LogEvent(
                    timestamp=attrs.get("timestamp", ""),
                    service=service,
                    message=attrs.get("message", ""),
                    attributes=attrs
                )
            )

        return Incident(
            id=str(random.randint(1000, 9999)),
            created_at=now.isoformat(),
            service=service,
            summary="Error spike detected from Datadog logs.",
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
                attributes={}
            ),
            LogEvent(
                timestamp=now.isoformat(),
                service=service,
                message="Unhandled exception in payment processor",
                attributes={}
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