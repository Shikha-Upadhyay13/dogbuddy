"""Tenant foundation: users, facilities, memberships.

Revision ID: 001_tenant
Revises:
Create Date: 2026-10-11

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "001_tenant"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("phone"),
    )
    op.create_table(
        "facilities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("timezone", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "memberships",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "facility_id", sa.Integer(), sa.ForeignKey("facilities.id"), nullable=False
        ),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "user_id", "facility_id", name="uq_membership_user_facility"
        ),
    )
    op.create_table(
        "one_time_codes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("phone", sa.String(), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column(
            "facility_id", sa.Integer(), sa.ForeignKey("facilities.id"), nullable=True
        ),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_one_time_codes_phone", "one_time_codes", ["phone"])
    op.create_table(
        "dogs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "facility_id", sa.Integer(), sa.ForeignKey("facilities.id"), nullable=False
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("breed", sa.String(), nullable=False),
        sa.Column("age_years", sa.Integer(), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=False),
        sa.Column("diet", sa.String(), nullable=True),
        sa.Column("medications", sa.String(), nullable=True),
        sa.Column("allergies", sa.String(), nullable=True),
        sa.Column("vaccination_status", sa.String(), nullable=False),
        sa.Column("vaccination_expires", sa.Date(), nullable=True),
        sa.Column("owner_name", sa.String(), nullable=False),
        sa.Column("owner_phone", sa.String(), nullable=False),
        sa.Column(
            "owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("vet_contact", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "facility_id", sa.Integer(), sa.ForeignKey("facilities.id"), nullable=False
        ),
        sa.Column("dog_id", sa.Integer(), sa.ForeignKey("dogs.id"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("kennel_id", sa.String(), nullable=True),
        sa.Column("last_walked_at", sa.DateTime(), nullable=True),
        sa.Column("last_fed_at", sa.DateTime(), nullable=True),
        sa.Column("last_meds_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "facility_id", sa.Integer(), sa.ForeignKey("facilities.id"), nullable=False
        ),
        sa.Column("dog_id", sa.Integer(), sa.ForeignKey("dogs.id"), nullable=False),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "facility_id", sa.Integer(), sa.ForeignKey("facilities.id"), nullable=False
        ),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("details", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("incidents")
    op.drop_table("bookings")
    op.drop_table("dogs")
    op.drop_index("ix_one_time_codes_phone", table_name="one_time_codes")
    op.drop_table("one_time_codes")
    op.drop_table("memberships")
    op.drop_table("facilities")
    op.drop_table("users")
