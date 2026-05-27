"""FastAPI application entrypoint.

Phase 1: /auth/*
Phase 2: /dogs, /bookings/today, /bookings/{id}/status, /bookings/{id}/activity,
         /incidents, /incidents/recent
Phase 3: /chat (SSE streaming)
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

# Force UTF-8 stdout so Windows cp1252 doesn't crash on Unicode in prompts/logs.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

from audit import write_audit
from auth import (
    create_access_token,
    get_current_staff,
    get_current_user,
    hash_password,
    require_role,
    verify_password,
)
from db import AuditLog, Booking, Dog, Incident, Staff, get_db, init_db
from schemas import (
    ActivityUpdate,
    AuditLogOut,
    AuthResponse,
    BookingOut,
    BookingsTodayOut,
    ChatRequest,
    CreateBookingRequest,
    CreateDogRequest,
    DogDetailOut,
    DogOut,
    IncidentIn,
    IncidentOut,
    LoginRequest,
    OwnerOut,
    SignupRequest,
    StaffOut,
    StatusUpdate,
    TodayBookingItem,
)

app = FastAPI(title="DogBuddy API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    # localhost and 127.0.0.1 are different origins from the browser's
    # perspective, so we whitelist both for dev. Also allow any localhost:*
    # port via regex in case Next.js picks a different port.
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    init_db()
    # Pre-open the async checkpointer so the first /chat request doesn't pay
    # the connection cost.
    from agent.graph import init_checkpointer

    await init_checkpointer()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    from agent.graph import close_checkpointer

    await close_checkpointer()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@app.post(
    "/auth/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED
)
def signup(body: SignupRequest, db: Session = Depends(get_db)) -> AuthResponse:
    """Self-service signup ALWAYS creates an owner. Staff are seeded; we
    never expose staff signup through the UI."""
    existing = db.query(Staff).filter(Staff.phone == body.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="Phone already registered")

    user = Staff(
        name=body.name,
        phone=body.phone,
        password_hash=hash_password(body.password),
        role="owner",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return AuthResponse(token=token, staff=StaffOut.model_validate(user))


@app.post("/auth/login", response_model=AuthResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.query(Staff).filter(Staff.phone == body.phone).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid phone or password")

    token = create_access_token(user.id)
    return AuthResponse(token=token, staff=StaffOut.model_validate(user))


@app.get("/auth/me", response_model=StaffOut)
def me(current: Staff = Depends(get_current_user)) -> StaffOut:
    return StaffOut.model_validate(current)


# ---------------------------------------------------------------------------
# Dogs
# ---------------------------------------------------------------------------


@app.get("/dogs", response_model=list[DogOut])
def list_dogs(
    db: Session = Depends(get_db),
    _: Staff = Depends(get_current_staff),
) -> list[DogOut]:
    rows = db.scalars(select(Dog).order_by(Dog.name)).all()
    return [DogOut.model_validate(d) for d in rows]


# Specific routes (/dogs/mine) MUST be declared before parameterised routes
# (/dogs/{dog_id}) or FastAPI will try to parse "mine" as an int and 422.


@app.get("/dogs/mine", response_model=list[DogOut])
def list_my_dogs(
    db: Session = Depends(get_db),
    current: Staff = Depends(require_role("owner")),
) -> list[DogOut]:
    rows = (
        db.query(Dog)
        .filter(Dog.owner_user_id == current.id)
        .order_by(Dog.name)
        .all()
    )
    return [DogOut.model_validate(d) for d in rows]


@app.post("/dogs", response_model=DogOut, status_code=status.HTTP_201_CREATED)
def register_dog(
    body: CreateDogRequest,
    db: Session = Depends(get_db),
    current: Staff = Depends(require_role("owner")),
) -> DogOut:
    """Owner registers their own dog. owner_name/phone are pulled from
    the logged-in user; owner_user_id links the dog to that account."""
    dog = Dog(
        name=body.name,
        breed=body.breed,
        age_years=body.age_years,
        weight_kg=body.weight_kg,
        diet=body.diet,
        medications=body.medications,
        allergies=body.allergies,
        vaccination_status=body.vaccination_status,
        vaccination_expires=body.vaccination_expires,
        owner_name=current.name,
        owner_phone=current.phone,
        owner_user_id=current.id,
        vet_contact=body.vet_contact,
        notes=body.notes,
    )
    db.add(dog)
    db.commit()
    db.refresh(dog)

    write_audit(
        db,
        staff_id=current.id,
        action="register_dog",
        target_type="dog",
        target_id=dog.id,
        details={"name": dog.name, "breed": dog.breed, "via": "owner"},
    )
    db.commit()
    return DogOut.model_validate(dog)


@app.get("/dogs/{dog_id}", response_model=DogDetailOut)
def get_dog(
    dog_id: int,
    db: Session = Depends(get_db),
    current: Staff = Depends(get_current_user),
) -> DogDetailOut:
    """Staff sees any dog; owner sees their own (404 otherwise so we don't
    leak which IDs exist)."""
    dog = db.get(Dog, dog_id)
    if dog is None:
        raise HTTPException(status_code=404, detail="Dog not found")
    if current.role == "owner" and dog.owner_user_id != current.id:
        raise HTTPException(status_code=404, detail="Dog not found")

    booking = (
        db.query(Booking)
        .filter(Booking.dog_id == dog_id)
        .order_by(Booking.start_date.desc(), Booking.id.desc())
        .first()
    )
    recent = (
        db.query(Incident)
        .filter(Incident.dog_id == dog_id)
        .order_by(Incident.created_at.desc())
        .limit(5)
        .all()
    )

    return DogDetailOut(
        **DogOut.model_validate(dog).model_dump(),
        current_booking=BookingOut.model_validate(booking) if booking else None,
        recent_incidents=[IncidentOut.model_validate(i) for i in recent],
    )


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------

# Bucket mapping for the dashboard. The seed data is built to fall into
# exactly these three groups when seed.py is run on the same day.
_CHECKING_IN_STATUSES = {"scheduled"}
_IN_CARE_STATUSES = {"checked_in", "in_care"}
_CHECKING_OUT_STATUSES = {"checked_out"}


def _to_today_item(b: Booking) -> TodayBookingItem:
    return TodayBookingItem(
        booking_id=b.id,
        dog=DogOut.model_validate(b.dog),
        kennel_id=b.kennel_id,
        status=b.status,
        last_walked_at=b.last_walked_at,
        last_fed_at=b.last_fed_at,
        last_meds_at=b.last_meds_at,
    )


@app.get("/bookings/today", response_model=BookingsTodayOut)
def bookings_today(
    db: Session = Depends(get_db),
    _: Staff = Depends(get_current_staff),
) -> BookingsTodayOut:
    today = date.today()
    # An "active today" booking has today within [start_date, end_date]
    # OR is in the checked_out bucket and ended today.
    rows = (
        db.query(Booking)
        .filter(Booking.start_date <= today, Booking.end_date >= today)
        .all()
    )

    checking_in: list[TodayBookingItem] = []
    in_care: list[TodayBookingItem] = []
    checking_out: list[TodayBookingItem] = []

    for b in rows:
        item = _to_today_item(b)
        if b.status in _CHECKING_IN_STATUSES:
            checking_in.append(item)
        elif b.status in _IN_CARE_STATUSES:
            in_care.append(item)
        elif b.status in _CHECKING_OUT_STATUSES:
            checking_out.append(item)

    return BookingsTodayOut(
        checking_in=checking_in,
        in_care=in_care,
        checking_out=checking_out,
    )


_ALLOWED_STATUSES = {"checked_in", "in_care", "checked_out"}


@app.patch("/bookings/{booking_id}/status", response_model=BookingOut)
def update_booking_status(
    booking_id: int,
    body: StatusUpdate,
    db: Session = Depends(get_db),
    current: Staff = Depends(get_current_staff),
) -> BookingOut:
    if body.status not in _ALLOWED_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status: {body.status}")

    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    before = booking.status
    booking.status = body.status

    write_audit(
        db,
        staff_id=current.id,
        action="update_status",
        target_type="booking",
        target_id=booking.id,
        details={"before": before, "after": body.status, "dog_id": booking.dog_id},
    )
    db.commit()
    db.refresh(booking)
    return BookingOut.model_validate(booking)


_ACTIVITY_FIELD = {
    "walk": "last_walked_at",
    "feed": "last_fed_at",
    "meds": "last_meds_at",
}


@app.patch("/bookings/{booking_id}/activity", response_model=BookingOut)
def update_booking_activity(
    booking_id: int,
    body: ActivityUpdate,
    db: Session = Depends(get_db),
    current: Staff = Depends(get_current_staff),
) -> BookingOut:
    field = _ACTIVITY_FIELD.get(body.activity)
    if field is None:
        raise HTTPException(
            status_code=422, detail=f"Invalid activity: {body.activity}"
        )

    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    now = datetime.now()
    setattr(booking, field, now)

    write_audit(
        db,
        staff_id=current.id,
        action="update_activity",
        target_type="booking",
        target_id=booking.id,
        details={
            "activity": body.activity,
            "at": now.isoformat(),
            "dog_id": booking.dog_id,
        },
    )
    db.commit()
    db.refresh(booking)
    return BookingOut.model_validate(booking)


# ---------------------------------------------------------------------------
# Owner-mode: create-booking + my-bookings
# ---------------------------------------------------------------------------


@app.post("/bookings", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create_booking(
    body: CreateBookingRequest,
    db: Session = Depends(get_db),
    current: Staff = Depends(require_role("owner")),
) -> BookingOut:
    """Owner books a stay for one of THEIR dogs. Initial status='scheduled'.
    Staff can flip it to checked_in/in_care/checked_out via PATCH later."""
    if body.end_date < body.start_date:
        raise HTTPException(status_code=422, detail="end_date must be >= start_date")

    dog = db.get(Dog, body.dog_id)
    if dog is None:
        raise HTTPException(status_code=404, detail="Dog not found")
    if dog.owner_user_id != current.id:
        raise HTTPException(
            status_code=403, detail="You can only book stays for your own dogs"
        )

    booking = Booking(
        dog_id=dog.id,
        start_date=body.start_date,
        end_date=body.end_date,
        status="scheduled",
        kennel_id=body.kennel_id,
    )
    db.add(booking)
    db.flush()

    write_audit(
        db,
        staff_id=current.id,
        action="create_booking",
        target_type="booking",
        target_id=booking.id,
        details={
            "dog_id": dog.id,
            "start_date": body.start_date.isoformat(),
            "end_date": body.end_date.isoformat(),
            "via": "owner",
        },
    )
    db.commit()
    db.refresh(booking)
    return BookingOut.model_validate(booking)


@app.get("/bookings/mine", response_model=list[BookingOut])
def list_my_bookings(
    db: Session = Depends(get_db),
    current: Staff = Depends(require_role("owner")),
) -> list[BookingOut]:
    rows = (
        db.query(Booking)
        .join(Dog, Booking.dog_id == Dog.id)
        .filter(Dog.owner_user_id == current.id)
        .order_by(Booking.start_date.desc())
        .all()
    )
    return [BookingOut.model_validate(b) for b in rows]


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------

_VALID_INCIDENT_TYPES = {"health", "behavior", "feeding", "other"}
_VALID_SEVERITIES = {"mild", "moderate", "severe"}


@app.post("/incidents", response_model=IncidentOut, status_code=status.HTTP_201_CREATED)
def create_incident(
    body: IncidentIn,
    db: Session = Depends(get_db),
    current: Staff = Depends(get_current_staff),
) -> IncidentOut:
    if body.type not in _VALID_INCIDENT_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid type: {body.type}")
    if body.severity not in _VALID_SEVERITIES:
        raise HTTPException(
            status_code=422, detail=f"Invalid severity: {body.severity}"
        )

    dog = db.get(Dog, body.dog_id)
    if dog is None:
        raise HTTPException(status_code=404, detail="Dog not found")

    incident = Incident(
        dog_id=body.dog_id,
        staff_id=current.id,
        type=body.type,
        severity=body.severity,
        description=body.description,
    )
    db.add(incident)
    db.flush()

    write_audit(
        db,
        staff_id=current.id,
        action="log_incident",
        target_type="incident",
        target_id=incident.id,
        details={
            "dog_id": body.dog_id,
            "type": body.type,
            "severity": body.severity,
            "description": body.description,
        },
    )
    db.commit()
    db.refresh(incident)
    return IncidentOut.model_validate(incident)


@app.get("/incidents/recent", response_model=list[IncidentOut])
def recent_incidents(
    db: Session = Depends(get_db),
    _: Staff = Depends(get_current_staff),
) -> list[IncidentOut]:
    rows = db.query(Incident).order_by(Incident.created_at.desc()).limit(20).all()
    return [IncidentOut.model_validate(i) for i in rows]


# ---------------------------------------------------------------------------
# Owners (staff directory of customer accounts)
# ---------------------------------------------------------------------------


@app.get("/owners", response_model=list[OwnerOut])
def list_owners(
    db: Session = Depends(get_db),
    _: Staff = Depends(get_current_staff),
) -> list[OwnerOut]:
    """Staff-only directory of owner accounts with their dog count."""
    rows = (
        db.query(Staff)
        .filter(Staff.role == "owner")
        .order_by(Staff.created_at.desc())
        .all()
    )
    out: list[OwnerOut] = []
    for u in rows:
        n = db.query(Dog).filter(Dog.owner_user_id == u.id).count()
        out.append(
            OwnerOut(
                id=u.id,
                name=u.name,
                phone=u.phone,
                created_at=u.created_at,
                dog_count=n,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Audit log (notifications feed)
# ---------------------------------------------------------------------------


@app.get("/audit_log/recent", response_model=list[AuditLogOut])
def recent_audit_log(
    limit: int = 20,
    db: Session = Depends(get_db),
    current: Staff = Depends(get_current_user),
) -> list[AuditLogOut]:
    """Recent activity feed. Staff sees everything; owners see only their
    own actions + actions taken on their dogs/bookings (so they get
    notified when staff check in their dog, walk it, etc.)."""
    q = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(max(1, min(limit, 100)))

    if current.role == "owner":
        # Owners only see audit rows linked to them or their dogs/bookings.
        my_dog_ids = [
            row[0]
            for row in db.query(Dog.id).filter(Dog.owner_user_id == current.id).all()
        ]
        my_booking_ids = [
            row[0]
            for row in db.query(Booking.id)
            .join(Dog, Booking.dog_id == Dog.id)
            .filter(Dog.owner_user_id == current.id)
            .all()
        ]
        rows = q.all()
        rows = [
            r
            for r in rows
            if r.staff_id == current.id
            or (r.target_type == "dog" and r.target_id in my_dog_ids)
            or (r.target_type == "booking" and r.target_id in my_booking_ids)
        ]
    else:
        rows = q.all()

    # Inline the actor's name for display.
    staff_names = {
        u.id: u.name
        for u in db.query(Staff).filter(Staff.id.in_([r.staff_id for r in rows])).all()
    }
    return [
        AuditLogOut(
            id=r.id,
            staff_id=r.staff_id,
            staff_name=staff_names.get(r.staff_id),
            action=r.action,
            target_type=r.target_type,
            target_id=r.target_id,
            details=r.details,
            created_at=r.created_at,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Chat (SSE)
# ---------------------------------------------------------------------------


@app.post("/chat")
async def chat(
    body: ChatRequest,
    current: Staff = Depends(get_current_user),
):
    # Import lazily so the auth path doesn't pay for langchain import at startup.
    from agent.graph import astream_chat

    staff_id = current.id
    staff_name = current.name
    role = current.role

    async def event_stream():
        async for ev in astream_chat(
            message=body.message,
            thread_id=body.thread_id,
            staff_name=staff_name,
            staff_id=staff_id,
            role=role,
        ):
            ev_type = ev.get("type", "message")
            payload = {k: v for k, v in ev.items() if k != "type"}
            yield {"event": ev_type, "data": json.dumps(payload)}

    return EventSourceResponse(event_stream())
