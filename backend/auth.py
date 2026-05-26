"""JWT auth + bcrypt password hashing + FastAPI dependencies.

We use the `bcrypt` library directly (passlib is unmaintained and warns
on bcrypt >=4.1.0).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from db import Staff, get_db

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-prod")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRES_MINUTES = int(os.getenv("JWT_EXPIRES_MINUTES", "1440"))

# tokenUrl is informational; the frontend posts to /auth/login directly.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(staff_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRES_MINUTES)
    payload = {"sub": str(staff_id), "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> int:
    """Returns staff_id. Raises HTTPException on invalid/expired token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            raise JWTError("missing sub")
        return int(sub)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_staff(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Staff:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    staff_id = decode_token(token)
    staff = db.get(Staff, staff_id)
    if staff is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Staff not found",
        )
    return staff
