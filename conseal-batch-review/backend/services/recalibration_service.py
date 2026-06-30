"""
Recalibration service — wraps category stat operations.
"""

from dal import category_stat_dal


async def get_all_category_stats():
    """Get all category statistics."""
    return await category_stat_dal.get_all_stats()


async def get_priority_weights():
    """Get current priority weights for all types."""
    return await category_stat_dal.get_priority_weights()
