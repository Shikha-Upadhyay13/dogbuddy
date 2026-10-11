"""The 4 tools the agent can call. PRD Section 7.3.

We build tools per request via `make_tools(staff_id)` so `staff_id` is
captured in a closure — this is more robust than a ContextVar across the
async/threaded boundaries LangGraph creates when dispatching tools.

* DB-touching tools open their own SessionLocal() and commit/close.
* Every mutation writes audit_log (deterministic eval oracle).
* All tools wrap in try/except and return error strings instead of raising,
  per PRD line 547–555.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Optional

import httpx
from dotenv import load_dotenv
from langchain_core.tools import tool
from sqlalchemy import select

from audit import write_audit
from booking_service import (
    BookingError,
    assign_kennel,
    check_in,
    check_out,
    create_request,
    kennel_conflict,
    log_care,
)
from db import Booking, Dog, Facility, Incident, Kennel, SessionLocal, User

load_dotenv()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt_dt(dt: Optional[datetime]) -> str:
    if dt is None:
        return "never"
    delta = datetime.now() - dt
    mins = int(delta.total_seconds() / 60)
    if mins < 1:
        return "just now"
    if mins < 60:
        return f"{mins} min ago"
    hours = mins // 60
    if hours < 24:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


def _find_dog_by_name(
    db, name: str, facility_id: int, owner_user_id: Optional[int] = None
) -> Optional[Dog]:
    name_l = name.strip().lower()
    q = select(Dog).where(Dog.facility_id == facility_id)
    if owner_user_id is not None:
        q = q.where(Dog.owner_user_id == owner_user_id)
    rows = db.scalars(q).all()
    for d in rows:
        if d.name.lower() == name_l:
            return d
    for d in rows:
        if d.name.lower().startswith(name_l):
            return d
    return None


PARALLEL_API_URL = "https://api.parallel.ai/v1beta/search"


# ---------------------------------------------------------------------------
# Factory: build a fresh tool set bound to a staff_id
# ---------------------------------------------------------------------------


def make_tools(staff_id: int, facility_id: int, role: str = "attendant") -> list:
    """Return tools bound to one user, one facility, and that membership's role."""

    owner_scope = staff_id if role == "parent" else None
    is_staff = role in ("admin", "attendant")

    @tool
    def query_db(query_type: str, params: Optional[dict] = None) -> str:
        """
        Query the facility database. Use this for any question about dogs,
        bookings, owners, or incidents in the facility.

        query_type options:
        - "todays_bookings": all dogs in facility today (no params)
        - "upcoming_bookings": all future bookings (today or later). Optional
          params {"dog_name": "Toby"} to filter to one dog's bookings. Use
          this when staff asks about future stays, scheduled arrivals, or
          "any booking for X".
        - "dog_by_name": get dog details (params: {"name": "Rex"})
        - "pending_tasks": dogs needing walk/feed/meds (params: {"task": "walk"})
        - "recent_incidents": last 20 incidents (no params)
        - "vaccination_status": dogs with expiring/expired vaccines (no params)

        Returns: a human-readable summary string.
        """
        params_local = params or {}
        db = SessionLocal()
        try:
            if query_type == "todays_bookings":
                today = date.today()
                q = db.query(Booking).filter(
                    Booking.facility_id == facility_id,
                    Booking.start_date <= today,
                    Booking.end_date >= today,
                )
                if owner_scope is not None:
                    q = q.join(Dog, Booking.dog_id == Dog.id).filter(
                        Dog.owner_user_id == owner_scope
                    )
                rows = q.all()
                if not rows:
                    return "No dogs in facility today."
                lines = [f"{len(rows)} dog(s) in facility today:"]
                for b in rows:
                    lines.append(
                        f"  - {b.dog.name} ({b.dog.breed}) - status={b.status} - kennel={b.kennel_id or '-'}"
                    )
                return "\n".join(lines)

            if query_type == "upcoming_bookings":
                today = date.today()
                dog_name = (params_local.get("dog_name") or "").strip()
                # start_date > today (strictly future) -- excludes dogs
                # already in care today. For currently-staying dogs use
                # `todays_bookings` instead.
                q = db.query(Booking).filter(
                    Booking.facility_id == facility_id,
                    Booking.start_date > today,
                )
                if owner_scope is not None:
                    q = q.join(Dog, Booking.dog_id == Dog.id).filter(
                        Dog.owner_user_id == owner_scope
                    )
                if dog_name:
                    target = _find_dog_by_name(db, dog_name, facility_id, owner_scope)
                    if target is None:
                        return f"No dog named '{dog_name}' found."
                    q = q.filter(Booking.dog_id == target.id)
                rows = q.order_by(Booking.start_date).all()
                if not rows:
                    if dog_name:
                        return f"No upcoming bookings for {dog_name}."
                    return "No upcoming bookings on the books."
                header = (
                    f"Upcoming bookings for {dog_name}:"
                    if dog_name
                    else f"{len(rows)} upcoming booking(s):"
                )
                lines = [header]
                for b in rows:
                    lines.append(
                        f"  - {b.dog.name} ({b.dog.breed}) · "
                        f"{b.start_date} -> {b.end_date} · status={b.status} · "
                        f"kennel={b.kennel_id or '-'}"
                    )
                return "\n".join(lines)

            if query_type == "dog_by_name":
                name = params_local.get("name", "").strip()
                if not name:
                    return "Error: dog_by_name requires params={'name': '<dog name>'}"
                d = _find_dog_by_name(db, name, facility_id, owner_scope)
                if d is None:
                    return f"No dog named '{name}' found in the facility."
                return (
                    f"{d.name} - {d.breed}, {d.age_years}y, {d.weight_kg}kg. "
                    f"Diet: {d.diet or 'n/a'}. Meds: {d.medications or 'none'}. "
                    f"Allergies: {d.allergies or 'none'}. Vacc: {d.vaccination_status}"
                    f"{f' (expires {d.vaccination_expires})' if d.vaccination_expires else ''}. "
                    f"Owner: {d.owner_name} ({d.owner_phone}). "
                    f"Notes: {d.notes or '-'}."
                )

            if query_type == "pending_tasks":
                task = params_local.get("task", "").lower()
                field_map = {
                    "walk": "last_walked_at",
                    "feed": "last_fed_at",
                    "meds": "last_meds_at",
                }
                if task not in field_map:
                    return "Error: pending_tasks requires params={'task': 'walk'|'feed'|'meds'}"
                today = date.today()
                rows = (
                    db.query(Booking)
                    .filter(
                        Booking.facility_id == facility_id,
                        Booking.start_date <= today,
                        Booking.end_date >= today,
                        Booking.status.in_(("checked_in", "in_care")),
                    )
                    .all()
                )
                threshold = timedelta(hours=4 if task == "walk" else 6)
                now = datetime.now()
                overdue = []
                for b in rows:
                    ts = getattr(b, field_map[task])
                    if ts is None or (now - ts) > threshold:
                        overdue.append(f"  - {b.dog.name}: last {task} {_fmt_dt(ts)}")
                if not overdue:
                    return f"No dogs are overdue for {task} right now."
                return f"Dogs needing {task}:\n" + "\n".join(overdue)

            if query_type == "recent_incidents":
                rows = (
                    db.query(Incident)
                    .filter(Incident.facility_id == facility_id)
                    .order_by(Incident.created_at.desc())
                    .limit(20)
                    .all()
                )
                if not rows:
                    return "No incidents on record."
                lines = [f"{len(rows)} recent incident(s):"]
                for i in rows:
                    d = db.get(Dog, i.dog_id)
                    lines.append(
                        f"  - #{i.id} {d.name if d else 'unknown'} - {i.type}/{i.severity} - "
                        f"{_fmt_dt(i.created_at)} - {i.description}"
                    )
                return "\n".join(lines)

            if query_type == "vaccination_status":
                rows = db.scalars(
                    select(Dog).where(
                        Dog.facility_id == facility_id,
                        Dog.vaccination_status.in_(("expiring_soon", "expired")),
                    )
                ).all()
                if not rows:
                    return "All dogs are up to date on vaccinations."
                lines = ["Vaccination concerns:"]
                for d in rows:
                    lines.append(
                        f"  - {d.name}: {d.vaccination_status}"
                        f"{f' (expires {d.vaccination_expires})' if d.vaccination_expires else ''}"
                    )
                return "\n".join(lines)

            return (
                f"Error: unknown query_type '{query_type}'. "
                "Valid options: todays_bookings, dog_by_name, pending_tasks, "
                "recent_incidents, vaccination_status."
            )
        except Exception as e:
            return (
                f"Could not complete that - {e}. Try rephrasing or check the dashboard."
            )
        finally:
            db.close()

    _ACTIVITY_ACTIONS = {
        "walked": "walk",
        "fed": "feed",
        "meds_given": "meds",
    }

    @tool
    def update_status(dog_name: str, action: str) -> str:
        """
        Update a dog's status or activity.

        action options:
        - "check_in": mark dog as checked in
        - "in_care": mark dog as in care
        - "check_out": mark dog as checked out (REQUIRES CONFIRMATION)
        - "walked": record a walk now
        - "fed": record feeding now
        - "meds_given": record medication given now

        Returns: confirmation string.
        """
        db = SessionLocal()
        try:
            if not is_staff:
                return "Error: only facility staff can update a dog's status."
            dog = _find_dog_by_name(db, dog_name, facility_id)
            if dog is None:
                return f"No dog named '{dog_name}' found."

            today = date.today()
            booking = (
                db.query(Booking)
                .filter(
                    Booking.facility_id == facility_id,
                    Booking.dog_id == dog.id,
                    Booking.start_date <= today,
                    Booking.end_date >= today,
                )
                .order_by(Booking.start_date.desc())
                .first()
            )
            if booking is None:
                booking = (
                    db.query(Booking)
                    .filter(
                        Booking.facility_id == facility_id,
                        Booking.dog_id == dog.id,
                    )
                    .order_by(Booking.start_date.desc())
                    .first()
                )
            if booking is None:
                return f"No booking found for {dog.name}."

            facility = db.get(Facility, facility_id)
            if facility is None:
                return "Error: facility not found."

            if action == "in_care":
                if booking.status != "checked_in":
                    return (
                        f"{dog.name} is not checked in. "
                        "A dog is in care from check-in until check-out."
                    )
                log_care(
                    db,
                    facility_id=facility_id,
                    booking=booking,
                    actor_id=staff_id,
                    kind="note",
                    note="Marked in care via chat",
                )
                db.commit()
                return f"{dog.name} is in care (checked in)."

            if action == "check_in":
                if not dog.diet or not dog.vet_contact:
                    return (
                        f"Cannot check {dog.name} in from chat until diet and vet "
                        "contact are on the record. Confirm them on the dashboard."
                    )
                kennel_id = booking.assigned_kennel_id
                if kennel_id is None:
                    for kennel in (
                        db.query(Kennel)
                        .filter(Kennel.facility_id == facility_id)
                        .order_by(Kennel.name)
                        .all()
                    ):
                        if kennel.status == "maintenance":
                            continue
                        if not kennel_conflict(
                            db,
                            kennel.id,
                            booking.start_date,
                            booking.end_date,
                            booking.id,
                        ):
                            kennel_id = kennel.id
                            break
                check_in(
                    db,
                    facility=facility,
                    booking=booking,
                    actor_id=staff_id,
                    belongings="Recorded via chat",
                    diet_confirmed=True,
                    meds_confirmed=True,
                    vet_confirmed=True,
                    kennel_id=kennel_id,
                )
                db.commit()
                return f"Checked in {dog.name}."

            if action == "check_out":
                check_out(
                    db,
                    facility=facility,
                    booking=booking,
                    actor_id=staff_id,
                    actor_role=role,
                    acknowledge_severe=False,
                )
                db.commit()
                return f"Checked out {dog.name}."

            if action in _ACTIVITY_ACTIONS:
                log_care(
                    db,
                    facility_id=facility_id,
                    booking=booking,
                    actor_id=staff_id,
                    kind=_ACTIVITY_ACTIONS[action],
                )
                db.commit()
                now = datetime.now()
                return f"Recorded for {dog.name}: {action} at {now.strftime('%H:%M')}."

            return (
                f"Error: unknown action '{action}'. "
                "Valid: check_in, in_care, check_out, walked, fed, meds_given."
            )
        except BookingError as err:
            db.rollback()
            return err.detail
        except Exception as e:
            db.rollback()
            return f"Could not update {dog_name} - {e}."
        finally:
            db.close()

    _INCIDENT_TYPES = {"health", "behavior", "feeding", "other"}
    _SEVERITIES = {"mild", "moderate", "severe"}

    @tool
    def log_incident(
        dog_name: str, incident_type: str, severity: str, description: str
    ) -> str:
        """
        Log an incident for a dog.

        incident_type: "health" | "behavior" | "feeding" | "other"
        severity: "mild" | "moderate" | "severe"
        description: factual description of what happened

        Returns: confirmation string with incident id.
        """
        db = SessionLocal()
        try:
            if incident_type not in _INCIDENT_TYPES:
                return f"Error: invalid incident_type '{incident_type}'. Valid: {sorted(_INCIDENT_TYPES)}."
            if severity not in _SEVERITIES:
                return f"Error: invalid severity '{severity}'. Valid: {sorted(_SEVERITIES)}."

            if not is_staff:
                return "Error: only facility staff can log incidents."
            dog = _find_dog_by_name(db, dog_name, facility_id)
            if dog is None:
                return f"No dog named '{dog_name}' found - cannot log incident."

            incident = Incident(
                facility_id=facility_id,
                dog_id=dog.id,
                staff_id=staff_id,
                type=incident_type,
                severity=severity,
                description=description,
            )
            db.add(incident)
            db.flush()
            write_audit(
                db,
                facility_id=facility_id,
                staff_id=staff_id,
                action="log_incident",
                target_type="incident",
                target_id=incident.id,
                details={
                    "dog_id": dog.id,
                    "type": incident_type,
                    "severity": severity,
                    "description": description,
                    "via": "agent",
                },
            )
            db.commit()
            return f"Logged incident #{incident.id} for {dog.name} - {incident_type}/{severity}."
        except Exception as e:
            db.rollback()
            return f"Could not log incident - {e}."
        finally:
            db.close()

    @tool
    def web_search(query: str) -> str:
        """
        Search the live web for general dog health, breed, behavior,
        nutrition, training, or care information. Use this for questions
        that are NOT about the specific facility's data.

        DO NOT use this for medication dosing - always defer to the vet instead.

        Returns: synthesized answer with citation URLs.
        """
        api_key = os.getenv("PARALLEL_API_KEY")
        if not api_key:
            return "Web search unavailable: PARALLEL_API_KEY is not set in the backend .env."
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    PARALLEL_API_URL,
                    headers={"x-api-key": api_key, "Content-Type": "application/json"},
                    json={
                        "objective": query,
                        "search_queries": [query],
                        "processor": "base",
                        "max_results": 5,
                    },
                )
            if resp.status_code != 200:
                return f"Web search failed ({resp.status_code}): {resp.text[:200]}"

            data = resp.json()
            results = data.get("results", [])
            if not results:
                return f"No results found for: {query}"

            excerpts: list[str] = []
            urls: list[str] = []
            for r in results[:3]:
                url = r.get("url")
                if url and url not in urls:
                    urls.append(url)
                for ex in r.get("excerpts", [])[:1]:
                    if ex:
                        excerpts.append(ex.strip())

            synthesis = " ".join(excerpts[:3])[:800]
            sources = "\n".join(f"- {u}" for u in urls[:3])
            return f"{synthesis}\n\nSources:\n{sources}"
        except Exception as e:
            return f"Web search error - {e}."

    _VACC = {"up_to_date", "expiring_soon", "expired"}

    @tool
    def register_dog(
        name: str,
        breed: str,
        age_years: int,
        weight_kg: float,
        diet: Optional[str] = None,
        medications: Optional[str] = None,
        allergies: Optional[str] = None,
        vaccination_status: str = "up_to_date",
        vet_contact: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> str:
        """
        Register a new dog under the current user's account. Use this when
        the OWNER (not staff) wants to add a dog to their profile, typically
        as a prelude to booking a stay.

        Required: name, breed, age_years, weight_kg.
        Optional: diet, medications, allergies, vaccination_status
                  (up_to_date / expiring_soon / expired), vet_contact, notes.

        Returns: confirmation with the new dog id.
        """
        db = SessionLocal()
        try:
            user = db.get(User, staff_id)
            if user is None:
                return "Error: current user not found."
            if role != "parent":
                return (
                    "Error: only pet parents can register a dog. Staff should "
                    "not create dogs via chat."
                )
            if vaccination_status not in _VACC:
                return (
                    f"Error: vaccination_status must be one of "
                    f"{sorted(_VACC)}, got {vaccination_status!r}."
                )
            dog = Dog(
                facility_id=facility_id,
                name=name,
                breed=breed,
                age_years=age_years,
                weight_kg=weight_kg,
                diet=diet,
                medications=medications,
                allergies=allergies,
                vaccination_status=vaccination_status,
                owner_name=user.name,
                owner_phone=user.phone,
                owner_user_id=user.id,
                vet_contact=vet_contact,
                notes=notes,
            )
            db.add(dog)
            db.flush()
            write_audit(
                db,
                facility_id=facility_id,
                staff_id=staff_id,
                action="register_dog",
                target_type="dog",
                target_id=dog.id,
                details={"name": name, "breed": breed, "via": "agent"},
            )
            db.commit()
            return (
                f"Registered {name} (#{dog.id}) - {breed}, {age_years}y, {weight_kg}kg."
            )
        except Exception as e:
            db.rollback()
            return f"Could not register dog - {e}."
        finally:
            db.close()

    @tool
    def create_booking(
        dog_name: str,
        start_date: str,
        end_date: str,
        kennel_id: Optional[str] = None,
    ) -> str:
        """
        Create a booking (a stay) for one of the OWNER'S dogs. Use this
        when an owner says something like "book Bruno from Dec 20 to Dec 28."

        dates: ISO format (YYYY-MM-DD).
        kennel_id: optional preferred kennel.

        Owners can only book stays for dogs THEY registered. Staff cannot
        use this tool (staff create bookings via the dashboard).

        Returns: confirmation with the new booking id and dates.
        """
        db = SessionLocal()
        try:
            user = db.get(User, staff_id)
            if user is None:
                return "Error: current user not found."
            if role != "parent":
                return "Error: only pet parents can create bookings via chat."

            try:
                start = date.fromisoformat(start_date)
                end = date.fromisoformat(end_date)
            except ValueError:
                return (
                    f"Error: dates must be YYYY-MM-DD. "
                    f"Got start={start_date!r}, end={end_date!r}."
                )
            if end < start:
                return "Error: end_date must be on or after start_date."

            dog = _find_dog_by_name(db, dog_name, facility_id, staff_id)
            if dog is None:
                return f"No dog named '{dog_name}' found - register them first."
            if dog.owner_user_id != user.id:
                return f"'{dog.name}' isn't on your profile - you can only book stays for your own dogs."

            facility = db.get(Facility, facility_id)
            if facility is None:
                return "Error: facility not found."
            booking = create_request(
                db,
                facility=facility,
                dog=dog,
                start=start,
                end=end,
                actor_id=staff_id,
                actor_role="parent",
                waiver_accepted=True,
            )
            if kennel_id:
                kennel = (
                    db.query(Kennel)
                    .filter(
                        Kennel.facility_id == facility_id,
                        Kennel.name == kennel_id,
                    )
                    .one_or_none()
                )
                if kennel is not None and booking.status in ("confirmed", "checked_in"):
                    assign_kennel(
                        db,
                        facility=facility,
                        booking=booking,
                        kennel_id=kennel.id,
                        actor_id=staff_id,
                    )
            db.commit()
            return (
                f"Requested stay #{booking.id} for {dog.name}: "
                f"{start.isoformat()} to {end.isoformat()} (status {booking.status})."
            )
        except BookingError as err:
            db.rollback()
            return err.detail
        except Exception as e:
            db.rollback()
            return f"Could not create booking - {e}."
        finally:
            db.close()

    return [
        query_db,
        update_status,
        log_incident,
        web_search,
        register_dog,
        create_booking,
    ]
