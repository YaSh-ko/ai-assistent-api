#!/usr/bin/env python3
"""
Применить миграции Alembic к PostgreSQL.
Использование (из каталога api/, с загруженным .env):

    python apply_migrations.py
"""
import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
migrations_dir = project_root / "common" / "database" / "migrations" / "postgresql"

sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "common"))

try:
    from dotenv import load_dotenv

    load_dotenv(project_root / ".env")
    load_dotenv(project_root / ".env.local")
except ImportError:
    pass

from alembic import command
from alembic.config import Config


def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        postgres_host = os.getenv("POSTGRES_HOST")
        if not postgres_host:
            print("POSTGRES_HOST или DATABASE_URL не заданы. Проверьте api/.env")
            sys.exit(1)
        postgres_port = os.getenv("POSTGRES_PORT", "5432")
        postgres_db = os.getenv("POSTGRES_DB", "db_for_delez")
        postgres_user = os.getenv("POSTGRES_USER", "postgres")
        postgres_password = os.getenv("POSTGRES_PASSWORD", "")
        database_url = (
            f"postgresql+asyncpg://{postgres_user}:{postgres_password}"
            f"@{postgres_host}:{postgres_port}/{postgres_db}"
        )

    os.chdir(migrations_dir)
    alembic_cfg = Config(str(migrations_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(migrations_dir))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    target = database_url.split("@")[-1]
    print(f"Migrations target: {target}")
    print("=" * 60)
    try:
        command.upgrade(alembic_cfg, "head")
        print("=" * 60)
        print("Миграции применены (head).")
    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
