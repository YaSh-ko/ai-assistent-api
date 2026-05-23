#!/usr/bin/env python3
"""
Detects the real migration state from schema and stamps alembic_version accordingly.
Run before `alembic upgrade head` to fix mismatched or unknown revision IDs.
"""
import asyncio
import os
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine

"""
Migration-id compatibility map.

Historical deploy scripts used synthetic IDs (rev_00X) that are not Alembic
revisions from the current migrations chain. We translate them to existing
revision IDs so `alembic upgrade head` can work.

IMPORTANT: If we only compare translated IDs in memory but skip UPDATE, the DB
still holds e.g. rev_010 and Alembic fails. Always persist mapped IDs.
"""
CURRENT_HEAD = "rev_010"
KNOWN_IDS = {
    # real alembic revisions (identity map)
    "rev_001": "rev_001",
    "rev_002": "rev_002",
    "rev_003": "rev_003",
    "rev_004": "rev_004",
    "rev_005": "rev_005",
    "rev_006": "rev_006",
    "rev_007": "rev_007",
    "rev_008": "rev_008",
    "rev_009": "rev_009",
    "rev_010": "rev_010",

    # legacy migration names -> map to current valid IDs
    "001_initial_schema": "rev_001",
    "fcabe41820ab": "rev_002",
    "7ed9a85edfa0": "rev_003",
    "002_add_auth_tables": "rev_004",
    "003_add_chat_tables": "rev_005",
    "004_create_chat_sessions": "rev_006",
    "005_add_audio_fields_to_entries": "rev_007",
    "006_add_beta_test_table": "rev_008",
    "007_unify_chat_history": "rev_009",
    "008_drop_chat_sessions_table": "rev_010",
}


async def detect_real_revision(conn) -> str:
    """Detect nearest valid revision by inspecting schema."""
    # Check for rev_009/rev_010 markers
    r = await conn.execute(sqlalchemy.text(
        "SELECT EXISTS (SELECT FROM information_schema.columns "
        "WHERE table_name = 'conversations' AND column_name = 'history')"
    ))
    has_history = r.scalar()

    r = await conn.execute(sqlalchemy.text(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'chat_sessions')"
    ))
    has_chat_sessions = r.scalar()

    # Check for rev_008 marker
    r = await conn.execute(sqlalchemy.text(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'beta_test')"
    ))
    has_beta = r.scalar()

    # Check for rev_007 marker
    r = await conn.execute(sqlalchemy.text(
        "SELECT EXISTS (SELECT FROM information_schema.columns "
        "WHERE table_name = 'entries' AND column_name = 'audio_source')"
    ))
    has_audio_fields = r.scalar()

    if has_history and not has_chat_sessions:
        return "rev_010"
    if has_history:
        return "rev_009"
    if has_beta:
        return "rev_008"
    if has_audio_fields:
        return "rev_007"
    return CURRENT_HEAD


async def run():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set, skipping stamp.")
        return

    engine = create_async_engine(url)
    async with engine.begin() as conn:
        res = await conn.execute(sqlalchemy.text("SELECT version_num FROM alembic_version"))
        rows = res.fetchall()

        if not rows:
            print("alembic_version is empty, skipping stamp.")
            return

        real_rev = await detect_real_revision(conn)
        print(f"Schema inspection result: {real_rev}")

        for row in rows:
            stored = row[0]

            # Resolve legacy/synthetic IDs to real Alembic revision strings
            if stored in KNOWN_IDS:
                effective = KNOWN_IDS[stored]
            elif stored.startswith("rev_"):
                print(f"Unknown synthetic revision {stored}; mapping to {CURRENT_HEAD}")
                effective = CURRENT_HEAD
            else:
                effective = stored

            # Must persist translation: DB may still say rev_010 while we only compared in memory
            if effective != stored:
                print(f"Updating alembic_version: {stored} -> {effective}")
                await conn.execute(
                    sqlalchemy.text(
                        "UPDATE alembic_version SET version_num = :new WHERE version_num = :old"
                    ),
                    {"new": effective, "old": stored},
                )

            # Align with detected schema if behind/ahead of reality
            if effective != real_rev:
                print(f"Mismatch: effective={effective}, schema={real_rev}. Stamping to {real_rev}.")
                await conn.execute(
                    sqlalchemy.text(
                        "UPDATE alembic_version SET version_num = :new WHERE version_num = :old"
                    ),
                    {"new": real_rev, "old": effective},
                )
            else:
                print(f"Revision {effective} matches schema state.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
