FROM python:3.11-slim AS base

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    g++ \
    make \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Force pip to look at PyTorch CPU wheels for all installs
ENV PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu

# Pre-install CPU-only torch to prevent override by transitive deps and enable caching
# This layer will be cached unless the Dockerfile changes
RUN pip install --no-cache-dir --upgrade pip "setuptools<70" wheel && \
    pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        --extra-index-url https://pypi.org/simple \
        "torch==2.5.1" "torchaudio==2.5.1"

# Копирование зависимостей
COPY requirements.txt .

# Установка остальных Python зависимостей
RUN pip install --no-cache-dir --no-build-isolation -r requirements.txt

# Копирование common submodule
COPY ./common /app/common

# Копирование кода приложения
ARG CACHEBUST=1
COPY ./src /app/src

# Утилиты для деплоя
COPY stamp_migrations.py /app/stamp_migrations.py

# Создание директории для логов
RUN mkdir -p /app/logs

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Healthcheck endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8001/api/v1/health || exit 1

# Expose порт
EXPOSE 8001

# Запуск приложения
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]
