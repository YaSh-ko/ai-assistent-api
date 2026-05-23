# Neo4j SSL Connection Fix

## Проблема

После истечения SSL-сертификата на `neo4j.delez-repo.ru` API перестал подключаться к Neo4j.

Ошибка в логах:
```
ssl.SSLCertVerificationError: certificate verify failed: certificate has expired
neo4j.exceptions.ServiceUnavailable: Couldn't connect to neo4j.delez-repo.ru:7687
```

Причина: в `docker-compose.staging.yml` на сервере была прописана переменная `NEO4J_URI=bolt+s://...` (через GitLab CI Variable), которая использует SSL **с верификацией** сертификата. Истёкший сертификат Python не принимает.

## Схемы подключения Neo4j

| Схема | SSL | Верификация сертификата |
|---|---|---|
| `bolt://` | нет | нет |
| `bolt+s://` / `neo4j+s://` | да | да |
| `bolt+ssc://` / `neo4j+ssc://` | да | нет |

## Решение

Заменили схему URI с `bolt+s://` на `bolt+ssc://` (ssc = self-signed certificate / skip cert check).

В `docker-compose.staging.yml` захардкодили значение вместо переменной, чтобы GitLab CI Variable не могла его перезаписать:

```yaml
# было
- NEO4J_URI=${NEO4J_URI}

# стало
- NEO4J_URI=bolt+ssc://neo4j.delez-repo.ru:7687
```

## Дополнительные исправления

- Добавлены переменные `JWT_PRIVATE_KEY_PEM` и `JWT_PUBLIC_KEY_PEM` в `docker-compose.staging.yml` — без них аутентификация возвращала 503.
- Создан `/deploy/api/.env` с паролями и JWT-ключами для ручного запуска контейнера.
- Исправлен цвет текста в блоке ошибки на форме входа (`color: #000` → `color: #fff`) — текст не был виден на тёмном фоне.

## Долгосрочное решение

Обновить SSL-сертификат на `neo4j.delez-repo.ru` и вернуть `bolt+s://` для полноценной верификации.
