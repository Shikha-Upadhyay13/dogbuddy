"""Severe incidents bypass notification preferences. Inboxes stay in-facility."""

from __future__ import annotations

from datetime import date, timedelta

from auth import hash_password
from db import (
    Booking,
    Dog,
    Facility,
    Kennel,
    Membership,
    NotificationDelivery,
    NotificationPreference,
    SessionLocal,
    User,
    VaccinationRecord,
)
from notify import process_due_jobs, scan_due_reminders


def _setup():
    db = SessionLocal()
    facility = Facility(
        name="Notify",
        slug="notify",
        state="Karnataka",
        require_vaccination=False,
        waiver_text="",
        whatsapp_enabled=True,
        email_enabled=True,
        deposit_percent=0,
        booking_mode="instant",
    )
    other = Facility(name="Other", slug="other", state="Kerala", waiver_text="")
    db.add_all([facility, other])
    db.flush()
    admin = User(name="Ada", phone="9200000001", password_hash=hash_password("password1"))
    parent = User(
        name="Pat",
        phone="9200000002",
        email="pat@example.com",
        password_hash=hash_password("password1"),
    )
    outsider = User(
        name="Out", phone="9200000003", password_hash=hash_password("password1")
    )
    db.add_all([admin, parent, outsider])
    db.flush()
    db.add_all(
        [
            Membership(user_id=admin.id, facility_id=facility.id, role="admin"),
            Membership(user_id=parent.id, facility_id=facility.id, role="parent"),
            Membership(user_id=outsider.id, facility_id=other.id, role="admin"),
        ]
    )
    dog = Dog(
        facility_id=facility.id,
        name="Rex",
        breed="Retriever",
        age_years=3,
        weight_kg=20,
        vaccination_status="up_to_date",
        owner_name="Pat",
        owner_phone=parent.phone,
        owner_user_id=parent.id,
        diet="kibble",
        medications="none",
        vet_contact="Dr. Mehta",
    )
    db.add(dog)
    db.flush()
    db.add(
        VaccinationRecord(
            facility_id=facility.id,
            dog_id=dog.id,
            vaccine_type="core",
            expires_on=date.today() + timedelta(days=100),
        )
    )
    kennel = Kennel(facility_id=facility.id, name="K-01", status="available")
    db.add(kennel)
    db.flush()
    booking = Booking(
        facility_id=facility.id,
        dog_id=dog.id,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=2),
        status="checked_in",
        assigned_kennel_id=kennel.id,
        kennel_id=kennel.name,
    )
    db.add(booking)
    db.commit()
    ids = {"dog_id": dog.id, "booking_id": booking.id, "parent_id": parent.id}
    db.close()
    return ids


def _login(client, phone, slug):
    res = client.post(
        "/auth/login",
        json={"phone": phone, "password": "password1", "facility_slug": slug},
    )
    assert res.status_code == 200, res.text


def test_severe_incident_bypasses_opt_out_and_stays_in_facility(client):
    ids = _setup()
    db = SessionLocal()
    pref = NotificationPreference(
        user_id=ids["parent_id"],
        facility_id=db.query(Facility).filter(Facility.slug == "notify").one().id,
        category="incidents",
        whatsapp=False,
        email=False,
    )
    db.add(pref)
    db.commit()
    db.close()

    _login(client, "9200000001", "notify")
    created = client.post(
        "/incidents",
        json={
            "dog_id": ids["dog_id"],
            "type": "health",
            "severity": "severe",
            "description": "Limping badly",
        },
    )
    assert created.status_code == 201, created.text

    db = SessionLocal()
    process_due_jobs(db)
    db.commit()
    whatsapp = (
        db.query(NotificationDelivery)
        .filter(NotificationDelivery.channel == "whatsapp")
        .all()
    )
    assert whatsapp, "forced WhatsApp delivery was not queued"
    db.close()

    client.post("/auth/logout")
    _login(client, "9200000002", "notify")
    inbox = client.get("/notifications")
    assert inbox.status_code == 200
    assert any(row["type"] == "severe_incident" for row in inbox.json())

    client.post("/auth/logout")
    _login(client, "9200000003", "other")
    assert client.get("/notifications").json() == []


def test_report_card_notifies_the_parent(client):
    ids = _setup()
    _login(client, "9200000001", "notify")
    sent = client.post(
        f"/bookings/{ids['booking_id']}/report-cards/send",
        json={"note": "Happy and tired."},
    )
    assert sent.status_code == 200, sent.text
    assert "Happy and tired" in sent.json()["summary"]

    client.post("/auth/logout")
    _login(client, "9200000002", "notify")
    inbox = client.get("/notifications").json()
    assert any(row["type"] == "report_card" for row in inbox)


def test_vaccination_reminder_is_sent_once(client):
    ids = _setup()
    db = SessionLocal()
    facility = db.query(Facility).filter(Facility.slug == "notify").one()
    db.add(
        VaccinationRecord(
            facility_id=facility.id,
            dog_id=ids["dog_id"],
            vaccine_type="rabies",
            expires_on=date.today() + timedelta(days=10),
        )
    )
    db.commit()
    assert scan_due_reminders(db) >= 1
    db.commit()
    first = (
        db.query(NotificationPreference).count()
    )  # preferences are created as a side effect of emit
    assert first >= 1
    again = scan_due_reminders(db)
    db.commit()
    db.close()
    assert again == 0

    _login(client, "9200000002", "notify")
    inbox = client.get("/notifications").json()
    assert any(row["type"] == "vaccination_expiring" for row in inbox)
