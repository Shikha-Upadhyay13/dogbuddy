"""Quotes, GST invoices, payments, and the ledger.

Revision ID: 004_money
Revises: 003_notify
Create Date: 2026-10-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_money"
down_revision: Union[str, Sequence[str], None] = "003_notify"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("billing_state", sa.String(), nullable=True))
    op.add_column("facilities", sa.Column("gstin", sa.String(), nullable=True))
    op.add_column(
        "facilities",
        sa.Column("gst_rate_bps", sa.Integer(), nullable=False, server_default="1800"),
    )
    op.add_column("facilities", sa.Column("razorpay_key_id", sa.String(), nullable=True))
    op.add_column(
        "facilities", sa.Column("razorpay_key_secret", sa.Text(), nullable=True)
    )
    op.add_column(
        "facilities", sa.Column("razorpay_webhook_secret", sa.Text(), nullable=True)
    )
    op.add_column(
        "facilities",
        sa.Column(
            "next_invoice_number", sa.Integer(), nullable=False, server_default="1"
        ),
    )
    op.add_column(
        "bookings",
        sa.Column("quote_saved", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    for name, type_ in (
        ("quote_nights", sa.Integer()),
        ("quote_nightly_paise", sa.Integer()),
        ("quote_addons_paise", sa.Integer()),
        ("quote_subtotal_paise", sa.Integer()),
        ("quote_tax_paise", sa.Integer()),
        ("quote_total_paise", sa.Integer()),
    ):
        op.add_column(
            "bookings",
            sa.Column(name, type_, nullable=False, server_default="0"),
        )
    op.add_column(
        "bookings", sa.Column("selected_addon_ids", sa.Text(), nullable=True)
    )
    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "facility_id", sa.Integer(), sa.ForeignKey("facilities.id"), nullable=False
        ),
        sa.Column(
            "booking_id", sa.Integer(), sa.ForeignKey("bookings.id"), nullable=True
        ),
        sa.Column("original_invoice_id", sa.Integer(), nullable=True),
        sa.Column("number", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("subtotal_paise", sa.Integer(), nullable=False),
        sa.Column("cgst_paise", sa.Integer(), nullable=False),
        sa.Column("sgst_paise", sa.Integer(), nullable=False),
        sa.Column("igst_paise", sa.Integer(), nullable=False),
        sa.Column("total_paise", sa.Integer(), nullable=False),
        sa.Column("place_of_supply", sa.String(), nullable=False),
        sa.Column("customer_state", sa.String(), nullable=False),
        sa.Column("pdf_key", sa.String(), nullable=True),
        sa.Column("payment_link", sa.String(), nullable=True),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("facility_id", "number", name="uq_invoice_facility_number"),
    )
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "facility_id", sa.Integer(), sa.ForeignKey("facilities.id"), nullable=False
        ),
        sa.Column(
            "invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=False
        ),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("razorpay_payment_id", sa.String(), nullable=True, unique=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("recorded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "facility_id", sa.Integer(), sa.ForeignKey("facilities.id"), nullable=False
        ),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id"), nullable=True),
        sa.Column(
            "invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=False
        ),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ledger_entries")
    op.drop_table("payments")
    op.drop_table("invoices")
