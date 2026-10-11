"""GST split, frozen quotes, and Razorpay webhook replay."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import date, timedelta

from auth import hash_password
from billing import encrypt_secret, gst_split
from db import Booking, Dog, Facility, Invoice, Membership, Payment, SessionLocal, User


def test_gst_splits_inside_a_state_and_uses_igst_across_states():
    assert gst_split(10000, 1800, "Karnataka", "Karnataka") == (900, 900, 0)
    assert gst_split(10000, 1800, "Karnataka", "Maharashtra") == (0, 0, 1800)


def _money_world():
    db = SessionLocal()
    facility = Facility(
        name="Money",
        slug="money",
        state="Karnataka",
        gstin="29ABCDE1234F1Z5",
        gst_rate_bps=1800,
        deposit_percent=50,
        nightly_rate_paise=100000,
        booking_mode="request",
        require_vaccination=False,
        waiver_text="",
        razorpay_webhook_secret=encrypt_secret("hook-secret"),
    )
    other = Facility(name="Other", slug="money-other", state="Kerala", waiver_text="")
    db.add_all([facility, other])
    db.flush()
    admin = User(name="Ada", phone="9300000001", password_hash=hash_password("password1"))
    parent = User(
        name="Pat",
        phone="9300000002",
        billing_state="Karnataka",
        password_hash=hash_password("password1"),
    )
    outsider = User(
        name="Out", phone="9300000003", password_hash=hash_password("password1")
    )
    attendant = User(
        name="Sam", phone="9300000004", password_hash=hash_password("password1")
    )
    db.add_all([admin, parent, outsider, attendant])
    db.flush()
    db.add_all(
        [
            Membership(user_id=admin.id, facility_id=facility.id, role="admin"),
            Membership(user_id=parent.id, facility_id=facility.id, role="parent"),
            Membership(user_id=outsider.id, facility_id=other.id, role="admin"),
            Membership(user_id=attendant.id, facility_id=facility.id, role="attendant"),
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
    db.commit()
    dog_id = dog.id
    db.close()
    return dog_id


def _login(client, phone, slug="money"):
    res = client.post(
        "/auth/login",
        json={"phone": phone, "password": "password1", "facility_slug": slug},
    )
    assert res.status_code == 200, res.text


def test_quote_survives_a_rate_change_and_webhook_replay_confirms_once(client, monkeypatch):
    monkeypatch.setenv("RAZORPAY_FAKE", "1")
    dog_id = _money_world()
    _login(client, "9300000002")
    start = date.today() + timedelta(days=3)
    created = client.post(
        "/bookings",
        json={
            "dog_id": dog_id,
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=2)).isoformat(),
            "waiver_accepted": True,
        },
    )
    assert created.status_code == 201, created.text
    booking_id = created.json()["id"]

    db = SessionLocal()
    booking = db.get(Booking, booking_id)
    frozen = booking.quote_nightly_paise
    facility = db.get(Facility, booking.facility_id)
    facility.nightly_rate_paise = 1
    db.commit()
    db.refresh(booking)
    assert booking.quote_nightly_paise == frozen == 100000
    db.close()

    client.post("/auth/logout")
    _login(client, "9300000001")
    accepted = client.post(f"/bookings/{booking_id}/decision", json={"action": "accept"})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "awaiting_payment"

    invoices = client.get("/invoices").json()
    deposit = next(row for row in invoices if row["kind"] == "deposit")
    assert deposit["cgst_paise"] == deposit["sgst_paise"]
    assert deposit["igst_paise"] == 0
    assert deposit["cgst_paise"] + deposit["sgst_paise"] + deposit["subtotal_paise"] == deposit[
        "total_paise"
    ]
    original_total = deposit["total_paise"]

    body = json.dumps(
        {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_test_1",
                        "amount": deposit["total_paise"],
                        "notes": {"invoice_id": str(deposit["id"])},
                    }
                }
            },
        }
    ).encode()
    signature = hmac.new(b"hook-secret", body, hashlib.sha256).hexdigest()
    headers = {"x-razorpay-signature": signature, "content-type": "application/json"}
    db = SessionLocal()
    facility_id = db.query(Facility).filter(Facility.slug == "money").one().id
    db.close()
    first = client.post(f"/webhooks/razorpay/{facility_id}", content=body, headers=headers)
    assert first.status_code == 200, first.text
    second = client.post(f"/webhooks/razorpay/{facility_id}", content=body, headers=headers)
    assert second.json()["duplicate"] is True

    db = SessionLocal()
    assert db.get(Booking, booking_id).status == "confirmed"
    assert (
        db.query(Payment).filter(Payment.razorpay_payment_id == "pay_test_1").count() == 1
    )
    invoice = db.get(Invoice, deposit["id"])
    assert invoice.total_paise == original_total
    db.close()

    note = client.post(
        f"/invoices/{deposit['id']}/credit-notes",
        json={"reason": "date change"},
    )
    assert note.status_code == 201, note.text
    assert note.json()["kind"] == "credit_note"
    db = SessionLocal()
    assert db.get(Invoice, deposit["id"]).total_paise == original_total
    db.close()

    client.post("/auth/logout")
    _login(client, "9300000004")
    denied = client.post(
        f"/invoices/{deposit['id']}/payments",
        json={"method": "cash", "amount_paise": 100},
    )
    assert denied.status_code == 403

    client.post("/auth/logout")
    _login(client, "9300000003", "money-other")
    assert client.get("/invoices").json() == []
