"""Cookie sessions, bcrypt passwords, and membership-scoped roles.

The session JWT lives in an httpOnly cookie. A Bearer token is accepted as
well so tests and scripts can call the API without a browser.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from db import Facility, Membership, OneTimeCode, User, get_db

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-prod")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRES_MINUTES = int(os.getenv("JWT_EXPIRES_MINUTES", "1440"))
COOKIE_NAME = "dogbuddy_session"
STAFF_ROLES = ("admin", "attendant")
PARENT_ROLE = "parent"
ROLES = STAFF_ROLES + (PARENT_ROLE,)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


@dataclass
class Principal:
    user: User
    membership: Membership
    facility: Facility

    @property
    def id(self) -> int:
        return self.user.id

    @property
    def role(self) -> str:
        return self.membership.role

    @property
    def name(self) -> str:
        return self.user.name

    @property
    def phone(self) -> str:
        return self.user.phone

    @property
    def facility_id(self) -> int:
        return self.facility.id


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def new_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def create_access_token(user_id: int, facility_id: int, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRES_MINUTES)
    payload = {
        "sub": str(user_id),
        "facility_id": facility_id,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("sub") is None or payload.get("facility_id") is None:
            raise JWTError("missing claims")
        return payload
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


def cookie_params() -> dict:
    secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    samesite = os.getenv("COOKIE_SAMESITE", "lax")
    return {
        "httponly": True,
        "secure": secure,
        "samesite": samesite,
        "path": "/",
        "max_age": JWT_EXPIRES_MINUTES * 60,
    }


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(COOKIE_NAME, token, **cookie_params())


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Principal:
    raw = token or request.cookies.get(COOKIE_NAME)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    payload = decode_token(raw)
    user = db.get(User, int(payload["sub"]))
    facility = db.get(Facility, int(payload["facility_id"]))
    if user is None or facility is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    membership = (
        db.query(Membership)
        .filter(
            Membership.user_id == user.id,
            Membership.facility_id == facility.id,
        )
        .one_or_none()
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No membership for this facility",
        )
    return Principal(user=user, membership=membership, facility=facility)


def require_role(*allowed_roles: str):
    """Only memberships with one of these roles pass."""

    def _dep(current: Principal = Depends(get_current_user)) -> Principal:
        if current.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires role: {' or '.join(allowed_roles)}",
            )
        return current

    return _dep


def get_current_staff(
    current: Principal = Depends(require_role(*STAFF_ROLES)),
) -> Principal:
    return current


def issue_code(
    db: Session,
    *,
    phone: str,
    purpose: str,
    facility_id: int | None = None,
    role: str | None = None,
    minutes: int = 15,
) -> str:
    """Store a hashed OTP and return the plaintext code once."""
    code = new_otp()
    db.add(
        OneTimeCode(
            phone=phone,
            purpose=purpose,
            code_hash=hash_code(code),
            facility_id=facility_id,
            role=role,
            expires_at=datetime.now() + timedelta(minutes=minutes),
        )
    )
    db.flush()
    return code


def consume_code(
    db: Session, *, phone: str, purpose: str, code: str
) -> OneTimeCode | None:
    now = datetime.now()
    row = (
        db.query(OneTimeCode)
        .filter(
            OneTimeCode.phone == phone,
            OneTimeCode.purpose == purpose,
            OneTimeCode.used_at.is_(None),
            OneTimeCode.expires_at >= now,
        )
        .order_by(OneTimeCode.id.desc())
        .first()
    )
    if row is None or row.code_hash != hash_code(code):
        return None
    row.used_at = now
    db.flush()
    return row
