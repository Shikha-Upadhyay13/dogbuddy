"""SQLAlchemy models and session factory.

Production data lives in Postgres (`DATABASE_URL`). Tests pin a throwaway
SQLite file before this module is imported. `create_all` matches the models;
Alembic revisions are the upgrade path for databases that already exist.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://dogbuddy:dogbuddy@localhost:5432/dogbuddy",
)

engine = create_engine(
    DATABASE_URL,
    connect_args=(
        {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
    ),
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now()


class User(Base):
    """A person. Which facility they belong to, and as whom, is a membership."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    billing_state: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="user")


class Facility(Base):
    __tablename__ = "facilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String, nullable=False, default="Karnataka")
    phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    timezone: Mapped[str] = mapped_column(
        String, nullable=False, default="Asia/Kolkata"
    )
    booking_mode: Mapped[str] = mapped_column(String, nullable=False, default="request")
    deposit_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancellation_window_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=24
    )
    max_dogs: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    require_vaccination: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    waiver_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    waiver_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    nightly_rate_paise: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    whatsapp_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    gstin: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    gst_rate_bps: Mapped[int] = mapped_column(Integer, nullable=False, default=1800)
    razorpay_key_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    razorpay_key_secret: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    razorpay_webhook_secret: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_invoice_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="facility")


class Membership(Base):
    """Role is scoped to one facility: admin, attendant, or parent."""

    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "facility_id", name="uq_membership_user_facility"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)

    user: Mapped["User"] = relationship(back_populates="memberships")
    facility: Mapped["Facility"] = relationship(back_populates="memberships")


class OneTimeCode(Base):
    """Hashed OTP for password reset and staff invites."""

    __tablename__ = "one_time_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String, nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String, nullable=False)
    code_hash: Mapped[str] = mapped_column(String, nullable=False)
    facility_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("facilities.id"), nullable=True
    )
    role: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class Dog(Base):
    __tablename__ = "dogs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    breed: Mapped[str] = mapped_column(String, nullable=False)
    age_years: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    diet: Mapped[Optional[str]] = mapped_column(String)
    medications: Mapped[Optional[str]] = mapped_column(String)
    allergies: Mapped[Optional[str]] = mapped_column(String)
    vaccination_status: Mapped[str] = mapped_column(String, nullable=False)
    vaccination_expires: Mapped[Optional[date]] = mapped_column(Date)
    owner_name: Mapped[str] = mapped_column(String, nullable=False)
    owner_phone: Mapped[str] = mapped_column(String, nullable=False)
    owner_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    vet_contact: Mapped[Optional[str]] = mapped_column(String)
    notes: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)

    bookings: Mapped[list["Booking"]] = relationship(back_populates="dog")
    incidents: Mapped[list["Incident"]] = relationship(back_populates="dog")
    vaccinations: Mapped[list["VaccinationRecord"]] = relationship(back_populates="dog")


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"), nullable=False
    )
    dog_id: Mapped[int] = mapped_column(ForeignKey("dogs.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    kennel_id: Mapped[Optional[str]] = mapped_column(String)
    assigned_kennel_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kennels.id"), nullable=True
    )
    belongings: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    diet_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    meds_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    vet_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    waiver_version_accepted: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    vaccination_override_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    vaccination_override_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    quote_saved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quote_nights: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quote_nightly_paise: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quote_addons_paise: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quote_subtotal_paise: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    quote_tax_paise: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quote_total_paise: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    selected_addon_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_walked_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_fed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_meds_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)

    dog: Mapped["Dog"] = relationship(back_populates="bookings")


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"), nullable=False
    )
    dog_id: Mapped[int] = mapped_column(ForeignKey("dogs.id"), nullable=False)
    staff_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    parent_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)

    dog: Mapped["Dog"] = relationship(back_populates="incidents")


class Kennel(Base):
    __tablename__ = "kennels"
    __table_args__ = (
        UniqueConstraint("facility_id", "name", name="uq_kennel_facility_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="available")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class VaccinationRecord(Base):
    __tablename__ = "vaccination_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"), nullable=False
    )
    dog_id: Mapped[int] = mapped_column(ForeignKey("dogs.id"), nullable=False)
    vaccine_type: Mapped[str] = mapped_column(String, nullable=False)
    expires_on: Mapped[date] = mapped_column(Date, nullable=False)
    file_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)

    dog: Mapped["Dog"] = relationship(back_populates="vaccinations")


class CareLog(Base):
    __tablename__ = "care_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"), nullable=False
    )
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), nullable=False)
    dog_id: Mapped[int] = mapped_column(ForeignKey("dogs.id"), nullable=False)
    staff_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    photo_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class FacilityAddon(Base):
    __tablename__ = "facility_addons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    price_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"), nullable=False
    )
    recipient_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    notification_id: Mapped[int] = mapped_column(
        ForeignKey("notifications.id"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "facility_id",
            "category",
            name="uq_pref_user_facility_category",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"), nullable=False
    )
    category: Mapped[str] = mapped_column(String, nullable=False)
    whatsapp: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    run_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ReportCard(Base):
    __tablename__ = "report_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"), nullable=False
    )
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class Invoice(Base):
    """Issued invoices are immutable. A correction is a new credit-note row."""

    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("facility_id", "number", name="uq_invoice_facility_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"), nullable=False
    )
    booking_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bookings.id"), nullable=True
    )
    original_invoice_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("invoices.id"), nullable=True
    )
    number: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="issued")
    subtotal_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    cgst_paise: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sgst_paise: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    igst_paise: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    place_of_supply: Mapped[str] = mapped_column(String, nullable=False)
    customer_state: Mapped[str] = mapped_column(String, nullable=False)
    pdf_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    payment_link: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"), nullable=False
    )
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[str] = mapped_column(String, nullable=False)
    razorpay_payment_id: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, unique=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="captured")
    recorded_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"), nullable=False
    )
    payment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("payments.id"), nullable=True
    )
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"), nullable=False
    )
    staff_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    target_type: Mapped[str] = mapped_column(String, nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    details: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


def init_db() -> None:
    """Create any missing tables. Safe to call repeatedly."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """FastAPI dependency: yields a session and closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
