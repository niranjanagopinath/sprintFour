"""
Export service - applies confirmed redactions to a document's text.
"""
from database import get_db
import io
import zipfile

async def export_document(doc_id: str) -> str:
    """Export the document with confirmed redactions applied."""
    db = await get_db()
    
    async with db.execute("SELECT raw_text FROM documents WHERE id = ?", (doc_id,)) as cursor:
        row = await cursor.fetchone()
        
    if not row:
        return None
        
    raw_text = row["raw_text"]
    
    # Get confirmed spans
    async with db.execute(
        "SELECT * FROM spans WHERE document_id = ? AND status = 'confirmed' ORDER BY char_start DESC", 
        (doc_id,)
    ) as cursor:
        rows = await cursor.fetchall()
        
    spans = [dict(r) for r in rows]
    
    # Remove overlapping spans before applying, keep the one with earlier start (or same start, later end)
    # Wait, we are iterating backwards, so we should filter them first
    # Actually, sorting by char_start ASC, then processing to remove overlaps
    spans.sort(key=lambda s: (s["char_start"], -s["char_end"]))
    non_overlapping = []
    last_end = -1
    for s in spans:
        if s["char_start"] >= last_end:
            non_overlapping.append(s)
            last_end = s["char_end"]
            
    # Now reverse to apply from end to start
    non_overlapping.sort(key=lambda s: s["char_start"], reverse=True)
    
    result_text = raw_text
    
    for span in non_overlapping:
        start = span["char_start"]
        end = span["char_end"]
        action_mode = span.get("action_mode") or "redact"
        
        if action_mode == "anonymize":
            # Fetch pseudonym
            async with db.execute(
                "SELECT pseudonym FROM pseudonym_map WHERE entity_text_normalized = ? AND type = ?",
                (span["text"].lower().strip(), span["type"])
            ) as p_cursor:
                p_row = await p_cursor.fetchone()
                if p_row:
                    replacement = p_row["pseudonym"]
                else:
                    replacement = "[REDACTED]"
        else:
            replacement = "[REDACTED]"
            
        result_text = result_text[:start] + replacement + result_text[end:]
        
    return result_text


async def export_all_documents() -> bytes:
    """
    Exports all documents (redacted) and packages them into a ZIP file in memory.
    Returns the ZIP file bytes.
    """
    db = await get_db()
    
    # Get all document IDs
    async with db.execute("SELECT id, title FROM documents") as cursor:
        rows = await cursor.fetchall()
        
    if not rows:
        return b""
        
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for row in rows:
            doc_id = row["id"]
            title = row["title"]
            # Get redacted text
            redacted_text = await export_document(doc_id)
            if redacted_text:
                # Add to ZIP
                filename = f"{title}_redacted.txt"
                # Clean up filename for zip (replace slashes, etc if needed, though they shouldn't exist)
                filename = "".join(c for c in filename if c.isalnum() or c in (' ', '.', '_', '-')).strip()
                zip_file.writestr(filename, redacted_text)
                
    return zip_buffer.getvalue()
