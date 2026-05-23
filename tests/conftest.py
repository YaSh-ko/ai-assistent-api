# tests/conftest.py
import os
import sys
import types
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

# ==================== 1. НАСТРОЙКА PYTHONPATH ====================
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def _ensure_jwt_keys_for_tests() -> None:
    """RS256: всегда генерируем свежие ключи для тестов, чтобы избежать проблем с 'грязными' переменными из CI."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pub_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    os.environ["JWT_PRIVATE_KEY_PEM"] = priv_pem
    os.environ["JWT_PUBLIC_KEY_PEM"] = pub_pem
    os.environ.setdefault("JWT_ISSUER", "delez-api-test")


_ensure_jwt_keys_for_tests()

# ==================== 1b. STUB common.database.models (CI без submodules) ====================
# В GitLab CI submodules могут быть отключены (Skipping Git submodules setup),
# из-за чего импорт `common.database.models` падает. Для тестов достаточно stub'а.
def _install_common_models_stub() -> None:
    if "common.database.models" in sys.modules:
        return

    common_mod = types.ModuleType("common")
    database_mod = types.ModuleType("common.database")
    models_mod = types.ModuleType("common.database.models")

    # Минимальные SQLAlchemy-модели, чтобы работали select()/delete() в сервисах.
    from sqlalchemy.orm import declarative_base, Mapped, mapped_column
    from sqlalchemy import TEXT, TIMESTAMP
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID
    import datetime
    import uuid

    Base = declarative_base()

    class User(Base):
        __tablename__ = "user"
        id: Mapped[str] = mapped_column(TEXT, primary_key=True)
        email: Mapped[str] = mapped_column(TEXT)
        name: Mapped[str] = mapped_column(TEXT, default="")
        emailVerified: Mapped[bool] = mapped_column(default=False)

    class Account(Base):
        __tablename__ = "account"
        id: Mapped[str] = mapped_column(TEXT, primary_key=True)
        user_id: Mapped[str] = mapped_column(TEXT)
        account_id: Mapped[str] = mapped_column(TEXT, default="")
        provider_id: Mapped[str] = mapped_column(TEXT, default="credential")
        password: Mapped[str] = mapped_column(TEXT, default="")
        access_token: Mapped[str | None] = mapped_column(TEXT, nullable=True)
        access_token_expires_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    class Session(Base):
        __tablename__ = "session"
        id: Mapped[str] = mapped_column(TEXT, primary_key=True)
        user_id: Mapped[str] = mapped_column(TEXT)
        token: Mapped[str] = mapped_column(TEXT)
        expires_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.datetime.now)
        ip_address: Mapped[str | None] = mapped_column(TEXT, nullable=True)
        user_agent: Mapped[str | None] = mapped_column(TEXT, nullable=True)

    class Conversation(Base):
        __tablename__ = "conversations"
        id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        user_id: Mapped[str] = mapped_column(TEXT, default="")
        thread_id: Mapped[str] = mapped_column(TEXT, default="")
        last_active_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.datetime.now)

    class Entry(Base):
        __tablename__ = "entries"
        id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        user_id: Mapped[str] = mapped_column(TEXT, default="")
        event_date: Mapped[datetime.date | None] = mapped_column(nullable=True)
        title: Mapped[str | None] = mapped_column(TEXT, nullable=True)
        description: Mapped[str | None] = mapped_column(TEXT, nullable=True)

    class IntensityMetric(Base):
        __tablename__ = "intensity_metrics"
        id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    class RelatedSituation(Base):
        __tablename__ = "related_situations"
        id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    class NegativeImpact(Base):
        __tablename__ = "negative_impacts"
        id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    class Transformation(Base):
        __tablename__ = "transformations"
        id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    class Message(Base):
        __tablename__ = "messages"
        id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        conversation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), default=uuid.uuid4)
        created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.datetime.now)
        updated_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.datetime.now)
        user_id: Mapped[str] = mapped_column(TEXT, default="")
        role: Mapped[str] = mapped_column(TEXT, default="user")
        content: Mapped[str] = mapped_column(TEXT, default="")
        meta_data: Mapped[str | None] = mapped_column(TEXT, nullable=True)

    class MessageReaction(Base):
        __tablename__ = "message_reactions"
        id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        message_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), default=uuid.uuid4)

    class EntryThread(Base):
        __tablename__ = "entry_threads"
        id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        entry_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True))
        thread_id: Mapped[str] = mapped_column(TEXT)
        context_type: Mapped[str | None] = mapped_column(TEXT, nullable=True)

    for cls in (
        User,
        Account,
        Session,
        Conversation,
        Entry,
        IntensityMetric,
        RelatedSituation,
        NegativeImpact,
        Transformation,
        Message,
        MessageReaction,
        EntryThread,
    ):
        setattr(models_mod, cls.__name__, cls)

    sys.modules["common"] = common_mod
    sys.modules["common.database"] = database_mod
    sys.modules["common.database.models"] = models_mod


_install_common_models_stub()

# ==================== 2. ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ====================
# Пароли для тестов — из окружения или тестовые подстановки (не для production)
_postgres_password = os.environ.get("POSTGRES_PASSWORD", "test_password")
_neo4j_password = os.environ.get("NEO4J_PASSWORD", "test")

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/test")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.update({
    "PROJECT_NAME": "API Test",
    "DEBUG": "false",
    "POSTGRES_PORT": "5432",
    "POSTGRES_DB": "test_db",
    "POSTGRES_USER": "test_user",
    "POSTGRES_PASSWORD": _postgres_password,
    "NEO4J_URI": "bolt://localhost:7687",
    "NEO4J_USER": "neo4j",
    "NEO4J_PASSWORD": _neo4j_password,
    "CHROMADB_HOST": "localhost",
    "CHROMADB_PORT": "8001",
    "AI_SERVICE_URL": "http://localhost:8000",
    "WHISPER_MODEL": "tiny",
    "WHISPER_LANGUAGE": "ru",
    "WHISPER_DEVICE": "cpu",
    "LANGGRAPH_API_URL": "http://localhost:2024",
    "CORS_ORIGINS": "http://localhost:3000,http://127.0.0.1:3000",
})

from src.core.database import get_db
from src.main import create_app


async def _override_get_db():
    """Тестовая сессия — мок, чтобы не дергать реальную БД."""
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.close = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
    yield session


# ==================== 3. ФИКСТУРА ДЛЯ МОКОВ ВНЕШНИХ ЗАВИСИМОСТЕЙ ====================
@pytest.fixture(autouse=True)
def mock_all_external():
    """Мокаем ВСЕ внешние зависимости перед каждым тестом."""
    mock_neo4j_driver = MagicMock()
    mock_neo4j_session = MagicMock()
    mock_neo4j_session.run = MagicMock(return_value=MagicMock())
    mock_neo4j_driver.session = MagicMock(return_value=mock_neo4j_session)
    mock_whisper_client = MagicMock()
    mock_whisper_client.model_name = "tiny"
    with patch('neo4j.GraphDatabase.driver', return_value=mock_neo4j_driver), \
         patch('asyncpg.create_pool', return_value=AsyncMock()), \
         patch('sqlalchemy.ext.asyncio.create_async_engine', return_value=AsyncMock()), \
         patch('httpx.AsyncClient', return_value=AsyncMock()), \
         patch('src.infrastructure.whisper_streaming_client.get_whisper_client', return_value=mock_whisper_client), \
         patch('src.infrastructure.neo4j_client.neo4j_client', MagicMock()), \
         patch('src.infrastructure.neo4j_client.Neo4jClient', MagicMock()):
        yield


# ==================== 4. ФИКСТУРЫ ПРИЛОЖЕНИЯ ====================
@pytest.fixture
def app():
    """Приложение с переопределённым get_db."""
    _app = create_app()
    _app.dependency_overrides[get_db] = _override_get_db
    return _app


@pytest.fixture
def client(app):
    """HTTP-клиент для запросов к API."""
    return TestClient(app)


@pytest.fixture
def test_jwt_keys():
    """PEM-ключи RS256 из окружения (ставит conftest до импорта приложения)."""
    return (
        os.environ["JWT_PRIVATE_KEY_PEM"],
        os.environ["JWT_PUBLIC_KEY_PEM"],
        os.environ.get("JWT_ISSUER", "delez-api-test"),
    )


# ==================== 5. ДОПОЛНИТЕЛЬНЫЕ ФИКСТУРЫ ====================
@pytest.fixture
def mock_db_session():
    """Фиктивная асинхронная сессия БД."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    yield session


@pytest.fixture
def mock_neo4j_client():
    """Фиктивный Neo4j клиент."""
    client = MagicMock()
    client.execute_query = MagicMock(return_value=[])
    client.execute_query_async = AsyncMock(return_value=[])
    client.get_rhizome_graph = AsyncMock(return_value={"nodes": [], "links": []})
    client.search_nodes = AsyncMock(return_value=[])
    client.get_node_by_id = AsyncMock(return_value=None)
    client.get_related_nodes = AsyncMock(return_value=[])
    client.close = MagicMock()
    yield client
