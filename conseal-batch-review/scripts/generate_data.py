#!/usr/bin/env python3
"""
Conseal Batch Review — Synthetic Data Generator

Generates a batch of synthetic case documents with mock PII detections,
seeds them into the SQLite database, and writes a generation_manifest.json.

Usage:
    python scripts/generate_data.py [--doc-count 150] [--entity-overlap-rate 0.2]
                                     [--noise-rate 0.15] [--unanticipated-rate 0.1]
                                     [--db-path backend/conseal.db]
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import string
import uuid
from datetime import datetime, timedelta

# ────────────────────────────────────────────────────────────────────────
# Entity value pools
# ────────────────────────────────────────────────────────────────────────

FIRST_NAMES = [
    "John", "Maria", "James", "Sarah", "Robert", "Linda", "Michael", "Jennifer",
    "David", "Patricia", "William", "Elizabeth", "Richard", "Barbara", "Joseph",
    "Susan", "Thomas", "Jessica", "Charles", "Karen", "Christopher", "Nancy",
    "Daniel", "Lisa", "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra",
]

LAST_NAMES = [
    "Carrera", "Westbrook", "Nguyen", "Patel", "O'Brien", "Kowalski", "Ramirez",
    "Chen", "Abernathy", "Fitzgerald", "Delgado", "Thompson", "Morrison", "Kuznetsov",
    "Blackwell", "Yamamoto", "Harper", "Castellano", "Lindgren", "Okafor",
    "Sullivan", "Marchetti", "Petrov", "Ashworth", "Nakamura",
]

STREETS = [
    "Oak Street", "Maple Avenue", "Cedar Lane", "Pine Road", "Elm Boulevard",
    "Birch Drive", "Walnut Court", "Spruce Way", "Willow Circle", "Ash Parkway",
    "Highland Drive", "Lakeview Terrace", "Sunset Boulevard", "River Road",
    "Mountain View Lane", "Park Avenue", "Broadway", "Main Street",
]

CITIES_STATES = [
    ("Springfield", "IL"), ("Portland", "OR"), ("Austin", "TX"), ("Denver", "CO"),
    ("Miami", "FL"), ("Seattle", "WA"), ("Boston", "MA"), ("Chicago", "IL"),
    ("Phoenix", "AZ"), ("Atlanta", "GA"), ("San Diego", "CA"), ("Detroit", "MI"),
    ("Nashville", "TN"), ("Charlotte", "NC"), ("Columbus", "OH"),
]

CASE_PREFIXES = ["CV", "CR", "FAM", "PRB", "JV", "CL", "MH", "TR", "WC", "BK"]
CASE_YEARS = ["2023", "2024", "2025"]

UNANTICIPATED_DETAILS = [
    ("was diagnosed with Type 2 diabetes in 2019 and continues insulin treatment", "medical condition"),
    ("provided bank account number 4782-9913-0054 during the intake process", "bank account"),
    ("mentioned her HIV-positive status during the preliminary interview", "medical condition"),
    ("disclosed a prior hospitalization at Greenfield Psychiatric Center", "medical history"),
    ("referenced checking account ending in 7743 at First National Bank", "bank account"),
    ("stated he receives disability payments for chronic PTSD", "medical condition"),
    ("identified herself as a recovering alcoholic in the witness statement", "personal disclosure"),
    ("has a distinctive facial scar from a childhood accident, noted by the officer", "identifying feature"),
    ("drives a red 2019 Ford F-150 with custom plates reading 'BGLDY42'", "identifying detail"),
    ("mentioned her ex-husband's Social Security number during testimony", "third-party PII"),
    ("carries an insulin pump visible during the deposition", "medical device"),
    ("disclosed his immigration status as a DACA recipient", "immigration status"),
    ("reported annual income of $127,450 from two employers", "financial detail"),
    ("referenced her therapist Dr. Angela Morrison at Sunset Counseling", "healthcare provider"),
    ("noted a prescription for Oxycontin filled at CVS pharmacy #4421", "prescription detail"),
    ("is currently enrolled in a methadone maintenance program", "substance treatment"),
    ("wears an ankle monitoring bracelet as a condition of parole", "legal status"),
    ("has a birthmark on the left forearm described in the police report", "identifying feature"),
    ("provided routing number 021000021 for JPMorgan Chase during settlement", "bank routing"),
    ("disclosed a prior conviction for DUI in Maricopa County in 2017", "criminal history"),
]

# ────────────────────────────────────────────────────────────────────────
# Document templates
# ────────────────────────────────────────────────────────────────────────

TEMPLATES = {
    "intake_form": {
        "title_prefix": "Intake Form",
        "body": """CLIENT INTAKE FORM — CONFIDENTIAL

Date of Intake: {date}
Case Number: {case_number}

CLIENT INFORMATION:
Full Name: {name}
Social Security Number: {ssn}
Phone Number: {phone}
Home Address: {address}

{paragraph_1}

The client, {name}, presented at our office on {date} seeking legal representation regarding {case_type}. Initial interview was conducted by the intake coordinator. Client confirmed their contact number as {phone} and verified their address at {address}.

{paragraph_2}

All identifying information including SSN ({ssn}) has been recorded in the secure case management system under case reference {case_number}. {extra_detail}Client has been advised of confidentiality protections and signed the engagement letter.""",
    },
    "deposition_summary": {
        "title_prefix": "Deposition Summary",
        "body": """DEPOSITION SUMMARY — PRIVILEGED AND CONFIDENTIAL

Case No.: {case_number}
Date of Deposition: {date}
Deponent: {name}

SUMMARY OF TESTIMONY:

{paragraph_1}

The deponent, {name}, was sworn in at 9:30 AM. When asked for identification, the deponent provided a Social Security Number of {ssn} and confirmed their current address as {address}. The deponent's contact telephone number was recorded as {phone}.

{paragraph_2}

During cross-examination, the deponent referenced case number {case_number} multiple times. The deponent confirmed their full legal name as {name} and stated they had resided at {address} for approximately three years. {extra_detail}The deposition concluded at 3:45 PM. Transcript to follow.""",
    },
    "case_note": {
        "title_prefix": "Case Note",
        "body": """CASE NOTE — ATTORNEY-CLIENT PRIVILEGED

Case: {case_number}
Date: {date}
Re: {name}

{paragraph_1}

Spoke with client {name} via phone at {phone} regarding status update on {case_type}. Client expressed concern about timeline and requested expedited processing. Confirmed current mailing address as {address} for service of documents.

{paragraph_2}

Verified client identity using last four of SSN ({ssn}). Updated case file {case_number} with new information. {extra_detail}Next follow-up scheduled for two weeks from today. Client prefers to be reached at {phone} during business hours only.""",
    },
    "incident_report": {
        "title_prefix": "Incident Report",
        "body": """INCIDENT REPORT — CONFIDENTIAL

Report Number: {case_number}
Date of Incident: {date}
Subject: {name}

NARRATIVE:

{paragraph_1}

On {date}, the subject identified as {name} (SSN: {ssn}) was involved in an incident at {address}. The subject was contacted at {phone} for a follow-up statement. The subject confirmed their identity and provided a written account of the events.

{paragraph_2}

All evidence has been catalogued under {case_number}. The subject, {name}, cooperated fully with the investigation. Contact records show the subject's primary phone as {phone} and residence as {address}. {extra_detail}This report is filed pursuant to standard protocols.""",
    },
    "witness_statement": {
        "title_prefix": "Witness Statement",
        "body": """WITNESS STATEMENT — CONFIDENTIAL

Case Reference: {case_number}
Statement Date: {date}
Witness: {name}

I, {name}, hereby provide the following voluntary statement:

{paragraph_1}

For the record, my Social Security Number is {ssn}, my home address is {address}, and I can be reached at {phone}. I am providing this statement in connection with case {case_number}.

{paragraph_2}

I have read this statement and confirm that it is true and accurate to the best of my knowledge. {extra_detail}My contact information remains {phone} and {address}. I am willing to appear for further proceedings if required.

Signed: {name}
Date: {date}""",
    },
}

FILLER_PARAGRAPHS = [
    "The matter involves allegations of negligence arising from events that occurred in the prior fiscal quarter. Counsel has reviewed the preliminary documentation and identified several areas requiring further investigation before any formal response can be filed with the court.",
    "Previous correspondence from opposing counsel indicates a willingness to negotiate a settlement within the statutory framework. However, certain evidentiary issues remain unresolved and may require additional discovery motions before mediation can proceed effectively.",
    "The relevant jurisdiction has established precedent in similar matters, most notably in the landmark ruling from 2018 that addressed comparable factual circumstances. Our analysis suggests that the current case presents distinguishable elements that may warrant a different legal strategy.",
    "Documentation received from third-party sources corroborates the timeline established in the initial filing. The chain of custody for all physical evidence has been verified and meets the requirements for admissibility under the applicable rules of evidence.",
    "The client has been cooperative throughout the preliminary stages of this matter and has provided all requested documentation in a timely manner. Financial records spanning the relevant period have been organized and indexed for review by the legal team.",
    "Expert witnesses have been retained to provide testimony regarding the technical aspects of the case. Their preliminary reports support the theory of liability outlined in the complaint and provide quantifiable metrics for the claimed damages.",
    "Regulatory compliance audits conducted during the review period indicate several areas of concern that may impact the overall legal strategy. These findings have been communicated to the client along with recommended remedial actions.",
    "The statute of limitations for the primary claims expires within the next eighteen months, necessitating prompt action on all discovery requests and pre-trial motions. A detailed timeline has been prepared and shared with co-counsel.",
]

CASE_TYPES = [
    "personal injury", "property dispute", "employment discrimination",
    "contract breach", "family law matter", "workers compensation claim",
    "insurance dispute", "landlord-tenant issue", "medical malpractice",
    "product liability", "intellectual property dispute", "estate planning",
]


def generate_ssn():
    """Generate a fake SSN."""
    return f"{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(1000, 9999)}"


def generate_phone():
    """Generate a fake phone number."""
    return f"({random.randint(200, 999)}) {random.randint(200, 999)}-{random.randint(1000, 9999)}"


def generate_address():
    """Generate a fake address."""
    num = random.randint(100, 9999)
    street = random.choice(STREETS)
    city, state = random.choice(CITIES_STATES)
    zipcode = f"{random.randint(10000, 99999)}"
    return f"{num} {street}, {city}, {state} {zipcode}"


def generate_case_number():
    """Generate a fake case number."""
    prefix = random.choice(CASE_PREFIXES)
    year = random.choice(CASE_YEARS)
    seq = random.randint(1000, 9999)
    return f"{prefix}-{year}-{seq}"


def generate_name():
    """Generate a fake full name."""
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def generate_date():
    """Generate a plausible date string."""
    base = datetime(2024, 1, 1)
    delta = timedelta(days=random.randint(0, 500))
    return (base + delta).strftime("%B %d, %Y")


# ────────────────────────────────────────────────────────────────────────
# Entity pool management for overlap control
# ────────────────────────────────────────────────────────────────────────

class EntityPool:
    """Manages entity value pools to achieve target overlap rates."""

    def __init__(self, doc_count: int, overlap_rate: float):
        self.doc_count = doc_count
        self.overlap_rate = overlap_rate

        # Pre-generate pools
        # For overlapping entities: smaller pool → more reuse
        overlap_count = max(3, int(doc_count * overlap_rate / 12))  # ~12 reuses each
        unique_count = doc_count - int(doc_count * overlap_rate)

        self.names_shared = [generate_name() for _ in range(overlap_count)]
        self.names_unique = [generate_name() for _ in range(unique_count)]

        self.ssns_shared = [generate_ssn() for _ in range(overlap_count)]
        self.ssns_unique = [generate_ssn() for _ in range(unique_count)]

        self.phones_shared = [generate_phone() for _ in range(overlap_count)]
        self.phones_unique = [generate_phone() for _ in range(unique_count)]

        self.addresses_shared = [generate_address() for _ in range(overlap_count)]
        self.addresses_unique = [generate_address() for _ in range(unique_count)]

        self.case_numbers_shared = [generate_case_number() for _ in range(overlap_count)]
        self.case_numbers_unique = [generate_case_number() for _ in range(unique_count)]

        # Track usage for manifest
        self.usage: dict[str, dict[str, list[str]]] = {}  # type -> value -> [doc_ids]

        self._unique_idx = {
            "name": 0, "ssn": 0, "phone": 0, "address": 0, "case_number": 0
        }

    def get_entity(self, entity_type: str, doc_id: str) -> str:
        """Get an entity value, sometimes from shared pool for overlap."""
        use_shared = random.random() < self.overlap_rate

        pools = {
            "name": (self.names_shared, self.names_unique),
            "ssn": (self.ssns_shared, self.ssns_unique),
            "phone": (self.phones_shared, self.phones_unique),
            "address": (self.addresses_shared, self.addresses_unique),
            "case_number": (self.case_numbers_shared, self.case_numbers_unique),
        }

        shared, unique = pools[entity_type]

        if use_shared and shared:
            value = random.choice(shared)
        else:
            idx = self._unique_idx[entity_type]
            if idx < len(unique):
                value = unique[idx]
                self._unique_idx[entity_type] = idx + 1
            else:
                value = random.choice(shared) if shared else self._generate_new(entity_type)

        # Track usage
        if entity_type not in self.usage:
            self.usage[entity_type] = {}
        if value not in self.usage[entity_type]:
            self.usage[entity_type][value] = []
        if doc_id not in self.usage[entity_type][value]:
            self.usage[entity_type][value].append(doc_id)

        return value

    def _generate_new(self, entity_type: str) -> str:
        generators = {
            "name": generate_name,
            "ssn": generate_ssn,
            "phone": generate_phone,
            "address": generate_address,
            "case_number": generate_case_number,
        }
        return generators[entity_type]()

    def get_overlap_stats(self) -> dict:
        """Return overlap statistics for the manifest."""
        stats = {}
        for etype, values in self.usage.items():
            overlapping = {v: docs for v, docs in values.items() if len(docs) > 1}
            stats[etype] = {
                "total_unique_values": len(values),
                "overlapping_values": len(overlapping),
                "top_overlapping": sorted(
                    [(v, len(docs)) for v, docs in overlapping.items()],
                    key=lambda x: -x[1]
                )[:10],
            }
        return stats


# ────────────────────────────────────────────────────────────────────────
# Span detection generation
# ────────────────────────────────────────────────────────────────────────

def find_all_occurrences(text: str, substring: str) -> list[tuple[int, int]]:
    """Find all occurrences of substring in text, return (start, end) pairs."""
    results = []
    start = 0
    while True:
        idx = text.find(substring, start)
        if idx == -1:
            break
        results.append((idx, idx + len(substring)))
        start = idx + 1
    return results


def generate_detections(
    doc_id: str,
    raw_text: str,
    entities: dict[str, str],
    noise_rate: float,
) -> list[dict]:
    """
    Generate structured detections for a document.
    - Finds all entity occurrences in the text
    - Injects false positives (noise_rate fraction)
    - Deliberately omits some real PII (noise_rate fraction)
    """
    detections = []
    span_counter = 0

    # Find real entity occurrences
    real_detections = []
    for etype, value in entities.items():
        occurrences = find_all_occurrences(raw_text, value)
        for start, end in occurrences:
            span_counter += 1
            real_detections.append({
                "id": f"span-{doc_id}-{span_counter:03d}",
                "document_id": doc_id,
                "text": value,
                "char_start": start,
                "char_end": end,
                "type": etype,
                "confidence": round(random.uniform(0.75, 0.99), 2),
                "tier": "structured",
                "reasoning": None,
                "status": "undecided",
                "decided_via": None,
                "source_span_id": None,
            })

    # Deliberately omit some real PII (simulating misses)
    omit_count = max(0, int(len(real_detections) * noise_rate))
    if omit_count > 0 and len(real_detections) > omit_count:
        omitted_indices = set(random.sample(range(len(real_detections)), omit_count))
        real_detections = [d for i, d in enumerate(real_detections) if i not in omitted_indices]

    detections.extend(real_detections)

    # Add false positive detections (noise)
    fp_count = max(0, int(len(detections) * noise_rate))
    for _ in range(fp_count):
        span_counter += 1
        # Pick a random substring from the text as a false positive
        text_len = len(raw_text)
        if text_len < 20:
            continue
        fp_start = random.randint(0, text_len - 15)
        # Find a word boundary
        while fp_start > 0 and raw_text[fp_start - 1] not in (' ', '\n', ',', '.'):
            fp_start -= 1
        fp_end = fp_start + random.randint(5, 15)
        fp_end = min(fp_end, text_len)
        # Find a word boundary for end
        while fp_end < text_len and raw_text[fp_end] not in (' ', '\n', ',', '.'):
            fp_end += 1

        fp_text = raw_text[fp_start:fp_end].strip()
        if not fp_text or len(fp_text) < 3:
            continue

        detections.append({
            "id": f"span-{doc_id}-fp-{span_counter:03d}",
            "document_id": doc_id,
            "text": fp_text,
            "char_start": fp_start,
            "char_end": fp_start + len(fp_text),
            "type": random.choice(["name", "phone", "address"]),
            "confidence": round(random.uniform(0.3, 0.65), 2),
            "tier": "structured",
            "reasoning": None,
            "status": "undecided",
            "decided_via": None,
            "source_span_id": None,
        })

    # Sort by char_start
    detections.sort(key=lambda d: d["char_start"])

    return detections


# ────────────────────────────────────────────────────────────────────────
# Main generation
# ────────────────────────────────────────────────────────────────────────

def generate_documents(
    doc_count: int = 150,
    entity_overlap_rate: float = 0.2,
    noise_rate: float = 0.15,
    unanticipated_rate: float = 0.1,
    db_path: str = "backend/conseal.db",
):
    """Generate synthetic documents and seed the database."""
    random.seed(42)  # Reproducible generation

    pool = EntityPool(doc_count, entity_overlap_rate)
    template_ids = list(TEMPLATES.keys())

    # Determine which documents get unanticipated details
    unanticipated_count = max(1, int(doc_count * unanticipated_rate))
    unanticipated_doc_indices = set(random.sample(range(doc_count), unanticipated_count))

    documents = []
    all_detections = []
    all_llm_fixtures = []
    unanticipated_manifest = []
    noise_stats = {"false_positives": 0, "omitted_real": 0, "total_detections": 0}

    for i in range(doc_count):
        doc_id = f"doc-{i+1:04d}"
        template_id = random.choice(template_ids)
        template = TEMPLATES[template_id]

        # Generate entity values (with overlap control)
        entities = {
            "name": pool.get_entity("name", doc_id),
            "ssn": pool.get_entity("ssn", doc_id),
            "phone": pool.get_entity("phone", doc_id),
            "address": pool.get_entity("address", doc_id),
            "case_number": pool.get_entity("case_number", doc_id),
        }

        # Build the document text
        paragraph_1 = random.choice(FILLER_PARAGRAPHS)
        paragraph_2 = random.choice(FILLER_PARAGRAPHS)

        # Handle unanticipated detail
        extra_detail = ""
        llm_fixture = []

        if i in unanticipated_doc_indices:
            detail_text, detail_type = random.choice(UNANTICIPATED_DETAILS)
            extra_detail = f"During the session, the client {detail_text}. "

        raw_text = template["body"].format(
            date=generate_date(),
            case_number=entities["case_number"],
            name=entities["name"],
            ssn=entities["ssn"],
            phone=entities["phone"],
            address=entities["address"],
            case_type=random.choice(CASE_TYPES),
            paragraph_1=paragraph_1,
            paragraph_2=paragraph_2,
            extra_detail=extra_detail,
        )

        title = f"{template['title_prefix']} — {entities['name']} ({entities['case_number']})"

        # Generate structured detections
        detections = generate_detections(doc_id, raw_text, entities, noise_rate)

        # Generate LLM tier fixture for unanticipated documents
        if i in unanticipated_doc_indices and extra_detail:
            detail_text_in_doc = f"the client {detail_text}"
            occurrences = find_all_occurrences(raw_text, detail_text_in_doc)
            if occurrences:
                start, end = occurrences[0]
                llm_span = {
                    "id": f"span-{doc_id}-llm-001",
                    "document_id": doc_id,
                    "text": detail_text_in_doc,
                    "char_start": start,
                    "char_end": end,
                    "type": "other",
                    "confidence": round(random.uniform(0.3, 0.5), 2),
                    "tier": "llm",
                    "reasoning": f"This text appears to contain {detail_type} information that could identify or expose the individual beyond standard PII categories.",
                    "status": "undecided",
                    "decided_via": None,
                    "source_span_id": None,
                }
                llm_fixture.append(llm_span)
                unanticipated_manifest.append({
                    "doc_id": doc_id,
                    "title": title,
                    "detail_type": detail_type,
                    "detail_text": detail_text_in_doc,
                })

        documents.append({
            "id": doc_id,
            "title": title,
            "raw_text": raw_text,
            "template_id": template_id,
            "state": "pending",
        })

        all_detections.extend(detections)
        all_llm_fixtures.extend(llm_fixture)

        noise_stats["total_detections"] += len(detections)

    # ── Seed the database ──
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)

    # Remove old DB if exists
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # Create schema
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            template_id TEXT,
            state TEXT NOT NULL DEFAULT 'pending',
            source_type TEXT NOT NULL DEFAULT 'synthetic',
            file_type TEXT NOT NULL DEFAULT 'text',
            ocr_used BOOLEAN NOT NULL DEFAULT 0,
            ocr_confidence REAL,
            batch_id TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS spans (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL REFERENCES documents(id),
            text TEXT NOT NULL,
            char_start INTEGER NOT NULL,
            char_end INTEGER NOT NULL,
            type TEXT NOT NULL,
            confidence REAL,
            tier TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'synthetic',
            reasoning TEXT,
            status TEXT NOT NULL DEFAULT 'undecided',
            action_mode TEXT,
            decided_via TEXT,
            source_span_id TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_spans_document_id ON spans(document_id);
        CREATE INDEX IF NOT EXISTS idx_spans_text ON spans(text COLLATE NOCASE);
        CREATE INDEX IF NOT EXISTS idx_spans_type ON spans(type);
        CREATE INDEX IF NOT EXISTS idx_spans_status ON spans(status);

        CREATE TABLE IF NOT EXISTS decisions (
            id TEXT PRIMARY KEY,
            span_id TEXT NOT NULL REFERENCES spans(id),
            document_id TEXT NOT NULL REFERENCES documents(id),
            action TEXT NOT NULL,
            action_mode TEXT,
            decided_via TEXT NOT NULL,
            confidence_at_decision REAL,
            timestamp TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_decisions_document_id ON decisions(document_id);
        CREATE INDEX IF NOT EXISTS idx_decisions_span_id ON decisions(span_id);

        CREATE TABLE IF NOT EXISTS category_stats (
            type TEXT PRIMARY KEY,
            reject_count INTEGER NOT NULL DEFAULT 0,
            confirm_count INTEGER NOT NULL DEFAULT 0,
            current_priority_weight REAL NOT NULL DEFAULT 1.0
        );

        CREATE TABLE IF NOT EXISTS pseudonym_map (
            id TEXT PRIMARY KEY,
            entity_text_normalized TEXT NOT NULL,
            type TEXT NOT NULL,
            pseudonym TEXT NOT NULL,
            first_seen_document_id TEXT NOT NULL REFERENCES documents(id),
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_pseudonym_map_entity ON pseudonym_map(entity_text_normalized, type);
    """)

    # Insert documents
    for doc in documents:
        conn.execute(
            "INSERT INTO documents (id, title, raw_text, template_id, state, source_type, file_type, ocr_used, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (doc["id"], doc["title"], doc["raw_text"], doc["template_id"], doc["state"], 'synthetic', 'text', False, 'synthetic-batch'),
        )

    # Insert structured detections
    for det in all_detections:
        conn.execute(
            """INSERT INTO spans (id, document_id, text, char_start, char_end, type, confidence, tier, source, reasoning, status, decided_via, source_span_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (det["id"], det["document_id"], det["text"], det["char_start"], det["char_end"],
             det["type"], det["confidence"], det["tier"], 'synthetic', det["reasoning"],
             det["status"], det["decided_via"], det["source_span_id"]),
        )

    # Insert LLM tier fixtures
    for llm in all_llm_fixtures:
        conn.execute(
            """INSERT INTO spans (id, document_id, text, char_start, char_end, type, confidence, tier, source, reasoning, status, decided_via, source_span_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (llm["id"], llm["document_id"], llm["text"], llm["char_start"], llm["char_end"],
             llm["type"], llm["confidence"], llm["tier"], 'gemma', llm["reasoning"],
             llm["status"], llm["decided_via"], llm["source_span_id"]),
        )

    # Initialize category stats
    for t in ("name", "ssn", "phone", "address", "case_number", "other"):
        conn.execute(
            "INSERT OR IGNORE INTO category_stats (type) VALUES (?)", (t,)
        )

    conn.commit()

    # ── Build manifest ──
    overlap_stats = pool.get_overlap_stats()

    # Count templates
    template_counts = {}
    for doc in documents:
        tid = doc["template_id"]
        template_counts[tid] = template_counts.get(tid, 0) + 1

    manifest = {
        "generated_at": datetime.now().isoformat(),
        "parameters": {
            "doc_count": doc_count,
            "entity_overlap_rate": entity_overlap_rate,
            "noise_rate": noise_rate,
            "unanticipated_rate": unanticipated_rate,
        },
        "summary": {
            "total_documents": len(documents),
            "total_structured_detections": len(all_detections),
            "total_llm_fixtures": len(all_llm_fixtures),
            "documents_with_unanticipated": len(unanticipated_manifest),
            "template_distribution": template_counts,
        },
        "overlap_stats": {},
        "unanticipated_details": unanticipated_manifest,
    }

    # Format overlap stats for readability
    for etype, stats in overlap_stats.items():
        manifest["overlap_stats"][etype] = {
            "total_unique_values": stats["total_unique_values"],
            "overlapping_values": stats["overlapping_values"],
            "top_reused": [
                {"value": v, "appears_in_docs": count}
                for v, count in stats["top_overlapping"]
            ],
        }

    # Print summary
    print(f"\n{'='*60}")
    print(f"  Conseal Batch Review — Data Generation Complete")
    print(f"{'='*60}")
    print(f"  Documents:           {len(documents)}")
    print(f"  Structured spans:    {len(all_detections)}")
    print(f"  LLM tier fixtures:   {len(all_llm_fixtures)}")
    print(f"  Unanticipated docs:  {len(unanticipated_manifest)}")
    print(f"  Database:            {db_path}")
    print(f"{'='*60}")

    print(f"\n  Template distribution:")
    for tid, count in template_counts.items():
        print(f"    {tid}: {count} documents")

    print(f"\n  Entity overlap (top reused):")
    for etype, stats in overlap_stats.items():
        top = stats["top_overlapping"][:3]
        if top:
            for value, count in top:
                print(f"    {etype}: '{value}' appears in {count} documents")

    print(f"\n  Unanticipated detail documents:")
    for item in unanticipated_manifest[:5]:
        print(f"    {item['doc_id']}: {item['detail_type']}")
    if len(unanticipated_manifest) > 5:
        print(f"    ... and {len(unanticipated_manifest) - 5} more")

    conn.close()

    return manifest


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic data for Conseal Batch Review")
    parser.add_argument("--doc-count", type=int, default=150, help="Number of documents to generate")
    parser.add_argument("--entity-overlap-rate", type=float, default=0.2, help="Fraction of entities reused across docs")
    parser.add_argument("--noise-rate", type=float, default=0.15, help="Fraction of detections that are false positives / omissions")
    parser.add_argument("--unanticipated-rate", type=float, default=0.1, help="Fraction of docs with unanticipated sensitive details")
    parser.add_argument("--db-path", type=str, default=None, help="Path to SQLite database")

    args = parser.parse_args()

    # Resolve db path relative to project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    db_path = args.db_path or os.path.join(project_root, "backend", "conseal.db")
    manifest_path = os.path.join(project_root, "generation_manifest.json")

    manifest = generate_documents(
        doc_count=args.doc_count,
        entity_overlap_rate=args.entity_overlap_rate,
        noise_rate=args.noise_rate,
        unanticipated_rate=args.unanticipated_rate,
        db_path=db_path,
    )

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n  Manifest written to: {manifest_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
