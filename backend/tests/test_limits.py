"""Auth is rate-limited. The medication prompt still forbids a dose."""

from __future__ import annotations

from pathlib import Path

from limits import allow, reset_limits


def test_auth_limit_returns_429(client, monkeypatch):
    monkeypatch.setenv("DOGBUDDY_DISABLE_RATE_LIMIT", "0")
    monkeypatch.setenv("DOGBUDDY_AUTH_LIMIT", "2")
    reset_limits()
    body = {"phone": "9000000000", "password": "nope", "facility_slug": "demo"}
    assert client.post("/auth/login", json=body).status_code in (401, 404, 422)
    assert client.post("/auth/login", json=body).status_code in (401, 404, 422)
    blocked = client.post("/auth/login", json=body)
    assert blocked.status_code == 429


def test_allow_resets_between_callers():
    reset_limits()
    assert allow("a", 1) is True
    assert allow("a", 1) is False
    assert allow("b", 1) is True


def test_health_advisor_refuses_medication_doses():
    prompt = Path("agent/prompts/health_advisor.md").read_text(encoding="utf-8")
    assert "NEVER give a specific dose" in prompt
