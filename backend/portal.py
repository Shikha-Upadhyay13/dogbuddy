"""Settings, the notification inbox, report cards, and signed media."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from auth import Principal, get_current_staff, get_current_user, require_role
from db import (
    Booking,
    CareLog,
    FacilityAddon,
    Notification,
    NotificationPreference,
    ReportCard,
    User,
    get_db,
)
from notify import CATEGORIES, emit, ensure_preferences
from storage import resolve_token, save_bytes, signed_path

router = APIRouter()


def _booking(db: Session, booking_id: int, facility_id: int) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None or booking.facility_id != facility_id:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.get("/notifications")
def list_notifications(
    db: Session = Depends(get_db),
    current: Principal = Depends(get_current_user),
) -> list[dict]:
    rows = (
        db.query(Notification)
        .filter(
            Notification.facility_id == current.facility_id,
            Notification.recipient_user_id == current.id,
        )
        .order_by(Notification.id.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": row.id,
            "type": row.type,
            "title": row.title,
            "body": row.body,
            "link": row.link,
            "read_at": row.read_at.isoformat() if row.read_at else None,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.post("/notifications/{notification_id}/read")
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current: Principal = Depends(get_current_user),
) -> dict:
    row = db.get(Notification, notification_id)
    if (
        row is None
        or row.facility_id != current.facility_id
        or row.recipient_user_id != current.id
    ):
        raise HTTPException(status_code=404, detail="Notification not found")
    if row.read_at is None:
        row.read_at = datetime.now()
        db.commit()
    return {"ok": True}


@router.get("/settings/account")
def get_account(current: Principal = Depends(get_current_user)) -> dict:
    return {
        "name": current.name,
        "phone": current.phone,
        "email": current.user.email,
        "billing_state": None,
        "role": current.role,
        "facility_name": current.facility.name,
    }


@router.patch("/settings/account")
def patch_account(
    body: dict,
    db: Session = Depends(get_db),
    current: Principal = Depends(get_current_user),
) -> dict:
    user = db.get(User, current.id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if body.get("name"):
        user.name = str(body["name"]).strip()
    if "email" in body:
        user.email = (str(body["email"]).strip() or None) if body["email"] else None
    db.commit()
    return {"ok": True, "name": user.name, "email": user.email}


@router.get("/settings/notifications")
def get_notification_settings(
    db: Session = Depends(get_db),
    current: Principal = Depends(get_current_user),
) -> list[dict]:
    ensure_preferences(db, current.id, current.facility_id)
    db.commit()
    rows = (
        db.query(NotificationPreference)
        .filter(
            NotificationPreference.user_id == current.id,
            NotificationPreference.facility_id == current.facility_id,
        )
        .all()
    )
    return [
        {"category": row.category, "whatsapp": row.whatsapp, "email": row.email}
        for row in rows
        if row.category in CATEGORIES
    ]


@router.put("/settings/notifications")
def put_notification_settings(
    body: list[dict],
    db: Session = Depends(get_db),
    current: Principal = Depends(get_current_user),
) -> dict:
    ensure_preferences(db, current.id, current.facility_id)
    by_cat = {item.get("category"): item for item in body}
    rows = (
        db.query(NotificationPreference)
        .filter(
            NotificationPreference.user_id == current.id,
            NotificationPreference.facility_id == current.facility_id,
        )
        .all()
    )
    for row in rows:
        incoming = by_cat.get(row.category)
        if not incoming:
            continue
        row.whatsapp = bool(incoming.get("whatsapp"))
        row.email = bool(incoming.get("email"))
    db.commit()
    return {"ok": True}


@router.get("/settings/facility")
def get_facility(current: Principal = Depends(require_role("admin"))) -> dict:
    facility = current.facility
    return {
        "name": facility.name,
        "slug": facility.slug,
        "address": facility.address,
        "state": facility.state,
        "phone": facility.phone,
        "timezone": facility.timezone,
        "booking_mode": facility.booking_mode,
        "deposit_percent": facility.deposit_percent,
        "cancellation_window_hours": facility.cancellation_window_hours,
        "max_dogs": facility.max_dogs,
        "require_vaccination": facility.require_vaccination,
        "waiver_text": facility.waiver_text,
        "nightly_rate_paise": facility.nightly_rate_paise,
        "whatsapp_enabled": facility.whatsapp_enabled,
        "email_enabled": facility.email_enabled,
    }


@router.patch("/settings/facility")
def patch_facility(
    body: dict,
    db: Session = Depends(get_db),
    current: Principal = Depends(require_role("admin")),
) -> dict:
    facility = current.facility
    fields = [
        "name",
        "address",
        "state",
        "phone",
        "timezone",
        "booking_mode",
        "waiver_text",
    ]
    for field in fields:
        if field in body and body[field] is not None:
            setattr(facility, field, body[field])
    for field in (
        "deposit_percent",
        "cancellation_window_hours",
        "max_dogs",
        "nightly_rate_paise",
    ):
        if field in body and body[field] is not None:
            setattr(facility, field, int(body[field]))
    for field in ("require_vaccination", "whatsapp_enabled", "email_enabled"):
        if field in body:
            setattr(facility, field, bool(body[field]))
    db.commit()
    return {"ok": True}


@router.get("/settings/rates")
def get_rates(
    db: Session = Depends(get_db),
    current: Principal = Depends(require_role("admin")),
) -> dict:
    addons = (
        db.query(FacilityAddon)
        .filter(FacilityAddon.facility_id == current.facility_id)
        .all()
    )
    return {
        "nightly_rate_paise": current.facility.nightly_rate_paise,
        "addons": [
            {"id": row.id, "name": row.name, "price_paise": row.price_paise}
            for row in addons
        ],
    }


@router.post("/settings/rates/addons", status_code=201)
def add_rate(
    body: dict,
    db: Session = Depends(get_db),
    current: Principal = Depends(require_role("admin")),
) -> dict:
    row = FacilityAddon(
        facility_id=current.facility_id,
        name=str(body.get("name") or "").strip(),
        price_paise=int(body.get("price_paise") or 0),
    )
    if not row.name:
        raise HTTPException(status_code=422, detail="Name is required")
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "name": row.name, "price_paise": row.price_paise}


def _card_summary(db: Session, booking: Booking, day: date, note: str | None) -> str:
    logs = (
        db.query(CareLog)
        .filter(CareLog.booking_id == booking.id)
        .order_by(CareLog.created_at)
        .all()
    )
    lines = [f"{booking.dog.name} on {day.isoformat()}"]
    for log in logs:
        if log.created_at.date() != day:
            continue
        extra = f" — {log.note}" if log.note else ""
        photo = " (photo)" if log.photo_key else ""
        lines.append(f"- {log.kind}{photo}{extra}")
    if note:
        lines.append(note)
    if len(lines) == 1:
        lines.append("No care logs yet today.")
    return "\n".join(lines)


@router.get("/bookings/{booking_id}/report-card")
def preview_report_card(
    booking_id: int,
    db: Session = Depends(get_db),
    current: Principal = Depends(get_current_user),
) -> dict:
    booking = _booking(db, booking_id, current.facility_id)
    if current.role == "parent" and booking.dog.owner_user_id != current.id:
        raise HTTPException(status_code=404, detail="Booking not found")
    day = date.today()
    logs = (
        db.query(CareLog)
        .filter(CareLog.booking_id == booking.id)
        .order_by(CareLog.created_at)
        .all()
    )
    return {
        "summary": _card_summary(db, booking, day, None),
        "logs": [
            {
                "id": log.id,
                "kind": log.kind,
                "note": log.note,
                "photo_url": signed_path(log.photo_key) if log.photo_key else None,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
    }


@router.post("/bookings/{booking_id}/report-cards/send")
def send_report_card(
    booking_id: int,
    body: dict | None = None,
    db: Session = Depends(get_db),
    current: Principal = Depends(get_current_staff),
) -> dict:
    booking = _booking(db, booking_id, current.facility_id)
    day = date.today()
    note = (body or {}).get("note")
    summary = _card_summary(db, booking, day, note)
    card = ReportCard(
        facility_id=current.facility_id,
        booking_id=booking.id,
        day=day,
        summary=summary,
        sent_at=datetime.now(),
        created_by=current.id,
    )
    db.add(card)
    parent = db.get(User, booking.dog.owner_user_id) if booking.dog.owner_user_id else None
    if parent is not None:
        emit(
            db,
            facility=current.facility,
            recipients=[parent],
            event="report_card",
            title=f"Update on {booking.dog.name}",
            body=summary,
            link=f"/owner/dashboard",
        )
    db.commit()
    return {"ok": True, "summary": summary}


@router.post("/bookings/{booking_id}/photos", status_code=201)
async def upload_photo(
    booking_id: int,
    photo: UploadFile = File(...),
    note: str = Form(""),
    db: Session = Depends(get_db),
    current: Principal = Depends(get_current_staff),
) -> dict:
    from booking_service import BookingError, log_care

    booking = _booking(db, booking_id, current.facility_id)
    data = await photo.read()
    if len(data) > 5_000_000:
        raise HTTPException(status_code=413, detail="Photo is larger than 5MB")
    key = save_bytes(current.facility_id, photo.filename or "photo.jpg", data)
    try:
        log = log_care(
            db,
            facility_id=current.facility_id,
            booking=booking,
            actor_id=current.id,
            kind="note",
            note=note or "Photo",
            photo_key=key,
        )
    except BookingError as err:
        raise HTTPException(status_code=err.status_code, detail=err.detail) from err
    db.commit()
    return {"id": log.id, "photo_url": signed_path(key)}


@router.get("/media/{token}")
def media(token: str):
    try:
        path = resolve_token(token)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path)
