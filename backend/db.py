"""SQLAlchemy 2.0 models and session factory for DogBuddy.

Schema source of truth: PRD Section 4. Do not change column names/types
without updating the PRD first.
"""

from __future__ import annotations

import os
from datetime import datetime, date
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Float,
    String,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
    Session,
)

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dogbuddy.db")

# SQLite needs check_same_thread=False so FastAPI can share connections across threads.
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


class Staff(Base):
    """The `staff` table now stores BOTH facility staff and dog owners.
    `role` distinguishes: 'staff' = facility user (Anand etc.), 'owner' =
    a dog owner who self-registered via /auth/signup.

    Kept the table name `staff` for backward compat with existing data and
    foreign keys, even though semantically it's now "users".
    """

    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="owner")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class Dog(Base):
    __tablename__ = "dogs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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
    # Links the dog to a user-mode owner account, if the owner self-registered.
    # NULL for legacy / seeded dogs (visible only to staff).
    owner_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff.id"), nullable=True
    )
    vet_contact: Mapped[Optional[str]] = mapped_column(String)
    notes: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)

    bookings: Mapped[list["Booking"]] = relationship(back_populates="dog")
    incidents: Mapped[list["Incident"]] = relationship(back_populates="dog")


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dog_id: Mapped[int] = mapped_column(ForeignKey("dogs.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    kennel_id: Mapped[Optional[str]] = mapped_column(String)
    last_walked_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_fed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_meds_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)

    dog: Mapped["Dog"] = relationship(back_populates="bookings")


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dog_id: Mapped[int] = mapped_column(ForeignKey("dogs.id"), nullable=False)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)

    dog: Mapped["Dog"] = relationship(back_populates="incidents")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id"), nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    target_type: Mapped[str] = mapped_column(String, nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    details: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


def init_db() -> None:
    """Create all tables. Safe to call repeatedly."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """FastAPI dependency: yields a session and closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
