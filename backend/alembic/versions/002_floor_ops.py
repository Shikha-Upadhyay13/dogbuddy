"""Floor operations: kennels, vaccinations, care logs, booking rules.

Revision ID: 002_floor
Revises: 001_tenant
Create Date: 2026-10-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_floor"
down_revision: Union[str, Sequence[str], None] = "001_tenant"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "facilities",
        sa.Column("booking_mode", sa.String(), nullable=False, server_default="request"),
    )
    op.add_column(
        "facilities",
        sa.Column("deposit_percent", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "facilities",
        sa.Column(
            "cancellation_window_hours",
            sa.Integer(),
            nullable=False,
            server_default="24",
        ),
    )
    op.add_column(
        "facilities",
        sa.Column("max_dogs", sa.Integer(), nullable=False, server_default="30"),
    )
    op.add_column(
        "facilities",
        sa.Column(
            "require_vaccination", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    )
    op.add_column(
        "facilities",
        sa.Column("waiver_text", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "facilities",
        sa.Column("waiver_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "facilities",
        sa.Column(
            "nightly_rate_paise", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.create_table(
        "kennels",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "facility_id", sa.Integer(), sa.ForeignKey("facilities.id"), nullable=False
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="available"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("facility_id", "name", name="uq_kennel_facility_name"),
    )
    op.add_column(
        "bookings",
        sa.Column("assigned_kennel_id", sa.Integer(), sa.ForeignKey("kennels.id")),
    )
    op.add_column("bookings", sa.Column("belongings", sa.Text(), nullable=True))
    op.add_column(
        "bookings",
        sa.Column("diet_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "bookings",
        sa.Column("meds_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "bookings",
        sa.Column("vet_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("bookings", sa.Column("waiver_version_accepted", sa.Integer()))
    op.add_column(
        "bookings",
        sa.Column("vaccination_override_by", sa.Integer(), sa.ForeignKey("users.id")),
    )
    op.add_column("bookings", sa.Column("vaccination_override_reason", sa.Text()))
    op.add_column(
        "incidents",
        sa.Column(
            "parent_visible", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column("incidents", sa.Column("acknowledged_at", sa.DateTime()))
    op.add_column(
        "incidents",
        sa.Column("acknowledged_by", sa.Integer(), sa.ForeignKey("users.id")),
    )
    op.create_table(
        "vaccination_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "facility_id", sa.Integer(), sa.ForeignKey("facilities.id"), nullable=False
        ),
        sa.Column("dog_id", sa.Integer(), sa.ForeignKey("dogs.id"), nullable=False),
        sa.Column("vaccine_type", sa.String(), nullable=False),
        sa.Column("expires_on", sa.Date(), nullable=False),
        sa.Column("file_key", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "care_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "facility_id", sa.Integer(), sa.ForeignKey("facilities.id"), nullable=False
        ),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id"), nullable=False),
        sa.Column("dog_id", sa.Integer(), sa.ForeignKey("dogs.id"), nullable=False),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("photo_key", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("care_logs")
    op.drop_table("vaccination_records")
    op.drop_column("incidents", "acknowledged_by")
    op.drop_column("incidents", "acknowledged_at")
    op.drop_column("incidents", "parent_visible")
    op.drop_column("bookings", "vaccination_override_reason")
    op.drop_column("bookings", "vaccination_override_by")
    op.drop_column("bookings", "waiver_version_accepted")
    op.drop_column("bookings", "vet_confirmed")
    op.drop_column("bookings", "meds_confirmed")
    op.drop_column("bookings", "diet_confirmed")
    op.drop_column("bookings", "belongings")
    op.drop_column("bookings", "assigned_kennel_id")
    op.drop_table("kennels")
    op.drop_column("facilities", "nightly_rate_paise")
    op.drop_column("facilities", "waiver_version")
    op.drop_column("facilities", "waiver_text")
    op.drop_column("facilities", "require_vaccination")
    op.drop_column("facilities", "max_dogs")
    op.drop_column("facilities", "cancellation_window_hours")
    op.drop_column("facilities", "deposit_percent")
    op.drop_column("facilities", "booking_mode")
