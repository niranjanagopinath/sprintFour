from __future__ import annotations
from typing import List
"""
Cluster service — template-based structural clustering.

In this prototype, documents sharing the same template_id form a cluster.
This is pre-computed from the data generator. In production, real clustering
would use text similarity metrics rather than a known template_id.
"""


from dal import document_dal, span_dal
from database import get_db


async def get_cluster_for_document(doc_id: str) -> dict | None:
    """
    Get the template cluster that a document belongs to.
    Returns cluster info with all member documents.
    """
    doc = await document_dal.get_document_by_id(doc_id)
    if not doc:
        return None

    template_id = doc["template_id"]
    db = await get_db()

    cursor = await db.execute(
        """SELECT d.id, d.title, d.template_id, d.state,
                  d.created_at, d.updated_at,
                  COUNT(s.id) as span_count,
                  SUM(CASE WHEN s.status != 'undecided' THEN 1 ELSE 0 END) as decided_count
           FROM documents d
           LEFT JOIN spans s ON s.document_id = d.id AND s.tier != 'llm'
           WHERE d.template_id = ? AND d.id != ?
           GROUP BY d.id
           ORDER BY d.title""",
        (template_id, doc_id),
    )
    rows = await cursor.fetchall()
    members = [dict(r) for r in rows]

    return {
        "template_id": template_id,
        "document_count": len(members),
        "documents": members,
    }


async def find_cluster_matching_spans(
    source_doc_id: str,
    source_span_id: str,
) -> List[dict]:
    """
    Find spans in other cluster members at similar positions.
    Used for applying redaction patterns across a template cluster.
    """
    doc = await document_dal.get_document_by_id(source_doc_id)
    span = await span_dal.get_span_by_id(source_span_id)

    if not doc or not span:
        return []

    matches = await span_dal.find_cluster_matching_spans(
        template_id=doc["template_id"],
        span_type=span["type"],
        char_start=span["char_start"],
        char_end=span["char_end"],
        exclude_document_id=source_doc_id,
        tolerance=10,
    )

    return matches