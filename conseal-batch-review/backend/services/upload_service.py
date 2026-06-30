"""
Upload service for ingesting PDFs, performing OCR, and triggering detection.
"""

import asyncio
import io
import os
import uuid
import fitz  # PyMuPDF
from database import get_db

# Try to import pytesseract, it may fail if not installed or configured
try:
    import pytesseract
    from PIL import Image
    # On Windows the binary is not on PATH by default
    import os as _os
    _tess = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if _os.path.exists(_tess):
        pytesseract.pytesseract.tesseract_cmd = _tess
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


async def process_upload(filename: str, file_bytes: bytes, batch_id: str) -> str:
    """
    Process an uploaded PDF file.
    Extracts text, falls back to OCR if it's a raster PDF, and creates a Document record.
    Returns the document ID.
    """
    # Run CPU-bound extraction in a thread pool (compatible with Python 3.8)
    loop = asyncio.get_event_loop()
    doc_data = await loop.run_in_executor(None, _extract_text, filename, file_bytes)
    
    doc_id = f"doc-{uuid.uuid4().hex[:8]}"
    
    db = await get_db()
    await db.execute(
        """INSERT INTO documents 
           (id, title, raw_text, state, source_type, file_type, ocr_used, ocr_confidence, batch_id) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            doc_id, 
            doc_data["title"], 
            doc_data["raw_text"], 
            "pending", 
            "uploaded", 
            doc_data["file_type"], 
            doc_data["ocr_used"], 
            doc_data["ocr_confidence"],
            batch_id
        ),
    )
    await db.commit()
    
    # Trigger Tier 1 detection asynchronously (fire and forget)
    from services.detection_service import run_tier1_detection
    asyncio.create_task(run_tier1_detection(doc_id, doc_data["raw_text"]))
    
    return doc_id


def _extract_text(filename: str, file_bytes: bytes) -> dict:
    """
    Extract text using PyMuPDF (fitz), with Tesseract OCR fallback for raster PDFs.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    
    text = ""
    for page in doc:
        text += page.get_text("text") + "\\n"
        
    num_pages = len(doc)
    text_length = len(text.strip())
    
    ocr_used = False
    ocr_confidence = None
    
    # Threshold for raster classification: < 50 chars per page
    if text_length / max(num_pages, 1) < 50:
        if not OCR_AVAILABLE:
            text = "[ERROR] Raster PDF detected but Tesseract OCR is not available."
        else:
            ocr_used = True
            ocr_text = ""
            confidences = []
            
            for page in doc:
                pix = page.get_pixmap(dpi=150)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                
                try:
                    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                    for i in range(len(data['text'])):
                        word = data['text'][i].strip()
                        if word:
                            conf = int(data['conf'][i])
                            if conf >= 0:
                                confidences.append(conf)
                                
                    page_text = pytesseract.image_to_string(img)
                    ocr_text += page_text + "\\n"
                except Exception as e:
                    print(f"OCR Error on page: {e}")
                    
            text = ocr_text
            if confidences:
                ocr_confidence = sum(confidences) / len(confidences) / 100.0
            else:
                ocr_confidence = 0.0
                
    doc.close()
            
    return {
        "title": filename,
        "raw_text": text.strip(),
        "file_type": "raster" if ocr_used else "digital",
        "ocr_used": ocr_used,
        "ocr_confidence": ocr_confidence,
    }
