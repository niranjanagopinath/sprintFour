"""
SQLite database connection and schema initialization.
Uses aiosqlite for async access.
"""

from __future__ import annotations
import aiosqlite
from config import DATABASE_PATH

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    """Return the singleton database connection."""
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DATABASE_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
    return _db


async def close_db() -> None:
    """Close the database connection."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None


async def init_schema() -> None:
    """Create all tables if they don't exist."""
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            template_id TEXT,
            state TEXT NOT NULL DEFAULT 'pending'
                CHECK(state IN ('pending', 'in_review', 'completed')),
            source_type TEXT NOT NULL DEFAULT 'synthetic'
                CHECK(source_type IN ('synthetic', 'uploaded')),
            file_type TEXT NOT NULL DEFAULT 'text'
                CHECK(file_type IN ('digital', 'raster', 'text')),
            ocr_used BOOLEAN NOT NULL DEFAULT 0,
            ocr_confidence REAL,
            batch_id TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            detection_started_at TEXT,
            detection_completed_at TEXT,
            span_count INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS spans (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL REFERENCES documents(id),
            text TEXT NOT NULL,
            char_start INTEGER NOT NULL,
            char_end INTEGER NOT NULL,
            type TEXT NOT NULL,
            confidence REAL,
            tier TEXT NOT NULL CHECK(tier IN ('structured', 'llm', 'manual')),
            source TEXT NOT NULL DEFAULT 'synthetic'
                CHECK(source IN ('synthetic', 'presidio', 'gliner', 'gemma', 'ollama', 'regex', 'manual')),
            reasoning TEXT,
            status TEXT NOT NULL DEFAULT 'undecided'
                CHECK(status IN ('undecided', 'confirmed', 'rejected')),
            action_mode TEXT
                CHECK(action_mode IN ('redact', 'anonymize', NULL)),
            decided_via TEXT
                CHECK(decided_via IN ('manual', 'propagated', 'cluster', 'spot_check', NULL)),
            source_span_id TEXT REFERENCES spans(id)
        );

        CREATE INDEX IF NOT EXISTS idx_spans_document_id ON spans(document_id);
        CREATE INDEX IF NOT EXISTS idx_spans_text ON spans(text COLLATE NOCASE);
        CREATE INDEX IF NOT EXISTS idx_spans_type ON spans(type);
        CREATE INDEX IF NOT EXISTS idx_spans_status ON spans(status);

        CREATE TABLE IF NOT EXISTS decisions (
            id TEXT PRIMARY KEY,
            span_id TEXT NOT NULL REFERENCES spans(id),
            document_id TEXT NOT NULL REFERENCES documents(id),
            action TEXT NOT NULL CHECK(action IN ('confirm', 'reject')),
            action_mode TEXT
                CHECK(action_mode IN ('redact', 'anonymize', NULL)),
            decided_via TEXT NOT NULL
                CHECK(decided_via IN ('manual', 'propagated', 'cluster', 'spot_check')),
            confidence_at_decision REAL,
            timestamp TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_decisions_document_id ON decisions(document_id);
        CREATE INDEX IF NOT EXISTS idx_decisions_span_id ON decisions(span_id);
        CREATE INDEX IF NOT EXISTS idx_decisions_decided_via ON decisions(decided_via);

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
        CREATE UNIQUE INDEX IF NOT EXISTS idx_pseudonym_map_entity ON pseudonym_map(entity_text_normalized);

        CREATE TABLE IF NOT EXISTS batch_audit_events (
            id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            entity_text TEXT,
            entity_type TEXT,
            note TEXT,
            timestamp TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_bae_entity ON batch_audit_events(LOWER(entity_text), entity_type);
    """)
    await db.commit()


async def reset_category_stats() -> None:
    """Ensure all known types exist in category_stats (preserves learned weights)."""
    db = await get_db()
    for t in ("name", "ssn", "phone", "address", "case_number", "other"):
        await db.execute(
            "INSERT OR IGNORE INTO category_stats (type, reject_count, confirm_count, current_priority_weight) VALUES (?, 0, 0, 1.0)",
            (t,),
        )
    await db.commit()