"""Payload parsing helpers for hook input."""

from __future__ import annotations

import json


def read_json_payload(raw: str) -> dict:
    raw = raw.strip()
    return json.loads(raw) if raw else {}


def get_payload_session_id(payload) -> str | None:
    if isinstance(payload, dict):
        return payload.get("session_id")
    return None
