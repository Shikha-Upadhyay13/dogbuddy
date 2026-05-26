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
from db import Booking, Dog, Incident, SessionLocal

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


def _find_dog_by_name(db, name: str) -> Optional[Dog]:
    name_l = name.strip().lower()
    rows = db.scalars(select(Dog)).all()
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


def make_tools(staff_id: int) -> list:
    """Return the 4 tools with `staff_id` captured by closure."""

    @tool
    def query_db(query_type: str, params: Optional[dict] = None) -> str:
        """
        Query the facility database. Use this for any question about dogs,
        bookings, owners, or incidents in the facility.

        query_type options:
        - "todays_bookings": all dogs in facility today (no params)
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
                rows = (
                    db.query(Booking)
                    .filter(Booking.start_date <= today, Booking.end_date >= today)
                    .all()
                )
                if not rows:
                    return "No dogs in facility today."
                lines = [f"{len(rows)} dog(s) in facility today:"]
                for b in rows:
                    lines.append(
                        f"  - {b.dog.name} ({b.dog.breed}) - status={b.status} - kennel={b.kennel_id or '-'}"
                    )
                return "\n".join(lines)

            if query_type == "dog_by_name":
                name = params_local.get("name", "").strip()
                if not name:
                    return "Error: dog_by_name requires params={'name': '<dog name>'}"
                d = _find_dog_by_name(db, name)
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
                        Dog.vaccination_status.in_(("expiring_soon", "expired"))
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

    _STATUS_ACTIONS = {
        "check_in": "checked_in",
        "in_care": "in_care",
        "check_out": "checked_out",
    }
    _ACTIVITY_ACTIONS = {
        "walked": "last_walked_at",
        "fed": "last_fed_at",
        "meds_given": "last_meds_at",
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
            dog = _find_dog_by_name(db, dog_name)
            if dog is None:
                return f"No dog named '{dog_name}' found."

            today = date.today()
            booking = (
                db.query(Booking)
                .filter(
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
                    .filter(Booking.dog_id == dog.id)
                    .order_by(Booking.start_date.desc())
                    .first()
                )
            if booking is None:
                return f"No booking found for {dog.name}."

            if action in _STATUS_ACTIONS:
                new_status = _STATUS_ACTIONS[action]
                before = booking.status
                booking.status = new_status
                write_audit(
                    db,
                    staff_id=staff_id,
                    action="update_status",
                    target_type="booking",
                    target_id=booking.id,
                    details={
                        "before": before,
                        "after": new_status,
                        "dog_id": dog.id,
                        "via": "agent",
                    },
                )
                db.commit()
                return f"Updated {dog.name}: status {before} -> {new_status}."

            if action in _ACTIVITY_ACTIONS:
                field = _ACTIVITY_ACTIONS[action]
                now = datetime.now()
                setattr(booking, field, now)
                write_audit(
                    db,
                    staff_id=staff_id,
                    action="update_activity",
                    target_type="booking",
                    target_id=booking.id,
                    details={
                        "activity": action,
                        "at": now.isoformat(),
                        "dog_id": dog.id,
                        "via": "agent",
                    },
                )
                db.commit()
                return f"Recorded for {dog.name}: {action} at {now.strftime('%H:%M')}."

            return (
                f"Error: unknown action '{action}'. "
                "Valid: check_in, in_care, check_out, walked, fed, meds_given."
            )
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

            dog = _find_dog_by_name(db, dog_name)
            if dog is None:
                return f"No dog named '{dog_name}' found - cannot log incident."

            incident = Incident(
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

    return [query_db, update_status, log_incident, web_search]
