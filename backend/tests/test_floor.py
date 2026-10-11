"""Vaccination gate, kennel overlap, and booking transitions."""

from __future__ import annotations

from datetime import date, timedelta

from auth import hash_password
from db import (
    Dog,
    Facility,
    Kennel,
    Membership,
    SessionLocal,
    User,
    VaccinationRecord,
)


def _world():
    db = SessionLocal()
    facility = Facility(
        name="Floor",
        slug="floor",
        state="Karnataka",
        max_dogs=1,
        require_vaccination=True,
        deposit_percent=0,
        booking_mode="request",
        waiver_text="I agree",
        waiver_version=1,
    )
    db.add(facility)
    db.flush()
    admin = User(
        name="Ada", phone="9100000001", password_hash=hash_password("password1")
    )
    parent = User(
        name="Pat", phone="9100000002", password_hash=hash_password("password1")
    )
    db.add_all([admin, parent])
    db.flush()
    db.add_all(
        [
            Membership(user_id=admin.id, facility_id=facility.id, role="admin"),
            Membership(user_id=parent.id, facility_id=facility.id, role="parent"),
        ]
    )
    dog = Dog(
        facility_id=facility.id,
        name="Rex",
        breed="Retriever",
        age_years=4,
        weight_kg=28,
        vaccination_status="expired",
        owner_name="Pat",
        owner_phone="9100000002",
        owner_user_id=parent.id,
        diet="kibble",
        medications="none",
        vet_contact="Dr. Mehta",
    )
    db.add(dog)
    db.flush()
    open_kennel = Kennel(facility_id=facility.id, name="K-01", status="available")
    taken = Kennel(facility_id=facility.id, name="K-02", status="available")
    db.add_all([open_kennel, taken])
    db.commit()
    ids = {
        "dog_id": dog.id,
        "open_kennel": open_kennel.id,
        "taken_kennel": taken.id,
    }
    db.close()
    return ids


def _login(client, phone):
    res = client.post(
        "/auth/login",
        json={"phone": phone, "password": "password1", "facility_slug": "floor"},
    )
    assert res.status_code == 200, res.text


def _book(client, dog_id, start, end):
    return client.post(
        "/bookings",
        json={
            "dog_id": dog_id,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "waiver_accepted": True,
        },
    )


def test_expired_vaccination_blocks_until_admin_override(client):
    ids = _world()
    _login(client, "9100000002")
    start = date.today() + timedelta(days=10)
    end = start + timedelta(days=2)
    blocked = _book(client, ids["dog_id"], start, end)
    assert blocked.status_code == 422
    assert "Vaccination" in blocked.json()["detail"]

    client.post("/auth/logout")
    _login(client, "9100000001")
    overridden = client.post(
        "/bookings/override",
        json={
            "dog_id": ids["dog_id"],
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "waiver_accepted": True,
            "override": True,
            "override_reason": "Vet letter on file",
        },
    )
    assert overridden.status_code == 201, overridden.text
    assert overridden.json()["status"] == "requested"


def test_accept_confirm_checkin_and_kennel_overlap(client):
    ids = _world()
    db = SessionLocal()
    dog = db.get(Dog, ids["dog_id"])
    db.add(
        VaccinationRecord(
            facility_id=dog.facility_id,
            dog_id=dog.id,
            vaccine_type="core",
            expires_on=date.today() + timedelta(days=200),
        )
    )
    db.commit()
    db.close()

    _login(client, "9100000002")
    start = date.today()
    end = start + timedelta(days=3)
    created = _book(client, ids["dog_id"], start, end)
    assert created.status_code == 201, created.text
    booking_id = created.json()["id"]
    assert created.json()["status"] == "requested"

    client.post("/auth/logout")
    _login(client, "9100000001")
    accepted = client.post(
        f"/bookings/{booking_id}/decision", json={"action": "accept"}
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "confirmed"

    missing = client.patch(
        f"/bookings/{booking_id}/status",
        json={"status": "checked_in"},
    )
    assert missing.status_code == 422

    checked = client.patch(
        f"/bookings/{booking_id}/status",
        json={
            "status": "checked_in",
            "belongings": "bed",
            "diet_confirmed": True,
            "meds_confirmed": True,
            "vet_confirmed": True,
            "kennel_id": ids["open_kennel"],
        },
    )
    assert checked.status_code == 200, checked.text
    assert checked.json()["status"] == "checked_in"

    # A second stay on the same kennel and dates is rejected.
    other = client.post(
        "/bookings/override",
        json={
            "dog_id": ids["dog_id"],
            "start_date": (start + timedelta(days=20)).isoformat(),
            "end_date": (start + timedelta(days=22)).isoformat(),
            "waiver_accepted": True,
            "override": False,
        },
    )
    assert other.status_code == 201, other.text
    other_id = other.json()["id"]
    client.post(f"/bookings/{other_id}/decision", json={"action": "accept"})
    clash = client.post(f"/bookings/{other_id}/kennel?kennel_id={ids['open_kennel']}")
    # Different dates, so the occupied kennel is free later.
    assert clash.status_code == 200, clash.text

    overlap = client.post(
        "/bookings/override",
        json={
            "dog_id": ids["dog_id"],
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "waiver_accepted": True,
        },
    )
    # max_dogs is 1 and the first stay is checked in, so instant path isn't used;
    # request mode still creates a requested booking. Accepting it waitlists.
    assert overlap.status_code == 201
    decision = client.post(
        f"/bookings/{overlap.json()['id']}/decision", json={"action": "accept"}
    )
    assert decision.json()["status"] == "waitlisted"

    same_dates = client.post(
        f"/bookings/{overlap.json()['id']}/kennel?kennel_id={ids['open_kennel']}"
    )
    assert same_dates.status_code == 409
