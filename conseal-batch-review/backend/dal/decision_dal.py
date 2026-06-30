"""
Data Access Layer for Decisions (append-only audit log).
"""

from __future__ import annotations
from database import get_db
from typing import List, Optional
import uuid


async def create_decision(
    span_id: str,
    document_id: str,
    action: str,
    decided_via: str,
    confidence_at_decision: Optional[float] = None,
    action_mode: Optional[str] = None,
) -> dict:
    """Create an append-only decision log entry."""
    decision_id = f"dec-{uuid.uuid4().hex[:8]}"
    db = await get_db()
    await db.execute(
        """INSERT INTO decisions
           (id, span_id, document_id, action, action_mode, decided_via, confidence_at_decision)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (decision_id, span_id, document_id, action, action_mode, decided_via, confidence_at_decision),
    )
    await db.commit()
    # Fetch the row back to get the generated timestamp
    cursor = await db.execute("SELECT * FROM decisions WHERE id = ?", (decision_id,))
    row = await cursor.fetchone()
    return dict(row)


async def get_decisions(
    document_id: Optional[str] = None,
    span_type: Optional[str] = None,
    decided_via: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[dict]:
    """
    Query decision log with optional filters.
    Joins to spans table to get type and text info.
    """
    db = await get_db()
    query = """
        SELECT
            dec.id, dec.span_id, dec.document_id, dec.action, dec.action_mode,
            dec.decided_via, dec.confidence_at_decision, dec.timestamp,
            s.text as span_text, s.type as span_type, s.tier as span_tier,
            d.title as document_title
        FROM decisions dec
        JOIN spans s ON s.id = dec.span_id
        JOIN documents d ON d.id = dec.document_id
        WHERE 1=1
    """
    params: list = []

    if document_id:
        query += " AND dec.document_id = ?"
        params.append(document_id)
    if span_type:
        query += " AND s.type = ?"
        params.append(span_type)
    if decided_via:
        query += " AND dec.decided_via = ?"
        params.append(decided_via)

    query += " ORDER BY dec.timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_decision_count(
    document_id: Optional[str] = None,
    span_type: Optional[str] = None,
    decided_via: Optional[str] = None,
) -> int:
    """Count decisions with optional filters."""
    db = await get_db()
    query = """
        SELECT COUNT(*) as cnt
        FROM decisions dec
        JOIN spans s ON s.id = dec.span_id
        WHERE 1=1
    """
    params: list = []

    if document_id:
        query += " AND dec.document_id = ?"
        params.append(document_id)
    if span_type:
        query += " AND s.type = ?"
        params.append(span_type)
    if decided_via:
        query += " AND dec.decided_via = ?"
        params.append(decided_via)

    cursor = await db.execute(query, params)
    row = await cursor.fetchone()
    return row["cnt"]