"""
Configuration for API service using Pydantic Settings.
"""
import json
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
from typing import Optional
from pydantic import BaseModel
from pydantic import Field

class EmailConfigModel(BaseModel):
    # Email (SMTP) настройки
    # Используем вложенную модель для поддержки формата EmailConfiguration__SmtpServer
    From: str = "noreply@delez.tech"
    SmtpServer: str = "smtp.gmail.com"
    Port: int = 587
    Username: Optional[str] = None
    Password: str = ""


class Settings(BaseSettings):
    # Project
    PROJECT_NAME: str = "delëz API"
    DEBUG: bool = False
    
    # PostgreSQL - можно задать либо DATABASE_URL напрямую, либо отдельные переменные
    DATABASE_URL: Optional[str] = None
    POSTGRES_HOST: Optional[str] = None  # Должен быть задан через переменную окружения
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "db_for_delez"
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: str = ""
    
    @property
    def db_url(self) -> str:
        """Возвращает DATABASE_URL если задан, иначе собирает из компонентов"""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        
        # Проверяем, что все необходимые параметры заданы
        # Fallback defaults to prevent crashes if variables are missing
        host = (self.POSTGRES_HOST or "Postgres_host_missing").strip()
        port = self.POSTGRES_PORT or 5432
        user = (self.POSTGRES_USER or "postgres").strip()
        password = (self.POSTGRES_PASSWORD or "").strip()
        db = (self.POSTGRES_DB or "postgres").strip()

        # Debug print to help identify what's wrong (masked password)
        print(f"DEBUG: Assembling DB URL with host='{host}', port={port}, user='{user}', db='{db}'")

        # Encode credentials to handle special characters safely
        from urllib.parse import quote_plus
        encoded_user = quote_plus(user)
        encoded_password = quote_plus(password)
        
        return f"postgresql+asyncpg://{encoded_user}:{encoded_password}@{host}:{port}/{db}"
    
    # Neo4j (локальная разработка; переопределяется через .env)
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""
    
    # ChromaDB (mapped to 8001 in docker-compose.staging.yml)
    CHROMADB_HOST: str = "localhost"
    CHROMADB_PORT: int = 8001
    
    # AI Service (mapped to 8000 in docker-compose.staging.yml)
    AI_SERVICE_URL: str = "http://localhost:8000"
    
    # LangGraph
    LANGGRAPH_API_URL: str = "http://localhost:2024"
    
    # Whisper
    WHISPER_MODEL: str = "turbo"  # tiny, base, small, medium, large, turbo
    WHISPER_LANGUAGE: Optional[str] = None  # None = автоопределение, "ru", "en", etc.
    WHISPER_DEVICE: str = "cpu"  # "cpu" или "cuda" (если доступно GPU)
    
    EmailConfiguration: EmailConfigModel = Field(default_factory=EmailConfigModel)
    
    # Auth
    BETTER_AUTH_SECRET: str = "change_me_in_production"
    SESSION_LIFETIME_DAYS: int = 7
    # JWT сессии (RS256): PEM целиком в переменной окружения (многострочный через \\n в .env)
    JWT_ISSUER: Optional[str] = "delez-api"
    JWT_PRIVATE_KEY_PEM: Optional[str] = None
    JWT_PUBLIC_KEY_PEM: Optional[str] = None
    # Допуск по часам (exp/nbf/iat) при проверке JWT; 0 — строго по UTC сервера
    JWT_LEEWAY_SECONDS: int = Field(default=120, ge=0, le=3600)
    # Если задано, в JWT добавляется claim `aud` и проверяется при decode
    JWT_AUDIENCE: Optional[str] = None

    # Rate limit (in-memory per process)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, ge=1, le=3600)
    RATE_LIMIT_MAX_REQUESTS: int = Field(default=300, ge=1, le=10000)
    # Route prefixes excluded from global limiter
    RATE_LIMIT_EXCLUDE_PATHS: str = "/docs,/redoc,/openapi.json,/v1/health"
    # Registration anti-abuse: how many sign-ups allowed per IP per window
    SIGNUP_IP_LIMIT_ENABLED: bool = True
    SIGNUP_IP_WINDOW_SECONDS: int = Field(default=86400, ge=60, le=31536000)
    SIGNUP_IP_MAX_REGISTRATIONS: int = Field(default=1, ge=1, le=100)

    @model_validator(mode="after")
    def normalize_jwt_pem_from_env(self):
        """PEM из .env часто приходит с литеральными \\n — приводим к реальным переводам строк."""
        from src.core.jwt_auth import normalize_pem

        if self.JWT_PRIVATE_KEY_PEM:
            self.JWT_PRIVATE_KEY_PEM = normalize_pem(self.JWT_PRIVATE_KEY_PEM)
        if self.JWT_PUBLIC_KEY_PEM:
            self.JWT_PUBLIC_KEY_PEM = normalize_pem(self.JWT_PUBLIC_KEY_PEM)
        return self
    
    # CORS — по умолчанию только localhost (прод добавляйте явно в .env, если нужно)
    CORS_ORIGINS: str | list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
    ]

    _BLOCKED_DB_HOST_FRAGMENTS: tuple[str, ...] = (
        "delez-repo.ru",
        "neo4j.delez",
        "85.198.103.254",
        "philosophy_staging",
    )
    
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list) -> list[str]:
        """Парсит CORS_ORIGINS из различных форматов."""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # Пробуем распарсить как JSON
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
            # Если не JSON, пробуем разделить по запятой
            if "," in v:
                return [origin.strip() for origin in v.split(",") if origin.strip()]
            # Иначе возвращаем как список с одним элементом
            return [v.strip()] if v.strip() else []
        return []

    @model_validator(mode="after")
    def reject_remote_production_database_hosts(self) -> "Settings":
        """Не подключаться к прод/удалённым БД, если хост случайно попал в .env."""
        if os.getenv("ALLOW_REMOTE_DATABASE", "").lower() in ("1", "true", "yes"):
            return self
        combined = f"{self.db_url} {self.NEO4J_URI} {self.POSTGRES_HOST or ''}"
        for fragment in self._BLOCKED_DB_HOST_FRAGMENTS:
            if fragment in combined:
                raise ValueError(
                    f"Refusing remote/production database host fragment {fragment!r}. "
                    "Use local .env (see .env.example) or set ALLOW_REMOTE_DATABASE=true."
                )
        return self
    
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_nested_delimiter="__",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
