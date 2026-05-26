"""Populate the SQLite DB with the exact mock data from PRD Section 5.

Usage:
    python seed.py

Idempotent: drops + recreates all tables on each run so the data stays
exactly as the PRD specifies.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import bcrypt

from db import (
    AuditLog,
    Base,
    Booking,
    Dog,
    Incident,
    SessionLocal,
    Staff,
    engine,
)

TODAY = date.today()
NOW = datetime.now()


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def reset_schema() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed_staff(session):
    staff = Staff(
        name="Anand",
        phone="9999900001",
        password_hash=_hash("dogbuddy123"),
    )
    session.add(staff)
    session.flush()
    return staff


# PRD Section 5: exact 8-dog roster.
DOGS_SPEC = [
    # (name, breed, age, weight, owner, owner_phone, status, notes,
    #  diet, medications, allergies, vaccination_status, vacc_expires_offset_days)
    ("Rex",     "Golden Retriever", 4, 28.0, "Priya Sharma",  "9876543210", "scheduled",
     "Friendly, loves tennis balls",
     "Twice daily kibble, 1.5 cups",        None,             None,           "up_to_date",   180),
    ("Bruno",   "Labrador",         7, 32.0, "Rohit Mehta",   "9876543211", "checked_in",
     "Allergic to chicken",
     "Lamb-based kibble, 2 cups twice/day", None,             "Chicken",      "up_to_date",   240),
    ("Charlie", "Beagle",           3, 12.0, "Ananya Iyer",   "9876543212", "in_care",
     "On daily thyroid medication",
     "Prescription diet, 1 cup twice/day",  "Levothyroxine",  None,           "up_to_date",   120),
    ("Bella",   "German Shepherd",  5, 30.0, "Karan Singh",   "9876543213", "in_care",
     "Reactive to other dogs, walk alone",
     "Large-breed kibble, 2.5 cups twice/day", None,          None,           "up_to_date",   300),
    ("Max",     "Pug",              6,  9.0, "Tara Kapoor",   "9876543214", "in_care",
     "Snores, breathing issues in heat",
     "Brachycephalic diet, 0.75 cup twice/day", None,         None,           "up_to_date",    90),
    ("Luna",    "Indie / Mixed",    2, 18.0, "Sneha Reddy",   "9876543215", "in_care",
     "Recently adopted, shy",
     "Standard kibble, 1.5 cups twice/day", None,             None,           "up_to_date",   200),
    ("Coco",    "Shih Tzu",         8,  6.0, "Vikram Joshi",  "9876543216", "checked_out",
     "Senior dog, gentle handling",
     "Senior wet food, 0.5 cup three times/day", "Glucosamine", None,         "expiring_soon", 14),
    ("Simba",   "Rottweiler",       4, 42.0, "Aisha Khan",    "9876543217", "checked_out",
     "Strong puller on leash",
     "Large-breed kibble, 3 cups twice/day", None,            None,           "expired",      -30),
]


def seed_dogs_and_bookings(session):
    dogs_by_name: dict[str, Dog] = {}
    kennel_counter = 1

    for (
        name, breed, age, weight, owner, owner_phone, status, notes,
        diet, meds, allergies, vacc_status, vacc_offset,
    ) in DOGS_SPEC:
        dog = Dog(
            name=name,
            breed=breed,
            age_years=age,
            weight_kg=weight,
            diet=diet,
            medications=meds,
            allergies=allergies,
            vaccination_status=vacc_status,
            vaccination_expires=TODAY + timedelta(days=vacc_offset),
            owner_name=owner,
            owner_phone=owner_phone,
            vet_contact="Dr. Mehta - 9811122233",
            notes=notes,
        )
        session.add(dog)
        session.flush()
        dogs_by_name[name] = dog

        if status == "scheduled":
            start, end = TODAY, TODAY + timedelta(days=3)
            last_walked = last_fed = last_meds = None
        elif status in ("checked_in", "in_care"):
            start, end = TODAY - timedelta(days=1), TODAY + timedelta(days=2)
        elif status == "checked_out":
            start, end = TODAY - timedelta(days=3), TODAY
            last_walked = last_fed = last_meds = None
        else:
            start, end = TODAY, TODAY

        # Varied activity timestamps for in_care dogs (PRD: "creates 'overdue' feel")
        if status == "in_care":
            if name == "Charlie":
                last_walked = NOW - timedelta(minutes=30)
                last_fed    = NOW - timedelta(hours=6)
                last_meds   = NOW - timedelta(hours=2)
            elif name == "Bella":
                last_walked = NOW - timedelta(hours=2)
                last_fed    = NOW - timedelta(minutes=45)
                last_meds   = None
            elif name == "Max":
                last_walked = NOW - timedelta(hours=6)
                last_fed    = NOW - timedelta(hours=1)
                last_meds   = None
            elif name == "Luna":
                last_walked = NOW - timedelta(hours=1)
                last_fed    = NOW - timedelta(minutes=30)
                last_meds   = None
        elif status == "checked_in":
            last_walked = NOW - timedelta(hours=3)
            last_fed    = NOW - timedelta(hours=2)
            last_meds   = None

        booking = Booking(
            dog_id=dog.id,
            start_date=start,
            end_date=end,
            status=status,
            kennel_id=f"K-{kennel_counter:02d}" if status != "scheduled" else None,
            last_walked_at=last_walked,
            last_fed_at=last_fed,
            last_meds_at=last_meds,
        )
        session.add(booking)
        kennel_counter += 1

    session.flush()
    return dogs_by_name


def seed_incidents(session, dogs_by_name, staff_id: int):
    incidents = [
        Incident(
            dog_id=dogs_by_name["Charlie"].id,
            staff_id=staff_id,
            type="health",
            severity="mild",
            description="Skipped breakfast this morning",
            created_at=NOW - timedelta(hours=2),
        ),
        Incident(
            dog_id=dogs_by_name["Bella"].id,
            staff_id=staff_id,
            type="behavior",
            severity="moderate",
            description="Growled at Max during morning walk overlap",
            created_at=NOW - timedelta(days=1),
        ),
        Incident(
            dog_id=dogs_by_name["Max"].id,
            staff_id=staff_id,
            type="health",
            severity="mild",
            description="Heavy panting after outdoor time, moved to AC area",
            created_at=NOW - timedelta(days=1),
        ),
    ]
    session.add_all(incidents)


def main() -> None:
    print("-> Resetting schema...")
    reset_schema()

    session = SessionLocal()
    try:
        print("-> Seeding staff...")
        staff = seed_staff(session)

        print("-> Seeding dogs + bookings...")
        dogs_by_name = seed_dogs_and_bookings(session)

        print("-> Seeding incidents...")
        seed_incidents(session, dogs_by_name, staff.id)

        session.commit()

        # Verification summary
        from sqlalchemy import select, func
        n_dogs = session.scalar(select(func.count()).select_from(Dog))
        n_bookings = session.scalar(select(func.count()).select_from(Booking))
        n_incidents = session.scalar(select(func.count()).select_from(Incident))
        print(f"OK Seed complete: 1 staff, {n_dogs} dogs, {n_bookings} bookings, {n_incidents} incidents")
        print("   Login -> phone: 9999900001  password: dogbuddy123")
    finally:
        session.close()


if __name__ == "__main__":
    main()
