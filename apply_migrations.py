#!/usr/bin/env python3
"""
Скрипт для применения миграций Alembic к базе данных.
Использование:
    python apply_migrations.py
"""
import os
import sys
import asyncio
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Устанавливаем переменные окружения
os.chdir(project_root / "common")

# Импортируем и запускаем Alembic
from alembic.config import Config
from alembic import command

def main():
    # Загружаем DATABASE_URL из .env или собираем из компонентов
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        # Собираем из компонентов (без хардкода IP адресов)
        postgres_host = os.getenv("POSTGRES_HOST")
        if not postgres_host:
            print("❌ Ошибка: POSTGRES_HOST не задан в переменных окружения")
            print("   Установите POSTGRES_HOST или используйте DATABASE_URL")
            sys.exit(1)
        
        postgres_port = os.getenv("POSTGRES_PORT", "5432")
        postgres_db = os.getenv("POSTGRES_DB", "philosophy_staging")
        postgres_user = os.getenv("POSTGRES_USER", "postgres")
        postgres_password = os.getenv("POSTGRES_PASSWORD", "")
        
        database_url = f"postgresql+asyncpg://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}"
    
    # Создаем конфигурацию Alembic
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    
    print(f"Применяю миграции к базе данных: {database_url.split('@')[-1]}") # Log safe part
    print("=" * 60)
    
    # Применяем все миграции
    try:
        command.upgrade(alembic_cfg, "head")
        print("=" * 60)
        print("✅ Миграции успешно применены!")
    except Exception as e:
        print(f"❌ Ошибка при применении миграций: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
