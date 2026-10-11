"""FastAPI application entrypoint."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, datetime

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

from audit import write_audit
from auth import (
    Principal,
    clear_session_cookie,
    consume_code,
    create_access_token,
    get_current_staff,
    get_current_user,
    hash_password,
    issue_code,
    require_role,
    set_session_cookie,
    verify_password,
)
from booking_service import (
    BookingError,
    assign_kennel,
    cancel_booking,
    check_in,
    check_out,
    create_request,
    decide,
    log_care,
    refresh_vaccination_status,
)
from db import (
    AuditLog,
    Booking,
    Dog,
    Facility,
    Incident,
    Kennel,
    Membership,
    User,
    VaccinationRecord,
    get_db,
    init_db,
)
from schemas import (
    AcceptInviteRequest,
    ActivityUpdate,
    AuditLogOut,
    AuthResponse,
    BookingOut,
    BookingsTodayOut,
    ChatRequest,
    CreateBookingRequest,
    CreateDogRequest,
    DecisionIn,
    DogDetailOut,
    DogOut,
    FacilityChoice,
    IncidentIn,
    IncidentOut,
    InviteRequest,
    InviteResponse,
    KennelIn,
    KennelOut,
    KennelPatch,
    LoginRequest,
    OwnerOut,
    QueueItem,
    PasswordResetConfirm,
    PasswordResetRequest,
    SessionUser,
    SignupRequest,
    StatusUpdate,
    TodayBookingItem,
    VaccinationIn,
    VaccinationOut,
)


def _http(err: BookingError) -> HTTPException:
    return HTTPException(status_code=err.status_code, detail=err.detail)

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

app = FastAPI(title="DogBuddy API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
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
    if os.getenv("DOGBUDDY_SKIP_AGENT") == "1":
        return
    from agent.graph import init_checkpointer

    await init_checkpointer()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    if os.getenv("DOGBUDDY_SKIP_AGENT") == "1":
        return
    from agent.graph import close_checkpointer

    await close_checkpointer()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _session_user(principal: Principal) -> SessionUser:
    return SessionUser(
        id=principal.id,
        name=principal.name,
        phone=principal.phone,
        email=principal.user.email,
        role=principal.role,
        facility_id=principal.facility_id,
        facility_name=principal.facility.name,
        facility_slug=principal.facility.slug,
    )


def _establish_session(
    response: Response, user: User, membership: Membership, facility: Facility
) -> AuthResponse:
    token = create_access_token(user.id, facility.id, membership.role)
    set_session_cookie(response, token)
    return AuthResponse(
        user=_session_user(Principal(user=user, membership=membership, facility=facility))
    )


def _facility_by_slug(db: Session, slug: str) -> Facility:
    facility = db.query(Facility).filter(Facility.slug == slug).one_or_none()
    if facility is None:
        raise HTTPException(status_code=404, detail="Facility not found")
    return facility


def _dog_in_facility(db: Session, dog_id: int, facility_id: int) -> Dog:
    dog = db.get(Dog, dog_id)
    if dog is None or dog.facility_id != facility_id:
        raise HTTPException(status_code=404, detail="Dog not found")
    return dog


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@app.post(
    "/auth/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED
)
def signup(
    body: SignupRequest, response: Response, db: Session = Depends(get_db)
) -> AuthResponse:
    """Parent self-signup is always scoped to one facility slug."""
    slug = body.facility_slug.strip().lower()
    if not SLUG_RE.match(slug):
        raise HTTPException(status_code=422, detail="Invalid facility slug")
    facility = _facility_by_slug(db, slug)
    phone = body.phone.strip()
    user = db.query(User).filter(User.phone == phone).one_or_none()
    if user is None:
        user = User(
            name=body.name.strip(),
            phone=phone,
            password_hash=hash_password(body.password),
        )
        db.add(user)
        db.flush()
    elif not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Phone already registered")

    membership = (
        db.query(Membership)
        .filter(Membership.user_id == user.id, Membership.facility_id == facility.id)
        .one_or_none()
    )
    if membership is not None:
        raise HTTPException(status_code=400, detail="Already a member of this facility")
    membership = Membership(user_id=user.id, facility_id=facility.id, role="parent")
    db.add(membership)
    db.commit()
    db.refresh(user)
    return _establish_session(response, user, membership, facility)


@app.post("/auth/login", response_model=AuthResponse)
def login(
    body: LoginRequest, response: Response, db: Session = Depends(get_db)
) -> AuthResponse:
    user = db.query(User).filter(User.phone == body.phone.strip()).one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid phone or password")

    memberships = (
        db.query(Membership).filter(Membership.user_id == user.id).all()
    )
    if not memberships:
        raise HTTPException(status_code=403, detail="No facility membership")

    chosen: Membership | None = None
    if body.facility_slug:
        facility = _facility_by_slug(db, body.facility_slug.strip().lower())
        chosen = next(
            (m for m in memberships if m.facility_id == facility.id), None
        )
        if chosen is None:
            raise HTTPException(status_code=403, detail="No facility membership")
    elif len(memberships) == 1:
        chosen = memberships[0]
    else:
        choices = []
        for m in memberships:
            facility = db.get(Facility, m.facility_id)
            if facility is None:
                continue
            choices.append(
                FacilityChoice(
                    facility_id=facility.id,
                    facility_name=facility.name,
                    facility_slug=facility.slug,
                    role=m.role,
                )
            )
        return AuthResponse(needs_facility=True, memberships=choices)

    facility = db.get(Facility, chosen.facility_id)
    if facility is None:
        raise HTTPException(status_code=403, detail="No facility membership")
    return _establish_session(response, user, chosen, facility)


@app.post("/auth/logout")
def logout(response: Response) -> dict:
    clear_session_cookie(response)
    return {"ok": True}


@app.get("/auth/me", response_model=SessionUser)
def me(current: Principal = Depends(get_current_user)) -> SessionUser:
    return _session_user(current)


@app.post("/auth/password-reset/request", response_model=AuthResponse)
def request_password_reset(
    body: PasswordResetRequest, db: Session = Depends(get_db)
) -> AuthResponse:
    """Always 200 so the endpoint does not reveal which phones exist."""
    phone = body.phone.strip()
    user = db.query(User).filter(User.phone == phone).one_or_none()
    debug_code = None
    if user is not None:
        code = issue_code(db, phone=phone, purpose="password_reset")
        db.commit()
        if os.getenv("DOGBUDDY_DEBUG_OTP") == "1":
            debug_code = code
    return AuthResponse(debug_code=debug_code)


@app.post("/auth/password-reset/confirm")
def confirm_password_reset(
    body: PasswordResetConfirm, db: Session = Depends(get_db)
) -> dict:
    row = consume_code(
        db, phone=body.phone.strip(), purpose="password_reset", code=body.code.strip()
    )
    if row is None:
        raise HTTPException(status_code=400, detail="Invalid or expired code")
    user = db.query(User).filter(User.phone == body.phone.strip()).one_or_none()
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid or expired code")
    user.password_hash = hash_password(body.password)
    db.commit()
    return {"ok": True}


@app.post("/team/invites", response_model=InviteResponse, status_code=201)
def invite_staff(
    body: InviteRequest,
    db: Session = Depends(get_db),
    current: Principal = Depends(require_role("admin")),
) -> InviteResponse:
    if body.role not in ("admin", "attendant"):
        raise HTTPException(status_code=422, detail="Role must be admin or attendant")
    phone = body.phone.strip()
    user = db.query(User).filter(User.phone == phone).one_or_none()
    if user is None:
        user = User(
            name=body.name.strip(),
            phone=phone,
            password_hash=hash_password(os.urandom(16).hex()),
        )
        db.add(user)
        db.flush()
    existing = (
        db.query(Membership)
        .filter(
            Membership.user_id == user.id,
            Membership.facility_id == current.facility_id,
        )
        .one_or_none()
    )
    if existing is not None:
        raise HTTPException(status_code=400, detail="Already a member of this facility")
    code = issue_code(
        db,
        phone=phone,
        purpose="invite",
        facility_id=current.facility_id,
        role=body.role,
        minutes=60 * 24,
    )
    db.commit()
    return InviteResponse(
        phone=phone,
        role=body.role,
        facility_slug=current.facility.slug,
        code=code,
    )


@app.post("/auth/accept-invite", response_model=AuthResponse)
def accept_invite(
    body: AcceptInviteRequest, response: Response, db: Session = Depends(get_db)
) -> AuthResponse:
    facility = _facility_by_slug(db, body.facility_slug.strip().lower())
    row = consume_code(
        db, phone=body.phone.strip(), purpose="invite", code=body.code.strip()
    )
    if row is None or row.facility_id != facility.id or row.role not in (
        "admin",
        "attendant",
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired code")
    user = db.query(User).filter(User.phone == body.phone.strip()).one_or_none()
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid or expired code")
    user.password_hash = hash_password(body.password)
    membership = Membership(
        user_id=user.id, facility_id=facility.id, role=row.role or "attendant"
    )
    db.add(membership)
    db.commit()
    db.refresh(user)
    return _establish_session(response, user, membership, facility)


# ---------------------------------------------------------------------------
# Dogs
# ---------------------------------------------------------------------------


@app.get("/dogs", response_model=list[DogOut])
def list_dogs(
    db: Session = Depends(get_db),
    current: Principal = Depends(get_current_staff),
) -> list[DogOut]:
    rows = db.scalars(
        select(Dog)
        .where(Dog.facility_id == current.facility_id)
        .order_by(Dog.name)
    ).all()
    return [DogOut.model_validate(d) for d in rows]


@app.get("/dogs/mine", response_model=list[DogOut])
def list_my_dogs(
    db: Session = Depends(get_db),
    current: Principal = Depends(require_role("parent")),
) -> list[DogOut]:
    rows = (
        db.query(Dog)
        .filter(
            Dog.owner_user_id == current.id,
            Dog.facility_id == current.facility_id,
        )
        .order_by(Dog.name)
        .all()
    )
    return [DogOut.model_validate(d) for d in rows]


@app.post("/dogs", response_model=DogOut, status_code=status.HTTP_201_CREATED)
def register_dog(
    body: CreateDogRequest,
    db: Session = Depends(get_db),
    current: Principal = Depends(require_role("parent")),
) -> DogOut:
    dog = Dog(
        facility_id=current.facility_id,
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
    db.flush()
    if body.vaccination_expires is not None:
        db.add(
            VaccinationRecord(
                facility_id=current.facility_id,
                dog_id=dog.id,
                vaccine_type="core",
                expires_on=body.vaccination_expires,
            )
        )
        db.flush()
        refresh_vaccination_status(db, dog)
    write_audit(
        db,
        facility_id=current.facility_id,
        staff_id=current.id,
        action="register_dog",
        target_type="dog",
        target_id=dog.id,
        details={"name": dog.name, "breed": dog.breed, "via": "parent"},
    )
    db.commit()
    db.refresh(dog)
    return DogOut.model_validate(dog)


@app.get("/dogs/{dog_id}", response_model=DogDetailOut)
def get_dog(
    dog_id: int,
    db: Session = Depends(get_db),
    current: Principal = Depends(get_current_user),
) -> DogDetailOut:
    dog = _dog_in_facility(db, dog_id, current.facility_id)
    if current.role == "parent" and dog.owner_user_id != current.id:
        raise HTTPException(status_code=404, detail="Dog not found")

    booking = (
        db.query(Booking)
        .filter(
            Booking.dog_id == dog_id,
            Booking.facility_id == current.facility_id,
        )
        .order_by(Booking.start_date.desc(), Booking.id.desc())
        .first()
    )
    recent = (
        db.query(Incident)
        .filter(
            Incident.dog_id == dog_id,
            Incident.facility_id == current.facility_id,
        )
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
    current: Principal = Depends(get_current_staff),
) -> BookingsTodayOut:
    today = date.today()
    rows = (
        db.query(Booking)
        .filter(
            Booking.facility_id == current.facility_id,
            Booking.start_date <= today,
            Booking.end_date >= today,
        )
        .all()
    )
    checking_in: list[TodayBookingItem] = []
    in_care: list[TodayBookingItem] = []
    checking_out: list[TodayBookingItem] = []
    for b in rows:
        item = _to_today_item(b)
        if b.status in ("confirmed", "scheduled"):
            checking_in.append(item)
        elif b.status in ("checked_in", "in_care") and b.end_date == today:
            checking_out.append(item)
        elif b.status in ("checked_in", "in_care"):
            in_care.append(item)
        elif b.status == "checked_out" and b.end_date == today:
            checking_out.append(item)
    return BookingsTodayOut(
        checking_in=checking_in,
        in_care=in_care,
        checking_out=checking_out,
    )


def _booking_in_facility(db: Session, booking_id: int, facility_id: int) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None or booking.facility_id != facility_id:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@app.patch("/bookings/{booking_id}/status", response_model=BookingOut)
def update_booking_status(
    booking_id: int,
    body: StatusUpdate,
    db: Session = Depends(get_db),
    current: Principal = Depends(get_current_staff),
) -> BookingOut:
    booking = _booking_in_facility(db, booking_id, current.facility_id)
    try:
        if body.status == "checked_in":
            check_in(
                db,
                facility=current.facility,
                booking=booking,
                actor_id=current.id,
                belongings=body.belongings,
                diet_confirmed=body.diet_confirmed,
                meds_confirmed=body.meds_confirmed,
                vet_confirmed=body.vet_confirmed,
                kennel_id=body.kennel_id,
            )
        elif body.status == "checked_out":
            check_out(
                db,
                facility=current.facility,
                booking=booking,
                actor_id=current.id,
                actor_role=current.role,
                acknowledge_severe=body.acknowledge_severe,
            )
        else:
            raise HTTPException(status_code=422, detail=f"Invalid status: {body.status}")
    except BookingError as err:
        raise _http(err) from err
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
    current: Principal = Depends(get_current_staff),
) -> BookingOut:
    field = _ACTIVITY_FIELD.get(body.activity)
    if field is None:
        raise HTTPException(
            status_code=422, detail=f"Invalid activity: {body.activity}"
        )
    booking = _booking_in_facility(db, booking_id, current.facility_id)
    kind = {"walk": "walk", "feed": "feed", "meds": "meds"}.get(body.activity)
    if kind is None:
        raise HTTPException(status_code=422, detail=f"Invalid activity: {body.activity}")
    try:
        log_care(
            db,
            facility_id=current.facility_id,
            booking=booking,
            actor_id=current.id,
            kind=kind,
        )
    except BookingError as err:
        raise _http(err) from err
    db.commit()
    db.refresh(booking)
    return BookingOut.model_validate(booking)


@app.post("/bookings", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create_booking(
    body: CreateBookingRequest,
    db: Session = Depends(get_db),
    current: Principal = Depends(require_role("parent")),
) -> BookingOut:
    dog = _dog_in_facility(db, body.dog_id, current.facility_id)
    if dog.owner_user_id != current.id:
        raise HTTPException(
            status_code=403, detail="You can only book stays for your own dogs"
        )
    try:
        booking = create_request(
            db,
            facility=current.facility,
            dog=dog,
            start=body.start_date,
            end=body.end_date,
            actor_id=current.id,
            actor_role="parent",
            waiver_accepted=body.waiver_accepted,
        )
    except BookingError as err:
        raise _http(err) from err
    db.commit()
    db.refresh(booking)
    return BookingOut.model_validate(booking)


@app.get("/bookings/queue", response_model=list[QueueItem])
def booking_queue(
    db: Session = Depends(get_db),
    current: Principal = Depends(get_current_staff),
) -> list[QueueItem]:
    rows = (
        db.query(Booking)
        .filter(
            Booking.facility_id == current.facility_id,
            Booking.status.in_(("requested", "waitlisted", "awaiting_payment")),
        )
        .order_by(Booking.start_date)
        .all()
    )
    return [
        QueueItem(
            booking=BookingOut.model_validate(b),
            dog_name=b.dog.name,
            owner_name=b.dog.owner_name,
        )
        for b in rows
    ]


@app.post("/bookings/{booking_id}/decision", response_model=BookingOut)
def booking_decision(
    booking_id: int,
    body: DecisionIn,
    db: Session = Depends(get_db),
    current: Principal = Depends(get_current_staff),
) -> BookingOut:
    booking = _booking_in_facility(db, booking_id, current.facility_id)
    try:
        decide(
            db,
            facility=current.facility,
            booking=booking,
            action=body.action,
            actor_id=current.id,
        )
    except BookingError as err:
        raise _http(err) from err
    db.commit()
    db.refresh(booking)
    return BookingOut.model_validate(booking)


@app.post("/bookings/{booking_id}/cancel", response_model=BookingOut)
def booking_cancel(
    booking_id: int,
    db: Session = Depends(get_db),
    current: Principal = Depends(get_current_user),
) -> BookingOut:
    booking = _booking_in_facility(db, booking_id, current.facility_id)
    if current.role == "parent" and booking.dog.owner_user_id != current.id:
        raise HTTPException(status_code=404, detail="Booking not found")
    try:
        cancel_booking(
            db,
            facility=current.facility,
            booking=booking,
            actor_id=current.id,
            actor_role=current.role,
        )
    except BookingError as err:
        raise _http(err) from err
    db.commit()
    db.refresh(booking)
    return BookingOut.model_validate(booking)


@app.post("/bookings/{booking_id}/kennel", response_model=BookingOut)
def booking_assign_kennel(
    booking_id: int,
    kennel_id: int,
    db: Session = Depends(get_db),
    current: Principal = Depends(get_current_staff),
) -> BookingOut:
    booking = _booking_in_facility(db, booking_id, current.facility_id)
    try:
        assign_kennel(
            db,
            facility=current.facility,
            booking=booking,
            kennel_id=kennel_id,
            actor_id=current.id,
        )
    except BookingError as err:
        raise _http(err) from err
    db.commit()
    db.refresh(booking)
    return BookingOut.model_validate(booking)


@app.get("/bookings/mine", response_model=list[BookingOut])
def list_my_bookings(
    db: Session = Depends(get_db),
    current: Principal = Depends(require_role("parent")),
) -> list[BookingOut]:
    rows = (
        db.query(Booking)
        .join(Dog, Booking.dog_id == Dog.id)
        .filter(
            Dog.owner_user_id == current.id,
            Booking.facility_id == current.facility_id,
        )
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
    current: Principal = Depends(get_current_staff),
) -> IncidentOut:
    if body.type not in _VALID_INCIDENT_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid type: {body.type}")
    if body.severity not in _VALID_SEVERITIES:
        raise HTTPException(
            status_code=422, detail=f"Invalid severity: {body.severity}"
        )
    dog = _dog_in_facility(db, body.dog_id, current.facility_id)
    incident = Incident(
        facility_id=current.facility_id,
        dog_id=dog.id,
        staff_id=current.id,
        type=body.type,
        severity=body.severity,
        description=body.description,
        parent_visible=body.parent_visible or body.severity == "severe",
    )
    db.add(incident)
    db.flush()
    write_audit(
        db,
        facility_id=current.facility_id,
        staff_id=current.id,
        action="log_incident",
        target_type="incident",
        target_id=incident.id,
        details={
            "dog_id": dog.id,
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
    current: Principal = Depends(get_current_staff),
) -> list[IncidentOut]:
    rows = (
        db.query(Incident)
        .filter(Incident.facility_id == current.facility_id)
        .order_by(Incident.created_at.desc())
        .limit(20)
        .all()
    )
    return [IncidentOut.model_validate(i) for i in rows]


@app.get("/owners", response_model=list[OwnerOut])
def list_owners(
    db: Session = Depends(get_db),
    current: Principal = Depends(get_current_staff),
) -> list[OwnerOut]:
    rows = (
        db.query(User)
        .join(Membership, Membership.user_id == User.id)
        .filter(
            Membership.facility_id == current.facility_id,
            Membership.role == "parent",
        )
        .order_by(User.created_at.desc())
        .all()
    )
    out: list[OwnerOut] = []
    for u in rows:
        n = (
            db.query(Dog)
            .filter(
                Dog.owner_user_id == u.id,
                Dog.facility_id == current.facility_id,
            )
            .count()
        )
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


@app.get("/audit_log/recent", response_model=list[AuditLogOut])
def recent_audit_log(
    limit: int = 20,
    db: Session = Depends(get_db),
    current: Principal = Depends(get_current_user),
) -> list[AuditLogOut]:
    q = (
        db.query(AuditLog)
        .filter(AuditLog.facility_id == current.facility_id)
        .order_by(AuditLog.id.desc())
        .limit(max(1, min(limit, 100)))
    )
    rows = q.all()
    if current.role == "parent":
        my_dog_ids = [
            row[0]
            for row in db.query(Dog.id)
            .filter(
                Dog.owner_user_id == current.id,
                Dog.facility_id == current.facility_id,
            )
            .all()
        ]
        my_booking_ids = [
            row[0]
            for row in db.query(Booking.id)
            .join(Dog, Booking.dog_id == Dog.id)
            .filter(
                Dog.owner_user_id == current.id,
                Booking.facility_id == current.facility_id,
            )
            .all()
        ]
        rows = [
            r
            for r in rows
            if r.staff_id == current.id
            or (r.target_type == "dog" and r.target_id in my_dog_ids)
            or (r.target_type == "booking" and r.target_id in my_booking_ids)
        ]
    staff_names = {
        u.id: u.name
        for u in db.query(User).filter(User.id.in_([r.staff_id for r in rows] or [-1])).all()
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


_KENNEL_STATUSES = {"available", "occupied", "reserved", "cleaning", "maintenance"}


@app.get("/kennels", response_model=list[KennelOut])
def list_kennels(
    db: Session = Depends(get_db),
    current: Principal = Depends(get_current_staff),
) -> list[KennelOut]:
    rows = (
        db.query(Kennel)
        .filter(Kennel.facility_id == current.facility_id)
        .order_by(Kennel.name)
        .all()
    )
    return [KennelOut.model_validate(k) for k in rows]


@app.post("/kennels", response_model=KennelOut, status_code=201)
def create_kennel(
    body: KennelIn,
    db: Session = Depends(get_db),
    current: Principal = Depends(require_role("admin")),
) -> KennelOut:
    if body.status not in _KENNEL_STATUSES:
        raise HTTPException(status_code=422, detail="Invalid kennel status")
    kennel = Kennel(
        facility_id=current.facility_id, name=body.name.strip(), status=body.status
    )
    db.add(kennel)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Kennel name already exists")
    db.refresh(kennel)
    return KennelOut.model_validate(kennel)


@app.patch("/kennels/{kennel_id}", response_model=KennelOut)
def patch_kennel(
    kennel_id: int,
    body: KennelPatch,
    db: Session = Depends(get_db),
    current: Principal = Depends(get_current_staff),
) -> KennelOut:
    if body.status not in _KENNEL_STATUSES:
        raise HTTPException(status_code=422, detail="Invalid kennel status")
    kennel = db.get(Kennel, kennel_id)
    if kennel is None or kennel.facility_id != current.facility_id:
        raise HTTPException(status_code=404, detail="Kennel not found")
    kennel.status = body.status
    db.commit()
    db.refresh(kennel)
    return KennelOut.model_validate(kennel)


@app.post(
    "/dogs/{dog_id}/vaccinations",
    response_model=VaccinationOut,
    status_code=201,
)
def add_vaccination(
    dog_id: int,
    body: VaccinationIn,
    db: Session = Depends(get_db),
    current: Principal = Depends(get_current_user),
) -> VaccinationOut:
    dog = _dog_in_facility(db, dog_id, current.facility_id)
    if current.role == "parent" and dog.owner_user_id != current.id:
        raise HTTPException(status_code=404, detail="Dog not found")
    if current.role == "attendant":
        raise HTTPException(status_code=403, detail="Only an admin can edit vaccinations")
    row = VaccinationRecord(
        facility_id=current.facility_id,
        dog_id=dog.id,
        vaccine_type=body.vaccine_type.strip(),
        expires_on=body.expires_on,
    )
    db.add(row)
    db.flush()
    refresh_vaccination_status(db, dog)
    write_audit(
        db,
        facility_id=current.facility_id,
        staff_id=current.id,
        action="update_vaccination",
        target_type="dog",
        target_id=dog.id,
        details={"vaccine_type": row.vaccine_type, "expires_on": body.expires_on.isoformat()},
    )
    db.commit()
    db.refresh(row)
    return VaccinationOut.model_validate(row)


@app.post("/bookings/override", response_model=BookingOut, status_code=201)
def override_booking(
    body: CreateBookingRequest,
    db: Session = Depends(get_db),
    current: Principal = Depends(require_role("admin")),
) -> BookingOut:
    dog = _dog_in_facility(db, body.dog_id, current.facility_id)
    try:
        booking = create_request(
            db,
            facility=current.facility,
            dog=dog,
            start=body.start_date,
            end=body.end_date,
            actor_id=current.id,
            actor_role="admin",
            waiver_accepted=True,
            override=body.override,
            override_reason=body.override_reason,
        )
    except BookingError as err:
        raise _http(err) from err
    db.commit()
    db.refresh(booking)
    return BookingOut.model_validate(booking)


@app.post("/chat")
async def chat(
    body: ChatRequest,
    current: Principal = Depends(get_current_user),
):
    from agent.graph import astream_chat

    staff_id = current.id
    staff_name = current.name
    role = current.role
    facility_id = current.facility_id
    facility_name = current.facility.name

    async def event_stream():
        async for ev in astream_chat(
            message=body.message,
            thread_id=body.thread_id,
            staff_name=staff_name,
            staff_id=staff_id,
            role=role,
            facility_id=facility_id,
            facility_name=facility_name,
        ):
            ev_type = ev.get("type", "message")
            payload = {k: v for k, v in ev.items() if k != "type"}
            yield {"event": ev_type, "data": json.dumps(payload)}

    return EventSourceResponse(event_stream())
