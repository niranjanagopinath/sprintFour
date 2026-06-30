"""
Data Access Layer for Documents.
"""

from __future__ import annotations
from database import get_db
from typing import Optional


async def get_documents(
    state: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    priority_weights: Optional[dict] = None,
) -> List[dict]:
    """
    List documents with optional state filter, pagination.
    If priority_weights provided, sort by weighted undecided span importance.
    """
    db = await get_db()
    where = ""
    params: list = []

    if state:
        where = "WHERE d.state = ?"
        params.append(state)

    query = f"""
        SELECT
            d.id, d.title, d.template_id, d.state,
            d.created_at, d.updated_at,
            COUNT(s.id) AS span_count,
            SUM(CASE WHEN s.status != 'undecided' THEN 1 ELSE 0 END) AS decided_count
        FROM documents d
        LEFT JOIN spans s ON s.document_id = d.id AND s.tier != 'llm'
        {where}
        GROUP BY d.id
        ORDER BY
            CASE d.state
                WHEN 'in_review' THEN 0
                WHEN 'pending' THEN 1
                WHEN 'completed' THEN 2
            END,
            d.created_at ASC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_document_by_id(doc_id: str) -> Optional[dict]:
    """Get a single document by ID."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def update_document_state(doc_id: str, state: str) -> bool:
    """Transition a document's state."""
    db = await get_db()
    cursor = await db.execute(
        "UPDATE documents SET state = ?, updated_at = datetime('now') WHERE id = ?",
        (state, doc_id),
    )
    await db.commit()
    return cursor.rowcount > 0


async def count_by_state() -> dict:
    """Count documents by state."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT state, COUNT(*) as cnt FROM documents GROUP BY state"
    )
    rows = await cursor.fetchall()
    result = {"pending": 0, "in_review": 0, "completed": 0}
    for row in rows:
        result[row["state"]] = row["cnt"]
    return result


async def get_total_count() -> int:
    """Total document count."""
    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM documents")
    row = await cursor.fetchone()
    return row["cnt"]