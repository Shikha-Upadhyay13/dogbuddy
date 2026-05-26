"""FastAPI application entrypoint. Phase 1: auth endpoints only.

Domain endpoints (dogs, bookings, incidents, chat) are added in later phases.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from auth import (
    create_access_token,
    get_current_staff,
    hash_password,
    verify_password,
)
from db import Staff, get_db, init_db
from schemas import AuthResponse, LoginRequest, SignupRequest, StaffOut

app = FastAPI(title="DogBuddy API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# --- Auth ---

@app.post("/auth/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, db: Session = Depends(get_db)) -> AuthResponse:
    existing = db.query(Staff).filter(Staff.phone == body.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="Phone already registered")

    staff = Staff(
        name=body.name,
        phone=body.phone,
        password_hash=hash_password(body.password),
    )
    db.add(staff)
    db.commit()
    db.refresh(staff)

    token = create_access_token(staff.id)
    return AuthResponse(token=token, staff=StaffOut.model_validate(staff))


@app.post("/auth/login", response_model=AuthResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    staff = db.query(Staff).filter(Staff.phone == body.phone).first()
    if staff is None or not verify_password(body.password, staff.password_hash):
        raise HTTPException(status_code=401, detail="Invalid phone or password")

    token = create_access_token(staff.id)
    return AuthResponse(token=token, staff=StaffOut.model_validate(staff))


@app.get("/auth/me", response_model=StaffOut)
def me(current: Staff = Depends(get_current_staff)) -> StaffOut:
    return StaffOut.model_validate(current)
