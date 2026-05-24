# API — локальная разработка

## Docker

| Файл | Статус |
|------|--------|
| `Dockerfile` | Нужен, если собираешь образ API |
| ~~`docker-compose.staging.yml`~~ | Удалён (staging/прод) |

API обычно запускается **на хосте** (PyCharm / `uvicorn`), а не в Docker.

## Env

1. `cp .env.example .env`
2. Только локальные хосты: `localhost:5433`, `bolt://localhost:7687`, пользователь Neo4j `neo4j`
3. Опционально `.env.local` перекрывает `.env` (см. `config.py`)

Если API в Docker (`local-dev-env`) — в compose уже заданы `db` / `neo4j`; на хосте — `localhost`.

## Базы данных

Подними из `python-ai-service`:

```bash
docker compose --env-file .env.local -f docker-compose.dev.yml up -d
```

Подробнее: `python-ai-service/LOCAL_DEVELOPMENT.md`.

## Защита от прод

При прод-хосте в `DATABASE_URL` / `NEO4J_URI` приложение не стартует (см. `src/core/config.py`).
