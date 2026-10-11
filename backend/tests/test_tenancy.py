"""A user of facility A cannot read or write facility B, including via tools."""

from __future__ import annotations

from datetime import date, timedelta

from agent.tools import make_tools
from auth import hash_password
from db import Booking, Dog, Facility, Membership, SessionLocal, User


def _seed_two_facilities():
    db = SessionLocal()
    a = Facility(name="Alpha Kennel", slug="alpha", state="Karnataka")
    b = Facility(name="Beta Kennel", slug="beta", state="Maharashtra")
    db.add_all([a, b])
    db.flush()
    admin_a = User(
        name="Asha", phone="9000000001", password_hash=hash_password("password1")
    )
    admin_b = User(
        name="Bala", phone="9000000002", password_hash=hash_password("password1")
    )
    db.add_all([admin_a, admin_b])
    db.flush()
    db.add_all(
        [
            Membership(user_id=admin_a.id, facility_id=a.id, role="admin"),
            Membership(user_id=admin_b.id, facility_id=b.id, role="admin"),
        ]
    )
    dog = Dog(
        facility_id=a.id,
        name="Rex",
        breed="Retriever",
        age_years=4,
        weight_kg=28,
        vaccination_status="up_to_date",
        owner_name="Priya",
        owner_phone="9876543210",
    )
    db.add(dog)
    db.flush()
    booking = Booking(
        facility_id=a.id,
        dog_id=dog.id,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=2),
        status="scheduled",
    )
    db.add(booking)
    db.commit()
    ids = {
        "dog_id": dog.id,
        "booking_id": booking.id,
        "admin_b_id": admin_b.id,
        "facility_b_id": b.id,
    }
    db.close()
    return ids


def _login(client, phone, slug):
    res = client.post(
        "/auth/login",
        json={"phone": phone, "password": "password1", "facility_slug": slug},
    )
    assert res.status_code == 200, res.text
    return res.json()["user"]


def test_other_facility_cannot_read_or_write_dog(client):
    ids = _seed_two_facilities()
    _login(client, "9000000002", "beta")

    assert client.get(f"/dogs/{ids['dog_id']}").status_code == 404
    assert client.get("/dogs").json() == []
    incident = client.post(
        "/incidents",
        json={
            "dog_id": ids["dog_id"],
            "type": "health",
            "severity": "mild",
            "description": "should not land",
        },
    )
    assert incident.status_code == 404
    status = client.patch(
        f"/bookings/{ids['booking_id']}/status",
        json={"status": "checked_in"},
    )
    assert status.status_code == 404


def test_chat_tools_stay_inside_the_facility(client):
    ids = _seed_two_facilities()
    tools = {
        t.name: t
        for t in make_tools(ids["admin_b_id"], ids["facility_b_id"], "admin")
    }
    found = tools["query_db"].invoke(
        {"query_type": "dog_by_name", "params": {"name": "Rex"}}
    )
    assert "No dog named" in found
    updated = tools["update_status"].invoke({"dog_name": "Rex", "action": "check_in"})
    assert "No dog named" in updated


def test_password_reset_and_invite_are_scoped(client):
    _seed_two_facilities()
    _login(client, "9000000001", "alpha")

    reset = client.post("/auth/password-reset/request", json={"phone": "9000000001"})
    assert reset.status_code == 200
    code = reset.json()["debug_code"]
    assert code
    confirmed = client.post(
        "/auth/password-reset/confirm",
        json={"phone": "9000000001", "code": code, "password": "password1"},
    )
    assert confirmed.status_code == 200

    invite = client.post(
        "/team/invites",
        json={"name": "Nia", "phone": "9000000003", "role": "attendant"},
    )
    assert invite.status_code == 201, invite.text
    accepted = client.post(
        "/auth/accept-invite",
        json={
            "phone": "9000000003",
            "code": invite.json()["code"],
            "password": "password1",
            "facility_slug": "alpha",
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["user"]["role"] == "attendant"
    assert accepted.json()["user"]["facility_slug"] == "alpha"

    # The new attendant's session must not see Beta, and a Beta login still
    # cannot see Alpha's dog.
    client.post("/auth/logout")
    _login(client, "9000000002", "beta")
    dogs = client.get("/dogs")
    assert dogs.status_code == 200
    assert dogs.json() == []
