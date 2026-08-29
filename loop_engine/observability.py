"""
loop_engine/observability.py
Structured Logging, Consequential Event Tracking, and Diagnostic Observability for 10 SHADOWS.

Invariants:
1. Structured JSON events contain run_id, task_id, component, event_type, candidate_sha, and timestamp.
2. Sensitive keys and tokens are automatically redacted.
3. Decouples human-readable terminal streams from authoritative receipts and telemetry records.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

SENSITIVE_PATTERNS = {"api_key", "token", "password", "secret", "auth", "credential"}


def redact_sensitive_data(data: Any) -> Any:
    """Recursively redacts values for keys matching sensitive naming patterns."""
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            if any(p in k.lower() for p in SENSITIVE_PATTERNS) and isinstance(v, str):
                cleaned[k] = "[REDACTED]"
            else:
                cleaned[k] = redact_sensitive_data(v)
        return cleaned
    elif isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]
    return data


@dataclass
class StructuredEvent:
    event_type: str
    component: str
    run_id: Optional[str] = None
    task_id: Optional[str] = None
    objective_version: Optional[int] = None
    candidate_sha: Optional[str] = None
    status: str = "INFO"
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["details"] = redact_sensitive_data(self.details)
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)


class StructuredLogger:
    """
    Standard structured logger for Ten Shadows subsystems.
    """

    def __init__(self, component_name: str, stream: Optional[Any] = None):
        self.component_name = component_name
        self.stream = stream or sys.stderr

    def emit(
        self,
        event_type: str,
        run_id: Optional[str] = None,
        task_id: Optional[str] = None,
        candidate_sha: Optional[str] = None,
        objective_version: Optional[int] = None,
        status: str = "INFO",
        **details: Any,
    ) -> StructuredEvent:
        event = StructuredEvent(
            event_type=event_type,
            component=self.component_name,
            run_id=run_id,
            task_id=task_id,
            objective_version=objective_version,
            candidate_sha=candidate_sha,
            status=status,
            details=details,
        )
        msg = f"[{event.timestamp}] [{event.status}] [{self.component_name}] {event.event_type}"
        if run_id:
            msg += f" (run={run_id})"
        if details:
            cleaned_details = redact_sensitive_data(details)
            msg += f" | {json.dumps(cleaned_details)}"
        print(msg, file=self.stream, flush=True)
        return event


def get_logger(component_name: str) -> StructuredLogger:
    return StructuredLogger(component_name)
