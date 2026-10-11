"""Settings, the notification inbox, report cards, and signed media."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
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
        "billing_state": current.user.billing_state,
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
    if "billing_state" in body:
        user.billing_state = str(body.get("billing_state") or "").strip() or None
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
        "gstin": facility.gstin,
        "gst_rate_bps": facility.gst_rate_bps,
        "razorpay_key_id": facility.razorpay_key_id,
        "razorpay_configured": bool(facility.razorpay_key_secret),
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
    if "gstin" in body:
        facility.gstin = str(body.get("gstin") or "").strip() or None
    if body.get("gst_rate_bps") is not None:
        facility.gst_rate_bps = int(body["gst_rate_bps"])
    if "razorpay_key_id" in body:
        facility.razorpay_key_id = (
            str(body.get("razorpay_key_id") or "").strip() or None
        )
    from billing import encrypt_secret

    if body.get("razorpay_key_secret"):
        facility.razorpay_key_secret = encrypt_secret(str(body["razorpay_key_secret"]))
    if body.get("razorpay_webhook_secret"):
        facility.razorpay_webhook_secret = encrypt_secret(
            str(body["razorpay_webhook_secret"])
        )
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
    parent = (
        db.get(User, booking.dog.owner_user_id) if booking.dog.owner_user_id else None
    )
    if parent is not None:
        emit(
            db,
            facility=current.facility,
            recipients=[parent],
            event="report_card",
            title=f"Update on {booking.dog.name}",
            body=summary,
            link="/owner/dashboard",
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


def _invoice_or_404(db: Session, invoice_id: int, facility_id: int):
    from db import Invoice

    invoice = db.get(Invoice, invoice_id)
    if invoice is None or invoice.facility_id != facility_id:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.get("/invoices")
def list_invoices(
    db: Session = Depends(get_db),
    current: Principal = Depends(get_current_staff),
) -> list[dict]:
    from billing import invoice_out
    from db import Invoice

    rows = (
        db.query(Invoice)
        .filter(Invoice.facility_id == current.facility_id)
        .order_by(Invoice.id.desc())
        .all()
    )
    return [invoice_out(row) for row in rows]


@router.get("/invoices/mine")
def my_invoices(
    db: Session = Depends(get_db),
    current: Principal = Depends(require_role("parent")),
) -> list[dict]:
    from billing import invoice_out
    from db import Dog, Invoice

    rows = (
        db.query(Invoice)
        .join(Booking, Invoice.booking_id == Booking.id)
        .join(Dog, Booking.dog_id == Dog.id)
        .filter(
            Invoice.facility_id == current.facility_id,
            Dog.owner_user_id == current.id,
        )
        .order_by(Invoice.id.desc())
        .all()
    )
    return [invoice_out(row) for row in rows]


@router.post("/invoices/{invoice_id}/payments", status_code=201)
def pay_invoice(
    invoice_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current: Principal = Depends(require_role("admin")),
) -> dict:
    from billing import BillingError, record_payment

    invoice = _invoice_or_404(db, invoice_id, current.facility_id)
    method = str(body.get("method") or "")
    if method not in ("cash", "upi"):
        raise HTTPException(status_code=422, detail="Record cash or UPI here")
    try:
        payment = record_payment(
            db,
            facility=current.facility,
            invoice=invoice,
            amount_paise=int(body.get("amount_paise") or 0),
            method=method,
            actor_id=current.id,
        )
    except BillingError as err:
        raise HTTPException(status_code=err.status_code, detail=err.detail) from err
    db.commit()
    return {"id": payment.id, "status": payment.status}


@router.post("/invoices/{invoice_id}/credit-notes", status_code=201)
def credit_invoice(
    invoice_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current: Principal = Depends(require_role("admin")),
) -> dict:
    from billing import BillingError, invoice_out, issue_credit_note

    invoice = _invoice_or_404(db, invoice_id, current.facility_id)
    try:
        note = issue_credit_note(
            db,
            current.facility,
            invoice,
            current.id,
            str(body.get("reason") or "correction"),
        )
    except BillingError as err:
        raise HTTPException(status_code=err.status_code, detail=err.detail) from err
    original_total = invoice.total_paise
    db.commit()
    db.refresh(invoice)
    if invoice.total_paise != original_total:
        raise HTTPException(status_code=500, detail="Issued invoice was modified")
    return invoice_out(note)


@router.post("/payments/{payment_id}/refund", status_code=201)
def refund(
    payment_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current: Principal = Depends(require_role("admin")),
) -> dict:
    from billing import BillingError, refund_payment
    from db import Payment

    payment = db.get(Payment, payment_id)
    if payment is None or payment.facility_id != current.facility_id:
        raise HTTPException(status_code=404, detail="Payment not found")
    try:
        entry = refund_payment(
            db,
            current.facility,
            payment,
            current.id,
            int(body.get("amount_paise") or payment.amount_paise),
        )
    except BillingError as err:
        raise HTTPException(status_code=err.status_code, detail=err.detail) from err
    db.commit()
    return {"id": entry.id, "amount_paise": entry.amount_paise}


@router.post("/webhooks/razorpay/{facility_id}")
async def razorpay_webhook(
    facility_id: int, request: Request, db: Session = Depends(get_db)
) -> dict:
    from billing import BillingError, handle_webhook

    body = await request.body()
    try:
        result = handle_webhook(
            db,
            facility_id,
            body,
            request.headers.get("x-razorpay-signature", ""),
        )
    except BillingError as err:
        raise HTTPException(status_code=err.status_code, detail=err.detail) from err
    db.commit()
    return result


@router.get("/media/{token}")
def media(token: str):
    try:
        path = resolve_token(token)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path)
