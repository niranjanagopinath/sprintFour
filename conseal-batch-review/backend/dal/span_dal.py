"""
Data Access Layer for Spans.
"""

from __future__ import annotations
from database import get_db
from typing import List, Optional
import uuid


async def get_spans_for_document(doc_id: str, tier: Optional[str] = None) -> List[dict]:
    """Get all spans for a document, optionally filtered by tier."""
    db = await get_db()
    if tier:
        cursor = await db.execute(
            "SELECT * FROM spans WHERE document_id = ? AND tier = ? ORDER BY char_start",
            (doc_id, tier),
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM spans WHERE document_id = ? ORDER BY char_start",
            (doc_id,),
        )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_span_by_id(span_id: str) -> Optional[dict]:
    """Get a single span by ID."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM spans WHERE id = ?", (span_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def update_span_status(
    span_id: str,
    status: str,
    decided_via: str,
    source_span_id: Optional[str] = None,
    action_mode: Optional[str] = None,
) -> bool:
    """Update a span's decision status and action mode."""
    db = await get_db()
    cursor = await db.execute(
        """UPDATE spans
           SET status = ?, decided_via = ?, source_span_id = ?, action_mode = ?
           WHERE id = ?""",
        (status, decided_via, source_span_id, action_mode, span_id),
    )
    await db.commit()
    return cursor.rowcount > 0


async def find_matching_spans(
    text: str,
    exclude_document_id: Optional[str] = None,
    exclude_span_id: Optional[str] = None,
) -> List[dict]:
    """
    Find spans in other documents with case-insensitive exact text match.
    Used for entity propagation.
    """
    db = await get_db()
    query = """
        SELECT s.*, d.title as document_title
        FROM spans s
        JOIN documents d ON d.id = s.document_id
        WHERE LOWER(s.text) = LOWER(?)
          AND d.state != 'completed'
    """
    params: list = [text]

    if exclude_document_id:
        query += " AND s.document_id != ?"
        params.append(exclude_document_id)

    if exclude_span_id:
        query += " AND s.id != ?"
        params.append(exclude_span_id)

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def find_cluster_matching_spans(
    template_id: str,
    span_type: str,
    char_start: int,
    char_end: int,
    exclude_document_id: str,
    tolerance: int = 10,
) -> List[dict]:
    """
    Find spans in other documents of the same template cluster
    at a similar character position (within tolerance).
    """
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT s.*, d.title as document_title
        FROM spans s
        JOIN documents d ON d.id = s.document_id
        WHERE d.template_id = ?
          AND s.type = ?
          AND ABS(s.char_start - ?) <= ?
          AND ABS(s.char_end - ?) <= ?
          AND s.document_id != ?
          AND d.state != 'completed'
        ORDER BY d.title
        """,
        (template_id, span_type, char_start, tolerance, char_end, tolerance, exclude_document_id),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def create_manual_span(
    document_id: str,
    text: str,
    char_start: int,
    char_end: int,
    span_type: str = "other",
    action_mode: str = "redact",
) -> dict:
    """Create a manually flagged span (Tier 3)."""
    span_id = f"span-manual-{uuid.uuid4().hex[:8]}"
    db = await get_db()
    await db.execute(
        """INSERT INTO spans
           (id, document_id, text, char_start, char_end, type, confidence, tier, reasoning, status, action_mode, decided_via)
           VALUES (?, ?, ?, ?, ?, ?, NULL, 'manual', NULL, 'confirmed', ?, 'manual')""",
        (span_id, document_id, text, char_start, char_end, span_type, action_mode),
    )
    await db.commit()
    return {
        "id": span_id,
        "document_id": document_id,
        "text": text,
        "char_start": char_start,
        "char_end": char_end,
        "type": span_type,
        "confidence": None,
        "tier": "manual",
        "reasoning": None,
        "status": "confirmed",
        "action_mode": action_mode,
        "decided_via": "manual",
        "source_span_id": None,
    }


async def check_all_spans_decided(doc_id: str) -> bool:
    """Check if all non-LLM spans in a document have been decided."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT COUNT(*) as cnt FROM spans
           WHERE document_id = ? AND tier != 'llm' AND status = 'undecided'""",
        (doc_id,),
    )
    row = await cursor.fetchone()
    return row["cnt"] == 0