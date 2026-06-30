"""
Detection service — Tier 1 (Presidio + GLiNER) + Tier 2 (LLM).

Model loading strategy:
  - Presidio: loaded eagerly at import time (fast, pure-Python).
  - GLiNER:   lazy-loaded on first use to avoid slowing startup.
"""

import asyncio
import uuid
import re
import logging
from typing import Optional
from database import get_db

# Limit concurrent detection runs so heavy model inference doesn't starve the
# event loop or exhaust RAM. Defaults to the CPU core count (capped 5–12); model
# inference releases the GIL so real cores translate to real parallelism.
import os as _os
from concurrent.futures import ThreadPoolExecutor

# Presidio/spaCy NER is largely GIL-bound, so more threads than ~5 oversubscribe
# the GIL and slow the batch down rather than speeding it up. 5 is the measured
# sweet spot; override with DETECTION_CONCURRENCY if running on a beefier box.
_DETECTION_CONCURRENCY = int(_os.environ.get("DETECTION_CONCURRENCY", 5))
_DETECTION_SEMAPHORE: asyncio.Semaphore | None = None
_DETECTION_POOL: ThreadPoolExecutor | None = None

def _get_semaphore() -> asyncio.Semaphore:
    global _DETECTION_SEMAPHORE
    if _DETECTION_SEMAPHORE is None:
        _DETECTION_SEMAPHORE = asyncio.Semaphore(_DETECTION_CONCURRENCY)
    return _DETECTION_SEMAPHORE

def _get_pool() -> ThreadPoolExecutor:
    """Dedicated 5-worker pool so detection threads never queue behind
    other run_in_executor(None, ...) calls on the shared default pool."""
    global _DETECTION_POOL
    if _DETECTION_POOL is None:
        _DETECTION_POOL = ThreadPoolExecutor(
            max_workers=_DETECTION_CONCURRENCY,
            thread_name_prefix="detect",
        )
    return _DETECTION_POOL

log = logging.getLogger(__name__)

# ── Lazy model registry ──────────────────────────────────────────────────────
# Both models are loaded on first use inside a thread-pool executor so the
# server starts and responds immediately; the CPU-heavy loading never blocks
# the event loop.

import threading

_presidio: Optional[object] = None
_presidio_attempted = False
_presidio_lock = threading.Lock()

_gliner: Optional[object] = None
_gliner_attempted = False
_gliner_lock = threading.Lock()


def _load_presidio():
    global _presidio, _presidio_attempted
    if _presidio_attempted:
        return _presidio
    # Lock so 5 concurrent detection threads don't each load the model.
    with _presidio_lock:
        if _presidio_attempted:
            return _presidio
        _presidio_attempted = True
        try:
            from presidio_analyzer import AnalyzerEngine
            _presidio = AnalyzerEngine()
            log.info("Presidio loaded OK")
        except Exception as exc:
            log.warning("Presidio unavailable (%s) — regex fallback active", exc)
    return _presidio


def _load_gliner():
    global _gliner, _gliner_attempted
    if _gliner_attempted:
        return _gliner
    with _gliner_lock:
        if _gliner_attempted:
            return _gliner
        _gliner_attempted = True
        try:
            from gliner import GLiNER
            _gliner = GLiNER.from_pretrained("urchade/gliner_medium-v2.1")
            log.info("GLiNER loaded OK")
        except Exception as exc:
            log.warning("GLiNER unavailable (%s)", exc)
    return _gliner


async def prewarm_models() -> None:
    """Load Presidio + GLiNER (and run a tiny inference) at startup so the
    first real documents don't pay the cold-load + JIT cost. Runs in the
    detection pool so server startup isn't blocked on the event loop."""
    def _warm():
        p = _load_presidio()
        g = _load_gliner()
        sample = "John Smith lives in Mumbai. Aadhaar 1234 5678 9012."
        try:
            if p:
                p.analyze(text=sample, entities=_PRESIDIO_ENTITIES, language="en")
            if g:
                g.predict_entities(sample, _GLINER_LABELS, threshold=0.4)
        except Exception as exc:
            log.warning("Model prewarm inference failed: %s", exc)
        log.info("Models pre-warmed (concurrency=%d)", _DETECTION_CONCURRENCY)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_get_pool(), _warm)


# Entity-type mapping
_PRESIDIO_TYPE_MAP = {
    "PERSON":          "name",
    "PHONE_NUMBER":    "phone",
    "EMAIL_ADDRESS":   "other",
    "US_SSN":          "ssn",
    "LOCATION":        "address",
    "ORGANIZATION":    "other",
}

_PRESIDIO_ENTITIES = list(_PRESIDIO_TYPE_MAP.keys())

_GLINER_LABELS = ["person", "address", "location", "organization"]
_GLINER_TYPE_MAP = {
    "person":       "name",
    "address":      "address",
    "location":     "address",
    "organization": "other",
}

# Regex fallback patterns (when Presidio not available)
_REGEX_PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),         "ssn",   0.80),
    (re.compile(r"\(\d{3}\)\s?\d{3}-\d{4}"),         "phone", 0.80),
    (re.compile(r"\b\d{3}[.\-]\d{3}[.\-]\d{4}\b"),   "phone", 0.75),
    (re.compile(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b"),     "name",  0.50),
]

# Indian PII patterns — always run regardless of whether Presidio is available
_INDIA_PATTERNS = [
    # Aadhaar: 12 digits, optionally grouped as XXXX XXXX XXXX
    (re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b"),                       "ssn",   0.95),
    (re.compile(r"\b\d{12}\b"),                                      "ssn",   0.85),
    # PAN: 5 uppercase letters, 4 digits, 1 uppercase letter
    (re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),                     "ssn",   0.95),
    # Indian mobile: +91 or 0 prefix, 10 digits
    (re.compile(r"\b(?:\+91|91|0)?[6-9]\d{9}\b"),                   "phone", 0.85),
    # Passport: one letter followed by 7 digits
    (re.compile(r"\b[A-Z]\d{7}\b"),                                  "ssn",   0.80),
    # Voter ID (EPIC): 3 uppercase letters + 7 digits
    (re.compile(r"\b[A-Z]{3}\d{7}\b"),                               "ssn",   0.80),
    # Driving licence: state code + digits (e.g. MH1234567890123)
    (re.compile(r"\b[A-Z]{2}\d{2}\s?\d{4}\s?\d{7}\b"),              "ssn",   0.80),
    # GST: 15-char alphanumeric with known structure
    (re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z0-9]\b"),      "ssn",   0.90),
    # IFSC code: 4 uppercase letters, 0, 6 alphanumeric
    (re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"),                       "other", 0.85),
    # UPI ID: word@word
    (re.compile(r"\b[\w.\-]+@[a-z]{2,}\b"),                         "other", 0.80),
    # Bank account numbers: 9–18 consecutive digits (not already matched as Aadhaar)
    (re.compile(r"\b\d{9,18}\b"),                                    "ssn",   0.60),
]

# Names embedded in URLs, emails, file paths, slugs — always run
_LINK_PATTERNS = [
    # Email address (full): name.surname@domain or name@domain
    (re.compile(
        r"\b[a-zA-Z][a-zA-Z0-9._%+\-]{1,40}@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"
    ), "other", 0.90),

    # URL containing a name-like slug: /firstname-lastname or /firstname.lastname
    # Matches path segments that look like two capitalisable words joined by - or .
    (re.compile(
        r"https?://[^\s]*?/([a-z]{2,20}[-_.][a-z]{2,20})(?:[/?#\s]|$)",
        re.IGNORECASE,
    ), "name", 0.80),

    # Bare slug in text that looks like a name (two words separated by hyphen/dot/underscore)
    # e.g. "john-smith", "rajesh.kumar", "priya_verma"
    (re.compile(
        r"\b([a-z]{2,15}[-_.][a-z]{2,15})\b",
        re.IGNORECASE,
    ), "name", 0.65),

    # File name with a name: firstname_lastname_anything.ext
    (re.compile(
        r"\b([A-Za-z]{2,15}[_\-][A-Za-z]{2,15}[_\-][^\s]{0,30}\.[a-zA-Z]{2,5})\b"
    ), "name", 0.70),

    # WhatsApp / Telegram style links with phone numbers
    (re.compile(r"wa\.me/(\+?[0-9]{10,15})"), "phone", 0.95),

    # tel: URI
    (re.compile(r"tel:(\+?[0-9\s\-]{7,15})"), "phone", 0.95),

    # mailto: URI
    (re.compile(r"mailto:([^\s\"'>]+)"), "other", 0.95),
]


async def run_tier1_detection(doc_id: str, text: str):
    """Run Presidio + GLiNER + Ollama on document text, throttled to 5 concurrent jobs."""

    def _run_models() -> list[dict]:
        results: list[dict] = []

        # ── Presidio (lazy) ─────────────────────────────────────────────────
        presidio = _load_presidio()
        if presidio:
            try:
                hits = presidio.analyze(
                    text=text,
                    entities=_PRESIDIO_ENTITIES,
                    language="en",
                )
                for h in hits:
                    results.append({
                        "text":       text[h.start:h.end],
                        "char_start": h.start,
                        "char_end":   h.end,
                        "type":       _PRESIDIO_TYPE_MAP.get(h.entity_type, "other"),
                        "confidence": round(h.score, 3),
                        "source":     "presidio",
                    })
            except Exception as exc:
                log.error("Presidio analysis failed: %s", exc)
        else:
            for pattern, etype, conf in _REGEX_PATTERNS:
                for m in pattern.finditer(text):
                    results.append({
                        "text":       m.group(0),
                        "char_start": m.start(),
                        "char_end":   m.end(),
                        "type":       etype,
                        "confidence": conf,
                        "source":     "regex",
                    })

        # ── GLiNER (lazy) ────────────────────────────────────────────────────
        gliner = _load_gliner()
        if gliner:
            try:
                entities = gliner.predict_entities(text, _GLINER_LABELS, threshold=0.4)
                for ent in entities:
                    results.append({
                        "text":       ent["text"],
                        "char_start": ent["start"],
                        "char_end":   ent["end"],
                        "type":       _GLINER_TYPE_MAP.get(ent["label"], "other"),
                        "confidence": round(ent["score"], 3),
                        "source":     "gliner",
                    })
            except Exception as exc:
                log.error("GLiNER prediction failed: %s", exc)

        # ── Indian PII + link/URL patterns (always run) ─────────────────────
        for pattern, etype, conf in _INDIA_PATTERNS + _LINK_PATTERNS:
            for m in pattern.finditer(text):
                matched_text = m.group(1) if m.lastindex else m.group(0)
                char_start   = m.start(1) if m.lastindex else m.start()
                char_end     = m.end(1)   if m.lastindex else m.end()
                if len(matched_text.strip()) < 2:
                    continue
                results.append({
                    "text":       matched_text,
                    "char_start": char_start,
                    "char_end":   char_end,
                    "type":       etype,
                    "confidence": conf,
                    "source":     "regex",
                })

        return results

    async with _get_semaphore():
        import time
        t0 = time.monotonic()
        db = await get_db()
        await db.execute(
            "UPDATE documents SET detection_started_at = datetime('now') WHERE id = ?", (doc_id,)
        )
        await db.commit()
        log.info("Detection slot acquired for doc %s", doc_id)

        loop = asyncio.get_event_loop()
        raw_spans = await loop.run_in_executor(_get_pool(), _run_models)

        # ── De-overlap: sort by start, prefer higher confidence on ties ──────
        raw_spans.sort(key=lambda s: (s["char_start"], -s["confidence"], s["char_end"]))
        filtered: list[dict] = []
        last_end = -1
        for span in raw_spans:
            if span["char_start"] >= last_end:
                filtered.append(span)
                last_end = span["char_end"]

        if filtered:
            for span in filtered:
                span_id = f"span-{uuid.uuid4().hex[:8]}"
                await db.execute(
                    """INSERT INTO spans
                       (id, document_id, text, char_start, char_end, type, confidence,
                        tier, source, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        span_id, doc_id,
                        span["text"], span["char_start"], span["char_end"],
                        span["type"], span["confidence"],
                        "structured", span["source"], "undecided",
                    ),
                )
            elapsed = time.monotonic() - t0
            await db.execute(
                """UPDATE documents
                   SET detection_completed_at = datetime('now'), span_count = ?
                   WHERE id = ?""",
                (len(filtered), doc_id),
            )
            await db.commit()
            log.info("Stored %d spans for doc %s in %.1fs", len(filtered), doc_id, elapsed)

        # ── Tier 2: context-aware LLM detection (Ollama) ─────────────────────
        tier1_span_dicts = [
            {"text": s["text"], "type": s["type"],
             "char_start": s["char_start"], "char_end": s["char_end"]}
            for s in filtered
        ]

    # Ollama runs OUTSIDE the semaphore — it's network I/O, not CPU
    from services.llm_tier_service import run_context_detection
    asyncio.create_task(run_context_detection(doc_id, text, tier1_span_dicts))
