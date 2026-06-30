"""
Data access layer for the PseudonymMap.
"""
import uuid
from database import get_db

def normalize_text(text: str) -> str:
    """Normalize text for consistent mapping."""
    return text.lower().strip()

async def get_or_create_pseudonym(entity_text: str, entity_type: str, doc_id: str) -> str:
    """
    Get an existing pseudonym for this entity text, or create one.

    Lookup is by normalized text ONLY — type is ignored on lookup so that
    the same name always gets the same pseudonym regardless of which model
    tagged it (Presidio → 'name', Ollama → 'other', etc.).
    """
    db = await get_db()
    norm_text = normalize_text(entity_text)

    # Look up by text alone — reuse whatever pseudonym already exists for this text
    async with db.execute(
        "SELECT pseudonym FROM pseudonym_map WHERE entity_text_normalized = ?",
        (norm_text,)
    ) as cursor:
        row = await cursor.fetchone()

    if row:
        return row["pseudonym"]

    # Nothing found — generate a new pseudonym keyed to the canonical type
    type_caps = entity_type.capitalize()
    if type_caps == "Ssn":
        type_caps = "SSN"

    # Count existing pseudonyms of this display type for the suffix number
    async with db.execute(
        "SELECT COUNT(*) as count FROM pseudonym_map WHERE type = ?", (entity_type,)
    ) as cursor:
        row = await cursor.fetchone()
        count = row["count"]

    new_pseudo = f"[{type_caps}_{count + 1}]"
    pseudo_id = f"pseudo-{uuid.uuid4().hex[:8]}"

    try:
        await db.execute(
            """INSERT INTO pseudonym_map
               (id, entity_text_normalized, type, pseudonym, first_seen_document_id)
               VALUES (?, ?, ?, ?, ?)""",
            (pseudo_id, norm_text, entity_type, new_pseudo, doc_id),
        )
        await db.commit()
    except Exception:
        # Race condition — another request inserted first; fetch what's there
        async with db.execute(
            "SELECT pseudonym FROM pseudonym_map WHERE entity_text_normalized = ?",
            (norm_text,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return row["pseudonym"]

    return new_pseudo
