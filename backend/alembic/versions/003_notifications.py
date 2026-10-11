"""Notifications, report cards, photos metadata, and rate add-ons.

Revision ID: 003_notify
Revises: 002_floor
Create Date: 2026-10-11

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "003_notify"
down_revision: Union[str, Sequence[str], None] = "002_floor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "facilities",
        sa.Column(
            "whatsapp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "facilities",
        sa.Column(
            "email_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.create_table(
        "facility_addons",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "facility_id", sa.Integer(), sa.ForeignKey("facilities.id"), nullable=False
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("price_paise", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "facility_id", sa.Integer(), sa.ForeignKey("facilities.id"), nullable=False
        ),
        sa.Column(
            "recipient_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("link", sa.String(), nullable=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "notification_id",
            sa.Integer(),
            sa.ForeignKey("notifications.id"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "facility_id", sa.Integer(), sa.ForeignKey("facilities.id"), nullable=False
        ),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("whatsapp", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("email", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint(
            "user_id",
            "facility_id",
            "category",
            name="uq_pref_user_facility_category",
        ),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("run_at", sa.DateTime(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.create_table(
        "report_cards",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "facility_id", sa.Integer(), sa.ForeignKey("facilities.id"), nullable=False
        ),
        sa.Column(
            "booking_id", sa.Integer(), sa.ForeignKey("bookings.id"), nullable=False
        ),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("report_cards")
    op.drop_table("jobs")
    op.drop_table("notification_preferences")
    op.drop_table("notification_deliveries")
    op.drop_table("notifications")
    op.drop_table("facility_addons")
    op.drop_column("facilities", "email_enabled")
    op.drop_column("facilities", "whatsapp_enabled")
