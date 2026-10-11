"""In-app notifications plus WhatsApp and email jobs.

In-app delivery is always recorded. WhatsApp and email follow the user's
preference unless the event is forced (severe incident, payment failure).
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from db import (
    Booking,
    Dog,
    Facility,
    Job,
    Membership,
    Notification,
    NotificationDelivery,
    NotificationPreference,
    User,
    VaccinationRecord,
)

CATEGORIES = (
    "bookings",
    "care_updates",
    "incidents",
    "billing",
)
EVENT_CATEGORY = {
    "booking_requested": "bookings",
    "booking_blocked": "bookings",
    "booking_confirmed": "bookings",
    "booking_declined": "bookings",
    "booking_cancelled": "bookings",
    "waitlist_opened": "bookings",
    "parent_arrived": "bookings",
    "dropoff_reminder": "bookings",
    "ready_for_pickup": "bookings",
    "report_card": "care_updates",
    "severe_incident": "incidents",
    "incident_note": "incidents",
    "vaccination_expiring": "incidents",
    "payment_received": "billing",
    "payment_failed": "billing",
    "invoice_issued": "billing",
}
FORCED = {"severe_incident", "payment_failed"}


def ensure_preferences(db: Session, user_id: int, facility_id: int) -> None:
    existing = {
        row.category
        for row in db.query(NotificationPreference)
        .filter(
            NotificationPreference.user_id == user_id,
            NotificationPreference.facility_id == facility_id,
        )
        .all()
    }
    for category in CATEGORIES:
        if category not in existing:
            db.add(
                NotificationPreference(
                    user_id=user_id,
                    facility_id=facility_id,
                    category=category,
                    whatsapp=True,
                    email=True,
                )
            )
    db.flush()


def staff_users(db: Session, facility_id: int) -> list[User]:
    return (
        db.query(User)
        .join(Membership, Membership.user_id == User.id)
        .filter(
            Membership.facility_id == facility_id,
            Membership.role.in_(("admin", "attendant")),
        )
        .all()
    )


def _preference(
    db: Session, user_id: int, facility_id: int, category: str
) -> NotificationPreference:
    ensure_preferences(db, user_id, facility_id)
    return (
        db.query(NotificationPreference)
        .filter(
            NotificationPreference.user_id == user_id,
            NotificationPreference.facility_id == facility_id,
            NotificationPreference.category == category,
        )
        .one()
    )


def emit(
    db: Session,
    *,
    facility: Facility,
    recipients: list[User],
    event: str,
    title: str,
    body: str,
    link: str | None = None,
) -> list[Notification]:
    category = EVENT_CATEGORY[event]
    force = event in FORCED
    created: list[Notification] = []
    for user in recipients:
        if user is None:
            continue
        note = Notification(
            facility_id=facility.id,
            recipient_user_id=user.id,
            type=event,
            title=title,
            body=body,
            link=link,
        )
        db.add(note)
        db.flush()
        db.add(
            NotificationDelivery(
                notification_id=note.id, channel="in_app", status="sent"
            )
        )
        pref = _preference(db, user.id, facility.id, category)
        use_whatsapp = facility.whatsapp_enabled and (force or pref.whatsapp)
        allow_email = (
            facility.email_enabled and bool(user.email) and (force or pref.email)
        )
        if use_whatsapp:
            _enqueue(
                db,
                note,
                "whatsapp",
                {
                    "channel": "whatsapp",
                    "phone": user.phone,
                    "email": user.email,
                    "fallback_email": bool(allow_email),
                    "title": title,
                    "body": body,
                },
            )
        elif allow_email:
            _enqueue(
                db,
                note,
                "email",
                {
                    "channel": "email",
                    "email": user.email,
                    "title": title,
                    "body": body,
                },
            )
        created.append(note)
    db.flush()
    return created


def _enqueue(db: Session, note: Notification, channel: str, payload: dict) -> None:
    delivery = NotificationDelivery(
        notification_id=note.id, channel=channel, status="pending"
    )
    db.add(delivery)
    db.flush()
    payload = {**payload, "delivery_id": delivery.id}
    db.add(
        Job(
            kind="deliver",
            payload=json.dumps(payload),
            status="pending",
            run_at=datetime.now(),
        )
    )


def _send(channel: str, payload: dict) -> tuple[str, str]:
    if channel == "whatsapp":
        if not os.getenv("WHATSAPP_TOKEN"):
            return "skipped", "WhatsApp is not configured"
        return "sent", "accepted by WhatsApp adapter"
    if channel == "email":
        if not os.getenv("SMTP_HOST"):
            return "skipped", "Email is not configured"
        return "sent", "accepted by email adapter"
    return "skipped", "unknown channel"


def process_due_jobs(db: Session, limit: int = 50) -> int:
    now = datetime.now()
    jobs = (
        db.query(Job)
        .filter(Job.status == "pending", Job.run_at <= now)
        .order_by(Job.id)
        .limit(limit)
        .all()
    )
    for job in jobs:
        job.attempts += 1
        try:
            payload = json.loads(job.payload)
            status, detail = _send(payload.get("channel", ""), payload)
            delivery = db.get(NotificationDelivery, payload.get("delivery_id"))
            if delivery is not None:
                delivery.status = status
                delivery.detail = detail
                if (
                    payload.get("channel") == "whatsapp"
                    and status != "sent"
                    and payload.get("fallback_email")
                    and payload.get("email")
                ):
                    email_status, email_detail = _send("email", payload)
                    db.add(
                        NotificationDelivery(
                            notification_id=delivery.notification_id,
                            channel="email",
                            status=email_status,
                            detail=email_detail or "Email fallback after WhatsApp",
                        )
                    )
            job.status = "done"
            job.last_error = None
        except Exception as err:
            job.status = "failed"
            job.last_error = str(err)
    db.flush()
    return len(jobs)


def _sent_today(db: Session, user_id: int, event: str, link: str) -> bool:
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(Notification)
        .filter(
            Notification.recipient_user_id == user_id,
            Notification.type == event,
            Notification.link == link,
            Notification.created_at >= start,
        )
        .first()
        is not None
    )


def scan_due_reminders(db: Session) -> int:
    """Drop-off, pickup, and vaccination reminders. Safe to run more than once a day."""
    today = date.today()
    sent = 0

    soon = today + timedelta(days=30)
    records = (
        db.query(VaccinationRecord)
        .filter(
            VaccinationRecord.expires_on >= today,
            VaccinationRecord.expires_on <= soon,
        )
        .all()
    )
    for record in records:
        dog = db.get(Dog, record.dog_id)
        facility = db.get(Facility, record.facility_id)
        parent = db.get(User, dog.owner_user_id) if dog and dog.owner_user_id else None
        link = f"/dogs/{record.dog_id}/vaccinations/{record.id}"
        if dog is None or facility is None or parent is None:
            continue
        if _sent_today(db, parent.id, "vaccination_expiring", link):
            continue
        emit(
            db,
            facility=facility,
            recipients=[parent],
            event="vaccination_expiring",
            title=f"{dog.name}'s {record.vaccine_type} expires {record.expires_on.isoformat()}",
            body="Upload a new record before the next stay.",
            link=link,
        )
        sent += 1

    tomorrow = today + timedelta(days=1)
    dropoffs = (
        db.query(Booking)
        .filter(
            Booking.start_date == tomorrow,
            Booking.status.in_(("confirmed", "awaiting_payment")),
        )
        .all()
    )
    for booking in dropoffs:
        parent = (
            db.get(User, booking.dog.owner_user_id)
            if booking.dog.owner_user_id
            else None
        )
        facility = db.get(Facility, booking.facility_id)
        link = f"/bookings/{booking.id}"
        if parent is None or facility is None:
            continue
        if _sent_today(db, parent.id, "dropoff_reminder", link):
            continue
        emit(
            db,
            facility=facility,
            recipients=[parent],
            event="dropoff_reminder",
            title=f"Drop-off tomorrow for {booking.dog.name}",
            body=f"Your stay starts {booking.start_date.isoformat()}.",
            link=link,
        )
        sent += 1

    pickups = (
        db.query(Booking)
        .filter(Booking.end_date == today, Booking.status == "checked_in")
        .all()
    )
    for booking in pickups:
        parent = (
            db.get(User, booking.dog.owner_user_id)
            if booking.dog.owner_user_id
            else None
        )
        facility = db.get(Facility, booking.facility_id)
        link = f"/bookings/{booking.id}"
        if parent is None or facility is None:
            continue
        if _sent_today(db, parent.id, "ready_for_pickup", link):
            continue
        emit(
            db,
            facility=facility,
            recipients=[parent],
            event="ready_for_pickup",
            title=f"{booking.dog.name} is ready for pickup",
            body="Today is the last day of the stay.",
            link=link,
        )
        sent += 1
    db.flush()
    return sent
