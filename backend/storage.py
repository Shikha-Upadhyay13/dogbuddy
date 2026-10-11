"""Private file storage. Keys are facility-prefixed; URLs are short-lived HMAC tokens."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jose import JWTError, jwt

ROOT = Path(os.getenv("STORAGE_DIR", "storage"))
_SECRET = os.getenv("JWT_SECRET", "change-me-in-prod")


def save_bytes(facility_id: int, name: str, data: bytes) -> str:
    safe = Path(name).name or "file"
    key = f"{facility_id}/{datetime.now().strftime('%Y%m%d%H%M%S')}-{safe}"
    path = ROOT / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return key


def signed_path(key: str, minutes: int = 10) -> str:
    token = jwt.encode(
        {
            "key": key,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes),
        },
        _SECRET,
        algorithm="HS256",
    )
    return f"/media/{token}"


def resolve_token(token: str) -> Path:
    try:
        payload = jwt.decode(token, _SECRET, algorithms=["HS256"])
    except JWTError as err:
        raise FileNotFoundError("invalid token") from err
    key = payload.get("key") or ""
    path = (ROOT / key).resolve()
    if not str(path).startswith(str(ROOT.resolve())) or not path.is_file():
        raise FileNotFoundError("missing file")
    return path
