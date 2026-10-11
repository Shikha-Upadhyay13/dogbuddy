"""Pin a throwaway SQLite database before the app imports its engine."""

from __future__ import annotations

import os
from pathlib import Path

_DB = Path(__file__).parent / "_tmp.db"
if _DB.exists():
    _DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{_DB.as_posix()}"
os.environ["DOGBUDDY_SKIP_AGENT"] = "1"
os.environ["COOKIE_SECURE"] = "false"
os.environ["COOKIE_SAMESITE"] = "lax"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["DOGBUDDY_DEBUG_OTP"] = "1"
os.environ["DOGBUDDY_SKIP_JOBS"] = "1"
os.environ["DOGBUDDY_DISABLE_RATE_LIMIT"] = "1"

import pytest
from fastapi.testclient import TestClient

from db import Base, engine
from main import app


@pytest.fixture()
def client():
    assert str(engine.url).startswith("sqlite"), "tests must not touch a real database"
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)
