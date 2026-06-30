from __future__ import annotations
from typing import List
"""
Data Access Layer for CategoryStats (session-scoped recalibration).
"""

from database import get_db


async def get_all_stats() -> List[dict]:
    """Get all category stats."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM category_stats ORDER BY type")
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_stat_by_type(type_name: str) -> dict | None:
    """Get stats for a specific type."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM category_stats WHERE type = ?", (type_name,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def increment_reject(type_name: str) -> None:
    """Increment reject count and recompute weight."""
    db = await get_db()
    # Ensure the type exists
    await db.execute(
        "INSERT OR IGNORE INTO category_stats (type, reject_count, confirm_count, current_priority_weight) VALUES (?, 0, 0, 1.0)",
        (type_name,),
    )
    await db.execute(
        "UPDATE category_stats SET reject_count = reject_count + 1 WHERE type = ?",
        (type_name,),
    )
    await _recompute_weight(db, type_name)
    await db.commit()


async def increment_confirm(type_name: str) -> None:
    """Increment confirm count and recompute weight."""
    db = await get_db()
    await db.execute(
        "INSERT OR IGNORE INTO category_stats (type, reject_count, confirm_count, current_priority_weight) VALUES (?, 0, 0, 1.0)",
        (type_name,),
    )
    await db.execute(
        "UPDATE category_stats SET confirm_count = confirm_count + 1 WHERE type = ?",
        (type_name,),
    )
    await _recompute_weight(db, type_name)
    await db.commit()


async def get_priority_weights() -> dict[str, float]:
    """Return a dict mapping type -> current_priority_weight."""
    db = await get_db()
    cursor = await db.execute("SELECT type, current_priority_weight FROM category_stats")
    rows = await cursor.fetchall()
    return {row["type"]: row["current_priority_weight"] for row in rows}


async def _recompute_weight(db, type_name: str) -> None:
    """
    Recompute priority weight for a type.

    Formula: weight = 1.0 / (1.0 + reject_count / (reject_count + confirm_count + 1))

    Intuition: As Maya rejects more spans of a given type, the weight decreases,
    pushing that type's spans lower in display priority. The denominator ensures
    the weight is always between 0.5 and 1.0, never zero.

    Example:
      - 0 rejects, 0 confirms -> weight = 1.0  (fully prioritized)
      - 5 rejects, 5 confirms -> weight ≈ 0.69 (still shows but lower)
      - 20 rejects, 2 confirms -> weight ≈ 0.54 (significantly deprioritized)
    """
    cursor = await db.execute(
        "SELECT reject_count, confirm_count FROM category_stats WHERE type = ?",
        (type_name,),
    )
    row = await cursor.fetchone()
    if row:
        rc = row["reject_count"]
        cc = row["confirm_count"]
        weight = 1.0 / (1.0 + rc / (rc + cc + 1))
        await db.execute(
            "UPDATE category_stats SET current_priority_weight = ? WHERE type = ?",
            (weight, type_name),
        )