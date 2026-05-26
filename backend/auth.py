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


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Staff:
    """Resolve the JWT into a Staff row (which now represents any user --
    staff OR owner -- distinguished by the `role` column)."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = decode_token(token)
    user = db.get(Staff, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def require_role(*allowed_roles: str):
    """FastAPI dependency factory: only lets users with one of the listed
    roles through. Usage: `current = Depends(require_role('staff'))`."""

    def _dep(current: Staff = Depends(get_current_user)) -> Staff:
        if current.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires role: {' or '.join(allowed_roles)}",
            )
        return current

    return _dep


# Backwards-compat alias: every endpoint that used get_current_staff still
# works, but now also implicitly enforces the staff role.
def get_current_staff(
    current: Staff = Depends(require_role("staff")),
) -> Staff:
    return current
