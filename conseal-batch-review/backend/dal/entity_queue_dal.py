"""
Data Access Layer for the Entity Review Queue.
Groups spans by (text, type) to surface high-leverage entities first.
"""

from __future__ import annotations
import uuid
from database import get_db
from typing import List


async def get_entity_queue(show_singletons: bool = False) -> List[dict]:
    """
    Return entity groups that still have undecided spans, sorted by
    occurrence_count (distinct undecided documents) descending.
    Filters to occurrence_count >= 2 unless show_singletons is True.
    """
    db = await get_db()
    min_count = 1 if show_singletons else 2
    cursor = await db.execute(
        """
        WITH entity_stats AS (
            SELECT
                LOWER(s.text)  AS entity_key,
                MIN(s.text)    AS entity_text,
                s.type,
                COUNT(DISTINCT CASE WHEN s.status = 'undecided' THEN s.document_id END)
                               AS occurrence_count,
                COUNT(DISTINCT s.document_id) AS total_docs,
                SUM(CASE WHEN s.status = 'undecided' THEN 1 ELSE 0 END) AS undecided_span_count,
                SUM(CASE WHEN s.status != 'undecided' THEN 1 ELSE 0 END) AS decided_span_count,
                MIN(CASE WHEN s.status = 'undecided' THEN s.document_id END) AS first_doc_id,
                MIN(CASE WHEN s.status = 'undecided' THEN s.char_start END)  AS first_char_start
            FROM spans s
            WHERE s.tier != 'manual'
            GROUP BY LOWER(s.text), s.type
            HAVING undecided_span_count > 0 AND occurrence_count >= ?
        )
        SELECT
            es.entity_key,
            es.entity_text,
            es.type         AS entity_type,
            es.occurrence_count,
            es.total_docs,
            es.undecided_span_count,
            es.first_doc_id,
            CASE WHEN es.decided_span_count > 0 THEN 'partially_decided' ELSE 'undecided' END AS status,
            SUBSTR(d.raw_text, MAX(1, es.first_char_start - 40), 120) AS snippet,
            bae.note        AS note
        FROM entity_stats es
        JOIN documents d ON d.id = es.first_doc_id
        LEFT JOIN batch_audit_events bae ON bae.id = (
            SELECT id FROM batch_audit_events
            WHERE LOWER(entity_text) = es.entity_key
              AND entity_type = es.type
              AND event_type = 'spot_check_failed_aborted'
            ORDER BY timestamp DESC LIMIT 1
        )
        ORDER BY es.occurrence_count DESC
        """,
        (min_count,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_undecided_spans_for_entity(entity_text: str, entity_type: str) -> List[dict]:
    """All undecided spans for a given entity text + type, with document context."""
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT s.*,
               d.title AS document_title,
               SUBSTR(d.raw_text, MAX(1, s.char_start - 40), 120) AS snippet
        FROM spans s
        JOIN documents d ON d.id = s.document_id
        WHERE LOWER(s.text) = LOWER(?) AND s.type = ? AND s.status = 'undecided'
        ORDER BY d.title
        """,
        (entity_text, entity_type),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_entity_stats() -> dict:
    """Aggregate entity resolution stats for the Batch Progress Panel."""
    db = await get_db()

    cursor = await db.execute(
        """
        SELECT
            COUNT(DISTINCT LOWER(text) || '|' || type) AS total_entities,
            COUNT(DISTINCT CASE WHEN status = 'undecided' THEN LOWER(text) || '|' || type END)
                                                        AS pending_entities
        FROM spans
        WHERE tier != 'manual'
        """
    )
    row = await cursor.fetchone()
    total = row["total_entities"] or 0
    pending = row["pending_entities"] or 0

    cursor2 = await db.execute(
        """
        SELECT decided_via, COUNT(*) AS cnt
        FROM decisions
        WHERE decided_via IN ('propagated', 'manual', 'cluster', 'spot_check')
        GROUP BY decided_via
        """
    )
    rows2 = await cursor2.fetchall()
    counts = {r["decided_via"]: r["cnt"] for r in rows2}

    return {
        "total_entities": total,
        "resolved_entities": total - pending,
        "pending_entities": pending,
        "propagated_decisions": (
            counts.get("propagated", 0)
            + counts.get("cluster", 0)
            + counts.get("spot_check", 0)
        ),
        "manual_decisions": counts.get("manual", 0),
    }


async def write_batch_audit_event(
    event_type: str, entity_text: str, entity_type: str, note: str
) -> None:
    db = await get_db()
    event_id = f"bae-{uuid.uuid4().hex[:8]}"
    await db.execute(
        "INSERT INTO batch_audit_events (id, event_type, entity_text, entity_type, note) VALUES (?, ?, ?, ?, ?)",
        (event_id, event_type, entity_text, entity_type, note),
    )
    await db.commit()
