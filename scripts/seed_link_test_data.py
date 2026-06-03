#!/usr/bin/env python3
"""
Сид тестовых наблюдений и целей с life_area для проверки semantic linker.

Запуск из каталога api (нужны Postgres, Neo4j, python-ai-service):
  python scripts/seed_link_test_data.py
  python scripts/seed_link_test_data.py --user-id <uuid>

Переменная SEED_USER_ID — id пользователя (по умолчанию первый из таблицы user).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from sqlalchemy import select

from common.database.models import User
from src.core.database import async_session_maker
from src.services.entry_service import create_entry_and_sync
from src.services.goal_service import create_goal_and_sync

TODAY = date.today()

OBSERVATIONS = [
    {
        "title": "Усталость и меньше спорта",
        "description": (
            "Последние две недели чувствую упадок сил, пропускаю пробежки "
            "и зал, настроение ниже обычного."
        ),
        "life_area": "health",
    },
    {
        "title": "Рост расходов на подписки",
        "description": (
            "Заметил, что траты на доставку еду, подписки и такси выросли "
            "примерно на треть по сравнению с прошлым месяцем."
        ),
        "life_area": "finance",
    },
    {
        "title": "Сложно учиться вечером",
        "description": (
            "После работы тяжело удерживать внимание на курсах по программированию, "
            "откладываю домашние задания на выходные."
        ),
        "life_area": "skills",
    },
]

GOALS = [
    {
        "title": "Тренировки три раза в неделю",
        "description": (
            "Вернуться к регулярным тренировкам: бег или зал минимум три раза "
            "в неделю, отслеживать восстановление."
        ),
        "life_area": "health",
    },
    {
        "title": "Увеличить месячные накопления",
        "description": (
            "Цель — откладывать фиксированную сумму каждый месяц и сократить "
            "импульсивные траты на сервисы."
        ),
        "life_area": "finance",
    },
    {
        "title": "Закончить курс по Python",
        "description": (
            "Пройти базовый курс по Python за два месяца с практикой "
            "на мини-проектах по вечерам."
        ),
        "life_area": "skills",
    },
]


async def resolve_user_id(explicit: str | None) -> str:
    if explicit:
        return explicit
    import os

    env_uid = os.getenv("SEED_USER_ID")
    if env_uid:
        return env_uid

    async with async_session_maker() as db:
        row = await db.execute(select(User.id).limit(1))
        uid = row.scalar_one_or_none()
    if not uid:
        raise SystemExit("В БД нет пользователей. Укажите --user-id или SEED_USER_ID.")
    return uid


async def seed(user_id: str) -> None:
    print(f"Seeding for user_id={user_id}")
    print("Убедитесь, что запущены API (8003), python-ai-service (8000), Neo4j, Postgres.\n")

    async with async_session_maker() as db:
        print("=== Наблюдения (3) ===")
        for i, obs in enumerate(OBSERVATIONS, 1):
            created = await create_entry_and_sync(
                db=db,
                user_id=user_id,
                title=obs["title"],
                description=obs["description"],
                event_date=TODAY,
                life_area=obs["life_area"],
            )
            print(f"  {i}. [{obs['life_area']}] {created.id} — {obs['title']}")

        print("\n=== Цели (3) ===")
        for i, g in enumerate(GOALS, 1):
            created = await create_goal_and_sync(
                db=db,
                user_id=user_id,
                title=g["title"],
                description=g["description"],
                life_area=g["life_area"],
            )
            print(f"  {i}. [{g['life_area']}] {created.id} — {g['title']}")

    print(
        "\nГотово. Откройте карту связей и нажмите «Синхр.» или дождитесь автосвязей "
        "(они уже вызывались при создании).\n"
        "Ожидаемые кластеры: health, finance, skills — по одной связи obs↔goal в каждом."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed test entries and goals for link testing")
    parser.add_argument("--user-id", help="ID пользователя (таблица user)")
    args = parser.parse_args()
    user_id = asyncio.run(resolve_user_id(args.user_id))
    asyncio.run(seed(user_id))


if __name__ == "__main__":
    main()
