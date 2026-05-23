FROM python:3.11-slim

# Создаём непривилегированного пользователя для безопасности
RUN groupadd -r langgraph \
    && useradd -r -g langgraph langgraph

WORKDIR /app

# Установка зависимостей
RUN pip install --no-cache-dir \
    psycopg[binary] \
    langgraph-checkpoint-postgres

# Копируем скрипт миграций
COPY migrations/langgraph/setup_langgraph_tables.py .

# Изменяем владельца файлов на непривилегированного пользователя
RUN chown -R langgraph:langgraph /app

# Переключаемся на непривилегированного пользователя
USER langgraph

CMD ["python", "setup_langgraph_tables.py"]
