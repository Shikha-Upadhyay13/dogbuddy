"""Booking state machine, kennel overlap, and the vaccination gate.

Statuses: requested, declined, waitlisted, awaiting_payment, confirmed,
checked_in, checked_out, cancelled. A dog is in care from check-in until
check-out; care itself is rows in care_logs.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from audit import write_audit
from db import Booking, CareLog, Dog, Facility, Incident, Kennel, VaccinationRecord

HOLDING = ("awaiting_payment", "confirmed", "checked_in")
CANCELLABLE = ("requested", "awaiting_payment", "confirmed")
CARE_KINDS = ("walk", "feed", "meds", "note")


class BookingError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def nights(start: date, end: date) -> int:
    return max((end - start).days, 1)


def refresh_vaccination_status(db: Session, dog: Dog) -> None:
    records = (
        db.query(VaccinationRecord)
        .filter(VaccinationRecord.dog_id == dog.id)
        .all()
    )
    today = date.today()
    if not records:
        dog.vaccination_status = "expired"
        dog.vaccination_expires = None
        return
    latest = max(records, key=lambda r: r.expires_on)
    dog.vaccination_expires = latest.expires_on
    if latest.expires_on < today:
        dog.vaccination_status = "expired"
    elif latest.expires_on <= today + timedelta(days=30):
        dog.vaccination_status = "expiring_soon"
    else:
        dog.vaccination_status = "up_to_date"


def vaccination_ok(db: Session, dog: Dog, on_date: date) -> bool:
    records = (
        db.query(VaccinationRecord)
        .filter(VaccinationRecord.dog_id == dog.id)
        .all()
    )
    return any(r.expires_on >= on_date for r in records)


def capacity_full(
    db: Session,
    facility: Facility,
    start: date,
    end: date,
    exclude_id: int | None = None,
) -> bool:
    q = db.query(Booking).filter(
        Booking.facility_id == facility.id,
        Booking.status.in_(HOLDING),
        Booking.start_date <= end,
        Booking.end_date >= start,
    )
    if exclude_id is not None:
        q = q.filter(Booking.id != exclude_id)
    return q.count() >= facility.max_dogs


def kennel_conflict(
    db: Session,
    kennel_id: int,
    start: date,
    end: date,
    exclude_id: int | None = None,
) -> bool:
    q = db.query(Booking).filter(
        Booking.assigned_kennel_id == kennel_id,
        Booking.status.in_(HOLDING),
        Booking.start_date <= end,
        Booking.end_date >= start,
    )
    if exclude_id is not None:
        q = q.filter(Booking.id != exclude_id)
    return q.first() is not None


def _status_after_accept(db: Session, facility: Facility, booking: Booking) -> str:
    if capacity_full(db, facility, booking.start_date, booking.end_date, booking.id):
        return "waitlisted"
    if facility.deposit_percent > 0:
        return "awaiting_payment"
    return "confirmed"


def create_request(
    db: Session,
    *,
    facility: Facility,
    dog: Dog,
    start: date,
    end: date,
    actor_id: int,
    actor_role: str,
    waiver_accepted: bool,
    override: bool = False,
    override_reason: str | None = None,
) -> Booking:
    if end < start:
        raise BookingError(422, "end_date must be >= start_date")
    if facility.waiver_text and not waiver_accepted:
        raise BookingError(422, "The facility waiver must be accepted")
    blocked = facility.require_vaccination and not vaccination_ok(db, dog, start)
    if blocked and not override:
        raise BookingError(
            422, "Vaccination records are missing or expired for these dates"
        )
    if override and actor_role != "admin":
        raise BookingError(403, "Only an admin can override vaccination requirements")
    if override and not (override_reason or "").strip():
        raise BookingError(422, "An override reason is required")

    if facility.booking_mode == "instant":
        placeholder = Booking(
            facility_id=facility.id,
            dog_id=dog.id,
            start_date=start,
            end_date=end,
            status="requested",
        )
        status = _status_after_accept(db, facility, placeholder)
    else:
        status = "requested"

    booking = Booking(
        facility_id=facility.id,
        dog_id=dog.id,
        start_date=start,
        end_date=end,
        status=status,
        waiver_version_accepted=facility.waiver_version if waiver_accepted else None,
    )
    if override:
        booking.vaccination_override_by = actor_id
        booking.vaccination_override_reason = (override_reason or "").strip()
    db.add(booking)
    db.flush()
    write_audit(
        db,
        facility_id=facility.id,
        staff_id=actor_id,
        action="create_booking",
        target_type="booking",
        target_id=booking.id,
        details={
            "dog_id": dog.id,
            "status": status,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "override": override,
        },
    )
    return booking


def decide(
    db: Session,
    *,
    facility: Facility,
    booking: Booking,
    action: str,
    actor_id: int,
) -> Booking:
    before = booking.status
    if action == "decline" and booking.status == "requested":
        booking.status = "declined"
    elif action == "waitlist" and booking.status == "requested":
        booking.status = "waitlisted"
    elif action == "accept" and booking.status in ("requested", "waitlisted"):
        booking.status = _status_after_accept(db, facility, booking)
    else:
        raise BookingError(422, f"Cannot {action} a booking that is {booking.status}")
    write_audit(
        db,
        facility_id=facility.id,
        staff_id=actor_id,
        action="booking_decision",
        target_type="booking",
        target_id=booking.id,
        details={"before": before, "after": booking.status, "decision": action},
    )
    return booking


def cancel_booking(
    db: Session, *, facility: Facility, booking: Booking, actor_id: int, actor_role: str
) -> Booking:
    if booking.status not in CANCELLABLE:
        raise BookingError(422, f"Cannot cancel a booking that is {booking.status}")
    if booking.status == "confirmed" and actor_role == "parent":
        window = timedelta(hours=facility.cancellation_window_hours)
        starts = datetime.combine(booking.start_date, datetime.min.time())
        if starts - datetime.now() < window:
            raise BookingError(
                422, "This stay is inside the cancellation window. Ask the facility."
            )
    before = booking.status
    booking.status = "cancelled"
    if booking.assigned_kennel_id:
        kennel = db.get(Kennel, booking.assigned_kennel_id)
        if kennel is not None and kennel.status == "reserved":
            kennel.status = "available"
    write_audit(
        db,
        facility_id=facility.id,
        staff_id=actor_id,
        action="cancel_booking",
        target_type="booking",
        target_id=booking.id,
        details={"before": before},
    )
    return booking


def assign_kennel(
    db: Session,
    *,
    facility: Facility,
    booking: Booking,
    kennel_id: int,
    actor_id: int,
) -> Booking:
    kennel = db.get(Kennel, kennel_id)
    if kennel is None or kennel.facility_id != facility.id:
        raise BookingError(404, "Kennel not found")
    if kennel.status == "maintenance":
        raise BookingError(422, f"{kennel.name} is under maintenance")
    if kennel_conflict(db, kennel.id, booking.start_date, booking.end_date, booking.id):
        raise BookingError(409, f"{kennel.name} is already booked for those dates")
    booking.assigned_kennel_id = kennel.id
    booking.kennel_id = kennel.name
    if booking.status == "confirmed":
        kennel.status = "reserved"
    elif booking.status == "checked_in":
        kennel.status = "occupied"
    write_audit(
        db,
        facility_id=facility.id,
        staff_id=actor_id,
        action="assign_kennel",
        target_type="booking",
        target_id=booking.id,
        details={"kennel_id": kennel.id, "kennel": kennel.name},
    )
    return booking


def open_severe_incidents(db: Session, booking: Booking) -> list[Incident]:
    return (
        db.query(Incident)
        .filter(
            Incident.facility_id == booking.facility_id,
            Incident.dog_id == booking.dog_id,
            Incident.severity == "severe",
            Incident.acknowledged_at.is_(None),
            Incident.created_at >= datetime.combine(booking.start_date, datetime.min.time()),
        )
        .all()
    )


def check_in(
    db: Session,
    *,
    facility: Facility,
    booking: Booking,
    actor_id: int,
    belongings: str,
    diet_confirmed: bool,
    meds_confirmed: bool,
    vet_confirmed: bool,
    kennel_id: int | None,
) -> Booking:
    if booking.status != "confirmed":
        raise BookingError(422, "Only a confirmed stay can be checked in")
    if not (diet_confirmed and meds_confirmed and vet_confirmed):
        raise BookingError(422, "Confirm diet, medication, and vet contact before check-in")
    if kennel_id is not None:
        assign_kennel(
            db,
            facility=facility,
            booking=booking,
            kennel_id=kennel_id,
            actor_id=actor_id,
        )
    if booking.assigned_kennel_id is None:
        raise BookingError(422, "Assign a kennel before check-in")
    kennel = db.get(Kennel, booking.assigned_kennel_id)
    if kennel is not None:
        kennel.status = "occupied"
    before = booking.status
    booking.status = "checked_in"
    booking.belongings = belongings
    booking.diet_confirmed = True
    booking.meds_confirmed = True
    booking.vet_confirmed = True
    write_audit(
        db,
        facility_id=facility.id,
        staff_id=actor_id,
        action="update_status",
        target_type="booking",
        target_id=booking.id,
        details={"before": before, "after": "checked_in", "dog_id": booking.dog_id},
    )
    return booking


def check_out(
    db: Session,
    *,
    facility: Facility,
    booking: Booking,
    actor_id: int,
    actor_role: str,
    acknowledge_severe: bool,
) -> Booking:
    if booking.status != "checked_in":
        raise BookingError(422, "Only a checked-in stay can be checked out")
    severe = open_severe_incidents(db, booking)
    if severe:
        if not acknowledge_severe or actor_role != "admin":
            raise BookingError(
                409,
                "An open severe incident must be acknowledged by an admin before check-out",
            )
        now = datetime.now()
        for incident in severe:
            incident.acknowledged_at = now
            incident.acknowledged_by = actor_id
    before = booking.status
    booking.status = "checked_out"
    if booking.assigned_kennel_id:
        kennel = db.get(Kennel, booking.assigned_kennel_id)
        if kennel is not None:
            kennel.status = "cleaning"
    write_audit(
        db,
        facility_id=facility.id,
        staff_id=actor_id,
        action="update_status",
        target_type="booking",
        target_id=booking.id,
        details={"before": before, "after": "checked_out", "dog_id": booking.dog_id},
    )
    return booking


def log_care(
    db: Session,
    *,
    facility_id: int,
    booking: Booking,
    actor_id: int,
    kind: str,
    note: str | None = None,
    photo_key: str | None = None,
) -> CareLog:
    if kind not in CARE_KINDS:
        raise BookingError(422, f"Invalid activity: {kind}")
    if booking.status != "checked_in":
        raise BookingError(422, "Care can only be logged while the dog is checked in")
    now = datetime.now()
    row = CareLog(
        facility_id=facility_id,
        booking_id=booking.id,
        dog_id=booking.dog_id,
        staff_id=actor_id,
        kind=kind,
        note=note,
        photo_key=photo_key,
        created_at=now,
    )
    db.add(row)
    field = {"walk": "last_walked_at", "feed": "last_fed_at", "meds": "last_meds_at"}.get(
        kind
    )
    if field:
        setattr(booking, field, now)
    db.flush()
    write_audit(
        db,
        facility_id=facility_id,
        staff_id=actor_id,
        action="update_activity",
        target_type="booking",
        target_id=booking.id,
        details={"activity": kind, "at": now.isoformat(), "dog_id": booking.dog_id},
    )
    return row
