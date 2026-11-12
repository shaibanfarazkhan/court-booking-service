"""Create the pre-migration schema expected by the historical revisions.

The repository's first revision upgrades an existing application schema. CI
starts with an empty PostgreSQL service, so create that legacy starting point
before exercising the checked-in Alembic revisions.
"""

import asyncio
import sys
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

# Python sets sys.path[0] to this script's directory when run from CI.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.config import settings
from app.db.base import Base


async def main() -> None:
    """Create the schema that existed immediately before revision 0000."""
    metadata = sa.MetaData()
    excluded_tables = {
        "availabilities",
        "booking_policies",
        "pricing_rules",
        "recurring_booking_requests",
    }
    removed_columns = {
        "venues": {"country", "timezone"},
        "bookings": {"refund_eligible"},
    }

    for table in Base.metadata.sorted_tables:
        if table.name in excluded_tables:
            continue
        legacy_table = table.to_metadata(metadata)
        for column_name in removed_columns.get(table.name, set()):
            legacy_table._columns.remove(legacy_table.c[column_name])

    sa.UniqueConstraint(
        metadata.tables["bookings"].c.time_slot_id,
        name="bookings_time_slot_id_key",
    )

    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
