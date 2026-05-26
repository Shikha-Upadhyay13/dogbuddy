"""Tiny helper for writing audit_log rows.

Every state-changing endpoint and every agent tool MUST call write_audit
so that audit_log is a complete record of who did what, when.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from db import AuditLog


def write_audit(
    db: Session,
    *,
    staff_id: int,
    action: str,
    target_type: str,
    target_id: int,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """Insert one audit_log row. Caller is responsible for committing."""
    row = AuditLog(
        staff_id=staff_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=json.dumps(details) if details is not None else None,
    )
    db.add(row)
    db.flush()
    return row
