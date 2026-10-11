"""Quotes, GST invoices, Razorpay, and the payment ledger.

A quote is frozen on the booking. Later rate changes do not rewrite it.
Issued invoices are never updated; a correction is a credit note.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import date, datetime

import httpx
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from audit import write_audit
from db import (
    Booking,
    Facility,
    FacilityAddon,
    Invoice,
    LedgerEntry,
    Payment,
    User,
)
from notify import emit, staff_users
from storage import save_bytes, signed_path


class BillingError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _fernet() -> Fernet:
    raw = hashlib.sha256(
        os.getenv("JWT_SECRET", "change-me-in-prod").encode("utf-8")
    ).digest()
    return Fernet(base64.urlsafe_b64encode(raw))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str | None) -> str:
    if not value:
        return ""
    return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")


def gst_split(
    subtotal_paise: int, rate_bps: int, facility_state: str, customer_state: str
) -> tuple[int, int, int]:
    """Return CGST, SGST, IGST. Same state splits the tax; other states are IGST."""
    tax = subtotal_paise * rate_bps // 10000
    supply = (customer_state or facility_state).strip().lower()
    if supply == facility_state.strip().lower():
        cgst = tax // 2
        return cgst, tax - cgst, 0
    return 0, 0, tax


def _nights(start: date, end: date) -> int:
    return max((end - start).days, 1)


def freeze_quote(db: Session, facility: Facility, booking: Booking) -> None:
    if booking.quote_saved:
        return
    addon_ids = []
    if booking.selected_addon_ids:
        addon_ids = json.loads(booking.selected_addon_ids)
    addon_sum = 0
    if addon_ids:
        rows = (
            db.query(FacilityAddon)
            .filter(
                FacilityAddon.facility_id == facility.id,
                FacilityAddon.id.in_(addon_ids),
            )
            .all()
        )
        addon_sum = sum(row.price_paise for row in rows)
    count = _nights(booking.start_date, booking.end_date)
    subtotal = count * facility.nightly_rate_paise + addon_sum
    _cgst, _sgst, _igst = gst_split(
        subtotal,
        facility.gst_rate_bps,
        facility.state,
        _customer_state(db, facility, booking),
    )
    booking.quote_nights = count
    booking.quote_nightly_paise = facility.nightly_rate_paise
    booking.quote_addons_paise = addon_sum
    booking.quote_subtotal_paise = subtotal
    booking.quote_tax_paise = _cgst + _sgst + _igst
    booking.quote_total_paise = subtotal + booking.quote_tax_paise
    booking.quote_saved = True
    db.flush()


def _customer_state(db: Session, facility: Facility, booking: Booking) -> str:
    owner_id = booking.dog.owner_user_id if booking.dog else None
    owner = db.get(User, owner_id) if owner_id else None
    if owner is not None and owner.billing_state:
        return owner.billing_state
    return facility.state


def _next_number(facility: Facility) -> str:
    number = f"{datetime.now().year}-{facility.next_invoice_number:04d}"
    facility.next_invoice_number += 1
    return number


def _pdf(invoice: Invoice, facility: Facility) -> bytes:
    lines = [
        f"Tax invoice {invoice.number}",
        f"Facility {facility.name}",
        f"GSTIN {facility.gstin or 'unregistered'}",
        f"Place of supply {invoice.place_of_supply}",
        f"Customer state {invoice.customer_state}",
        f"Subtotal paise {invoice.subtotal_paise}",
        f"CGST paise {invoice.cgst_paise}",
        f"SGST paise {invoice.sgst_paise}",
        f"IGST paise {invoice.igst_paise}",
        f"Total paise {invoice.total_paise}",
        f"Kind {invoice.kind}",
    ]
    return _simple_pdf(lines)


def _simple_pdf(lines: list[str]) -> bytes:
    commands = ["BT", "/F1 11 Tf", "50 780 Td"]
    for index, line in enumerate(lines):
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if index:
            commands.append("0 -16 Td")
        commands.append(f"({safe}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1", errors="replace")
    objects = [
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n",
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n",
        b"4 0 obj<< /Length "
        + str(len(stream)).encode()
        + b" >>stream\n"
        + stream
        + b"\nendstream endobj\n",
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n",
    ]
    chunks = [b"%PDF-1.4\n"]
    offsets = [0]
    for obj in objects:
        offsets.append(sum(len(part) for part in chunks))
        chunks.append(obj)
    xref = sum(len(part) for part in chunks)
    xref_body = [f"xref\n0 {len(offsets)}\n".encode(), b"0000000000 65535 f \n"]
    for offset in offsets[1:]:
        xref_body.append(f"{offset:010d} 00000 n \n".encode())
    trailer = (
        f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    ).encode()
    return b"".join(chunks + xref_body + [trailer])


def _issue(
    db: Session,
    *,
    facility: Facility,
    booking: Booking,
    kind: str,
    subtotal_paise: int,
    actor_id: int,
    original: Invoice | None = None,
) -> Invoice:
    customer_state = _customer_state(db, facility, booking)
    cgst, sgst, igst = gst_split(
        subtotal_paise, facility.gst_rate_bps, facility.state, customer_state
    )
    if kind == "credit_note":
        cgst, sgst, igst, subtotal_paise = -cgst, -sgst, -igst, -abs(subtotal_paise)
    invoice = Invoice(
        facility_id=facility.id,
        booking_id=booking.id,
        original_invoice_id=original.id if original else None,
        number=_next_number(facility),
        kind=kind,
        status="issued",
        subtotal_paise=subtotal_paise,
        cgst_paise=cgst,
        sgst_paise=sgst,
        igst_paise=igst,
        total_paise=subtotal_paise + cgst + sgst + igst,
        place_of_supply=facility.state,
        customer_state=customer_state,
    )
    db.add(invoice)
    db.flush()
    invoice.pdf_key = save_bytes(facility.id, f"invoice-{invoice.number}.pdf", _pdf(invoice, facility))
    if kind == "deposit" and invoice.total_paise > 0:
        invoice.payment_link = create_payment_link(facility, invoice)
    db.flush()
    write_audit(
        db,
        facility_id=facility.id,
        staff_id=actor_id,
        action="issue_invoice",
        target_type="invoice",
        target_id=invoice.id,
        details={"number": invoice.number, "kind": kind, "total": invoice.total_paise},
    )
    parent = _parent(db, booking)
    if parent is not None:
        emit(
            db,
            facility=facility,
            recipients=[parent],
            event="invoice_issued",
            title=f"Invoice {invoice.number}",
            body=f"{invoice.kind} for {invoice.total_paise} paise.",
            link="/owner/dashboard",
        )
    return invoice


def _parent(db: Session, booking: Booking) -> User | None:
    owner_id = booking.dog.owner_user_id if booking.dog else None
    return db.get(User, owner_id) if owner_id else None


def _existing(db: Session, booking: Booking, kind: str) -> Invoice | None:
    return (
        db.query(Invoice)
        .filter(Invoice.booking_id == booking.id, Invoice.kind == kind)
        .order_by(Invoice.id)
        .first()
    )


def create_payment_link(facility: Facility, invoice: Invoice) -> str:
    key_id = facility.razorpay_key_id
    secret = decrypt_secret(facility.razorpay_key_secret)
    if not key_id or not secret or os.getenv("RAZORPAY_FAKE") == "1":
        return f"https://rzp.io/i/test-{invoice.id}"
    response = httpx.post(
        "https://api.razorpay.com/v1/payment_links",
        auth=(key_id, secret),
        json={
            "amount": invoice.total_paise,
            "currency": "INR",
            "description": f"DogBuddy {invoice.number}",
            "notes": {"invoice_id": str(invoice.id), "facility_id": str(facility.id)},
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json().get("short_url") or f"https://rzp.io/i/test-{invoice.id}"


def sync_booking_money(
    db: Session, facility: Facility, booking: Booking, actor_id: int
) -> None:
    freeze_quote(db, facility, booking)
    if booking.status == "awaiting_payment" and _existing(db, booking, "deposit") is None:
        deposit = booking.quote_total_paise * facility.deposit_percent // 100
        if deposit > 0:
            subtotal = deposit * 10000 // (10000 + facility.gst_rate_bps)
            _issue(
                db,
                facility=facility,
                booking=booking,
                kind="deposit",
                subtotal_paise=subtotal,
                actor_id=actor_id,
            )
    elif (
        booking.status == "confirmed"
        and facility.deposit_percent == 0
        and _existing(db, booking, "invoice") is None
    ):
        _issue(
            db,
            facility=facility,
            booking=booking,
            kind="invoice",
            subtotal_paise=booking.quote_subtotal_paise,
            actor_id=actor_id,
        )
    elif booking.status == "checked_out":
        paid = _captured_total(db, booking)
        balance = booking.quote_total_paise - paid
        if balance > 0 and _existing(db, booking, "balance") is None:
            subtotal = balance * 10000 // (10000 + facility.gst_rate_bps)
            _issue(
                db,
                facility=facility,
                booking=booking,
                kind="balance",
                subtotal_paise=subtotal,
                actor_id=actor_id,
            )


def _captured_total(db: Session, booking: Booking) -> int:
    invoices = db.query(Invoice).filter(Invoice.booking_id == booking.id).all()
    if not invoices:
        return 0
    ids = [row.id for row in invoices]
    payments = (
        db.query(Payment)
        .filter(Payment.invoice_id.in_(ids), Payment.status == "captured")
        .all()
    )
    return sum(row.amount_paise for row in payments)


def _confirm_if_deposit_met(db: Session, invoice: Invoice) -> None:
    if invoice.kind != "deposit" or invoice.booking_id is None:
        return
    booking = db.get(Booking, invoice.booking_id)
    if booking is None or booking.status != "awaiting_payment":
        return
    paid = (
        db.query(Payment)
        .filter(Payment.invoice_id == invoice.id, Payment.status == "captured")
        .all()
    )
    if sum(row.amount_paise for row in paid) >= invoice.total_paise:
        booking.status = "confirmed"


def record_payment(
    db: Session,
    *,
    facility: Facility,
    invoice: Invoice,
    amount_paise: int,
    method: str,
    actor_id: int,
    razorpay_payment_id: str | None = None,
) -> Payment:
    if method not in ("cash", "upi", "razorpay"):
        raise BillingError(422, "Unknown payment method")
    if method in ("cash", "upi") and actor_id <= 0:
        raise BillingError(403, "Manual payments are admin-only")
    if razorpay_payment_id:
        existing = (
            db.query(Payment)
            .filter(Payment.razorpay_payment_id == razorpay_payment_id)
            .one_or_none()
        )
        if existing is not None:
            return existing
    payment = Payment(
        facility_id=facility.id,
        invoice_id=invoice.id,
        amount_paise=amount_paise,
        method=method,
        razorpay_payment_id=razorpay_payment_id,
        status="captured",
        recorded_by=actor_id or None,
    )
    db.add(payment)
    db.flush()
    db.add(
        LedgerEntry(
            facility_id=facility.id,
            payment_id=payment.id,
            invoice_id=invoice.id,
            kind="charge",
            amount_paise=amount_paise,
            note=method,
        )
    )
    if method in ("cash", "upi"):
        write_audit(
            db,
            facility_id=facility.id,
            staff_id=actor_id,
            action="record_payment",
            target_type="payment",
            target_id=payment.id,
            details={"method": method, "amount_paise": amount_paise},
        )
    _confirm_if_deposit_met(db, invoice)
    parent = _parent(db, db.get(Booking, invoice.booking_id)) if invoice.booking_id else None
    recipients = staff_users(db, facility.id)
    if parent is not None:
        recipients = recipients + [parent]
    emit(
        db,
        facility=facility,
        recipients=recipients,
        event="payment_received",
        title="Payment received",
        body=f"{amount_paise} paise via {method}.",
        link="/owner/dashboard",
    )
    return payment


def handle_webhook(
    db: Session, facility_id: int, body: bytes, signature: str
) -> dict:
    facility = db.get(Facility, facility_id)
    if facility is None:
        raise BillingError(404, "Facility not found")
    secret = decrypt_secret(facility.razorpay_webhook_secret)
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not secret or not hmac.compare_digest(expected, signature or ""):
        raise BillingError(400, "Invalid Razorpay signature")
    payload = json.loads(body)
    entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    payment_id = entity.get("id")
    notes = entity.get("notes") or {}
    invoice_id = int(notes.get("invoice_id") or 0)
    invoice = db.get(Invoice, invoice_id)
    if invoice is None or invoice.facility_id != facility.id or not payment_id:
        raise BillingError(422, "Payment does not match an invoice")
    event = payload.get("event")
    if event == "payment.failed":
        existing = (
            db.query(Payment)
            .filter(Payment.razorpay_payment_id == payment_id)
            .one_or_none()
        )
        if existing is not None:
            return {"ok": True, "duplicate": True}
        db.add(
            Payment(
                facility_id=facility.id,
                invoice_id=invoice.id,
                amount_paise=int(entity.get("amount") or 0),
                method="razorpay",
                razorpay_payment_id=payment_id,
                status="failed",
            )
        )
        parent = _parent(db, db.get(Booking, invoice.booking_id)) if invoice.booking_id else None
        recipients = staff_users(db, facility.id)
        if parent is not None:
            recipients.append(parent)
        emit(
            db,
            facility=facility,
            recipients=recipients,
            event="payment_failed",
            title="Payment failed",
            body=f"Razorpay payment {payment_id} failed.",
        )
        return {"ok": True}
    if event != "payment.captured":
        return {"ok": True, "ignored": True}
    existing = (
        db.query(Payment)
        .filter(Payment.razorpay_payment_id == payment_id)
        .one_or_none()
    )
    if existing is not None:
        return {"ok": True, "duplicate": True}
    record_payment(
        db,
        facility=facility,
        invoice=invoice,
        amount_paise=int(entity.get("amount") or invoice.total_paise),
        method="razorpay",
        actor_id=0,
        razorpay_payment_id=payment_id,
    )
    return {"ok": True}


def issue_credit_note(
    db: Session, facility: Facility, invoice: Invoice, actor_id: int, reason: str
) -> Invoice:
    if invoice.facility_id != facility.id:
        raise BillingError(404, "Invoice not found")
    if invoice.kind == "credit_note":
        raise BillingError(422, "A credit note cannot be credited again")
    booking = db.get(Booking, invoice.booking_id)
    if booking is None:
        raise BillingError(422, "Invoice is not attached to a stay")
    note = _issue(
        db,
        facility=facility,
        booking=booking,
        kind="credit_note",
        subtotal_paise=abs(invoice.subtotal_paise),
        actor_id=actor_id,
        original=invoice,
    )
    db.add(
        LedgerEntry(
            facility_id=facility.id,
            invoice_id=note.id,
            kind="credit_note",
            amount_paise=note.total_paise,
            note=reason,
        )
    )
    return note


def refund_payment(
    db: Session, facility: Facility, payment: Payment, actor_id: int, amount_paise: int
) -> LedgerEntry:
    if payment.facility_id != facility.id:
        raise BillingError(404, "Payment not found")
    if amount_paise <= 0 or amount_paise > payment.amount_paise:
        raise BillingError(422, "Refund amount is outside the payment")
    if payment.method == "razorpay":
        _razorpay_refund(facility, payment, amount_paise)
    entry = LedgerEntry(
        facility_id=facility.id,
        payment_id=payment.id,
        invoice_id=payment.invoice_id,
        kind="refund",
        amount_paise=-amount_paise,
        note="admin refund",
    )
    db.add(entry)
    if amount_paise == payment.amount_paise:
        payment.status = "refunded"
    write_audit(
        db,
        facility_id=facility.id,
        staff_id=actor_id,
        action="refund",
        target_type="payment",
        target_id=payment.id,
        details={"amount_paise": amount_paise},
    )
    db.flush()
    return entry


def _razorpay_refund(facility: Facility, payment: Payment, amount_paise: int) -> None:
    if os.getenv("RAZORPAY_FAKE") == "1":
        return
    key_id = facility.razorpay_key_id
    secret = decrypt_secret(facility.razorpay_key_secret)
    if not key_id or not secret or not payment.razorpay_payment_id:
        raise BillingError(409, "Razorpay is not configured for this facility")
    response = httpx.post(
        f"https://api.razorpay.com/v1/payments/{payment.razorpay_payment_id}/refund",
        auth=(key_id, secret),
        json={"amount": amount_paise},
        timeout=20,
    )
    if response.status_code >= 400:
        raise BillingError(502, "Razorpay refused the refund")


def invoice_out(invoice: Invoice) -> dict:
    return {
        "id": invoice.id,
        "booking_id": invoice.booking_id,
        "number": invoice.number,
        "kind": invoice.kind,
        "status": invoice.status,
        "subtotal_paise": invoice.subtotal_paise,
        "cgst_paise": invoice.cgst_paise,
        "sgst_paise": invoice.sgst_paise,
        "igst_paise": invoice.igst_paise,
        "total_paise": invoice.total_paise,
        "place_of_supply": invoice.place_of_supply,
        "customer_state": invoice.customer_state,
        "payment_link": invoice.payment_link,
        "pdf_url": signed_path(invoice.pdf_key) if invoice.pdf_key else None,
    }
