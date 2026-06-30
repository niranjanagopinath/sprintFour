"""
LLM Tier service — context-aware PII detection via Ollama.

Presidio and GLiNER are pattern/NER models — they find obvious PII tokens
(names, SSNs, phone numbers) but have no understanding of the document.

Ollama reads the FULL document and finds things that are only sensitive
IN CONTEXT:
  - Dates that are only sensitive because they're someone's admission date
  - Relationship mentions ("his sister", "the claimant's employer")
  - Medical/financial details that slip past keyword matching
  - Anything that, combined with the document's subject matter, could
    identify or harm the person being discussed

Runs automatically after Tier 1 on every upload. Fails silently if
Ollama is not running — the document is still reviewed with Tier 1 spans.
"""

import os
import json
import uuid
import asyncio
import logging
from typing import List

import aiohttp

from config import OLLAMA_URL, OLLAMA_MODEL
from database import get_db

log = logging.getLogger(__name__)

# How long to wait for Ollama before giving up (seconds)
_OLLAMA_TIMEOUT = 90

# The local LLM is heavy (a 20B-class model pegs the CPU). In a 200-doc batch we
# must NOT fire 200 concurrent Ollama calls — that starves the Tier-1 detection
# threads and tanks throughput. Throttle to a small number of in-flight calls.
_OLLAMA_CONCURRENCY = int(os.environ.get("OLLAMA_CONCURRENCY", 2))
_OLLAMA_SEMAPHORE: asyncio.Semaphore | None = None


def _ollama_sem() -> asyncio.Semaphore:
    global _OLLAMA_SEMAPHORE
    if _OLLAMA_SEMAPHORE is None:
        _OLLAMA_SEMAPHORE = asyncio.Semaphore(_OLLAMA_CONCURRENCY)
    return _OLLAMA_SEMAPHORE


async def run_context_detection(doc_id: str, text: str, tier1_spans: List[dict]) -> None:
    """
    Send the full document to Ollama for context-aware detection.
    Stores any new spans that don't overlap with Tier 1 hits.
    Called automatically after Tier 1 completes on upload.
    Throttled to a few concurrent calls so it never starves Tier-1.
    """
    async with _ollama_sem():
        await _run_context_detection_inner(doc_id, text, tier1_spans)


async def _run_context_detection_inner(doc_id: str, text: str, tier1_spans: List[dict]) -> None:
    # Build a summary of what Tier 1 already found so Ollama can focus on gaps
    already_found = ", ".join(
        f'"{s["text"]}" ({s["type"]})' for s in tier1_spans[:30]
    ) or "nothing yet"

    occupied = [(s["char_start"], s["char_end"]) for s in tier1_spans]

    prompt = f"""You are a PII and sensitive-information analyst reviewing a legal/administrative document, likely from India.

Standard NER tools have ALREADY detected these spans in this document:
{already_found}

Your job is to find everything they MISSED. Focus on two categories:

CATEGORY A — INDIAN GOVERNMENT IDs (pattern-based but possibly missed):
- Aadhaar number (12 digits, often written as XXXX XXXX XXXX)
- PAN card number (format: ABCDE1234F)
- Passport number (1 letter + 7 digits, e.g. A1234567)
- Voter ID / EPIC number (3 letters + 7 digits)
- Driving licence number
- GST number (15 characters)
- IFSC code, bank account number, UPI ID
- Ration card number, NPR number

CATEGORY B — CONTEXT-SENSITIVE INFORMATION (only sensitive given this document):
- Dates that reveal sensitive events (admission, arrest, diagnosis, filing date)
- Relationship words that identify people ("the applicant's husband", "her employer")
- Medical conditions, diagnoses, medications, disabilities
- Financial details: amounts, account references, loan details
- Caste, religion, community if mentioned
- Employment details that narrow identity
- Case/docket/claim/file reference numbers

Return ONLY a valid JSON array. No markdown. No explanation outside the JSON. If nothing found, return [].

Each item:
{{"text": "exact substring from the document", "type": "name|ssn|phone|address|other", "confidence": 0.0-1.0, "reasoning": "one sentence"}}

Rules:
- "text" must appear VERBATIM in the document
- Do NOT repeat: {already_found}
- Minimum confidence 0.4
- Prefer short, precise spans

Document:
---
{text[:8000]}
---
"""

    db = await get_db()
    try:
        timeout = aiohttp.ClientTimeout(total=_OLLAMA_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(OLLAMA_URL, json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
            }) as resp:
                if resp.status != 200:
                    log.warning("Ollama returned HTTP %d for doc %s — LLM tier skipped", resp.status, doc_id)
                    return
                data = await resp.json()
    except aiohttp.ClientConnectorError:
        log.info("Ollama not running — LLM context tier skipped for doc %s", doc_id)
        return
    except Exception as exc:
        log.warning("Ollama error for doc %s: %s", doc_id, exc)
        return

    response_text = data.get("response", "").strip()
    if not response_text:
        return

    # Strip markdown fences
    for fence in ("```json", "```"):
        if fence in response_text:
            parts = response_text.split(fence)
            if len(parts) >= 3:
                response_text = parts[1].split("```")[0].strip()
            break

    try:
        results = json.loads(response_text)
        if not isinstance(results, list):
            log.warning("Ollama response was not a list for doc %s", doc_id)
            return
    except json.JSONDecodeError as exc:
        log.warning("Ollama JSON parse error for doc %s: %s | response: %s", doc_id, exc, response_text[:300])
        return

    stored = 0
    for r in results:
        raw_text = (r.get("text") or "").strip()
        if not raw_text or len(raw_text) < 2:
            continue

        # Find exact position in document
        start = text.find(raw_text)
        if start == -1:
            # Try case-insensitive fallback
            lower = text.lower()
            idx = lower.find(raw_text.lower())
            if idx == -1:
                continue
            start = idx
            raw_text = text[start: start + len(raw_text)]
        end = start + len(raw_text)

        # Skip if overlaps an existing Tier 1 span
        if any(s <= start < e or s < end <= e for s, e in occupied):
            continue

        span_type = r.get("type", "other")
        if span_type not in ("name", "ssn", "phone", "address", "other"):
            span_type = "other"

        confidence = float(r.get("confidence", 0.5))
        if confidence < 0.4:
            continue

        span_id = f"span-{doc_id}-llm-{uuid.uuid4().hex[:6]}"
        await db.execute(
            """INSERT OR IGNORE INTO spans
               (id, document_id, text, char_start, char_end, type, confidence,
                tier, source, reasoning, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'llm', 'ollama', ?, 'undecided')""",
            (span_id, doc_id, raw_text, start, end, span_type, confidence,
             r.get("reasoning", "")),
        )
        occupied.append((start, end))
        stored += 1

    await db.commit()
    log.info("LLM context tier stored %d new spans for doc %s", stored, doc_id)


# Backward-compat for the /llm-review route (returns already-stored LLM spans)
async def get_llm_tier_spans(doc_id: str) -> List[dict]:
    from dal.span_dal import get_spans_for_document
    return await get_spans_for_document(doc_id, tier="llm")
