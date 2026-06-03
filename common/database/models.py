"""
SQLAlchemy ORM Models - Single Source of Truth for Database Schema.

This file contains all database models used across all services (API, python-ai-service, etc.).
Any changes to the database schema should be made here and propagated via Alembic migrations.
"""
from sqlalchemy import TEXT, VARCHAR, TIMESTAMP, ForeignKey, Index, Date, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from typing import Optional, Any, List
import datetime
import uuid

from .connection import Base

# Constants for repeated string literals
USER_ID_COLUMN = "user_id"
THREAD_ID_COLUMN = "thread_id"
CREATED_AT_COLUMN = "created_at"
SOURCE_TYPE_COLUMN = "source_type"
SOURCE_ID_COLUMN = "source_id"
CASCADE_DELETE = "CASCADE"
USER_TABLE_FK = "user.id"
ENTRIES_TABLE_FK = "entries.id"
GOALS_TABLE_FK = "goals.id"
EXPERIMENTS_TABLE_FK = "experiments.id"
CONVERSATIONS_TABLE_FK = "conversations.id"
MESSAGES_TABLE_FK = "messages.id"


class User(Base):
    """User account model."""
    __tablename__ = "user"
    
    id: Mapped[str] = mapped_column(TEXT, primary_key=True)
    name: Mapped[str] = mapped_column(TEXT, nullable=False)
    email: Mapped[str] = mapped_column(TEXT, nullable=False, unique=True)
    emailVerified: Mapped[bool] = mapped_column(nullable=False)
    image: Mapped[str | None] = mapped_column(TEXT)
    phone_number: Mapped[str | None] = mapped_column(VARCHAR(20))
    bio: Mapped[str | None] = mapped_column(TEXT)
    ai_persona_tone: Mapped[str | None] = mapped_column(TEXT)
    ai_persona_role: Mapped[str | None] = mapped_column(TEXT)
    createdAt: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=func.now()
    )
    updatedAt: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now()
    )


class Conversation(Base):
    """Chat conversation model."""
    __tablename__ = "conversations"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(
        TEXT, 
        ForeignKey(USER_TABLE_FK, ondelete=CASCADE_DELETE), 
        nullable=False
    )
    thread_id: Mapped[str] = mapped_column(TEXT, unique=True, nullable=False)
    llm_provider: Mapped[str] = mapped_column(VARCHAR(50), server_default="gigachat", nullable=False)
    model: Mapped[str | None] = mapped_column(VARCHAR(100))
    provider_session_id: Mapped[str | None] = mapped_column(TEXT, unique=True)
    title: Mapped[str | None] = mapped_column(TEXT)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    last_active_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=func.now())

    # LangGraph SDK / AI Service fields
    history: Mapped[Optional[Any]] = mapped_column(JSONB, server_default='[]', nullable=True)
    context: Mapped[Optional[Any]] = mapped_column(JSONB, server_default='{}', nullable=True)
    meta_data: Mapped[Optional[Any]] = mapped_column("metadata", JSONB, server_default='{}', nullable=True)
    states: Mapped[Optional[Any]] = mapped_column(JSONB, server_default='[]', nullable=True)
    status: Mapped[str] = mapped_column(VARCHAR(50), server_default="active", nullable=False)
    
    __table_args__ = (
        Index("idx_conversations_user_id", USER_ID_COLUMN),
        Index("idx_conversations_thread_id", THREAD_ID_COLUMN),
        Index("idx_conversations_provider_session_id", "provider_session_id"),
    )


class Entry(Base):
    """Diary entry model."""
    __tablename__ = "entries"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(
        TEXT, 
        ForeignKey(USER_TABLE_FK, ondelete=CASCADE_DELETE), 
        nullable=False
    )
    title: Mapped[str | None] = mapped_column(VARCHAR(500))
    description: Mapped[str] = mapped_column(TEXT, nullable=False)
    event_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    
    # Audio transcription fields
    audio_source: Mapped[str | None] = mapped_column(VARCHAR(50))  # "upload", "stream"
    audio_duration: Mapped[float | None] = mapped_column()  # seconds
    transcription_model: Mapped[str | None] = mapped_column(VARCHAR(50))  # "whisper-turbo"
    transcription_language: Mapped[str | None] = mapped_column(VARCHAR(10))  # "ru", "en"
    audio_file_url: Mapped[str | None] = mapped_column(TEXT)  # URL to stored audio file
    life_area: Mapped[str | None] = mapped_column(VARCHAR(32))  # career|health|finance|...

    __table_args__ = (
        Index("idx_entries_user_id", USER_ID_COLUMN),
        Index("idx_entries_event_date", "event_date"),
    )


class EntryNote(Base):
    """Append-only supplement to an observation (does not overwrite original description)."""
    __tablename__ = "entry_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(ENTRIES_TABLE_FK, ondelete=CASCADE_DELETE),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        TEXT,
        ForeignKey(USER_TABLE_FK, ondelete=CASCADE_DELETE),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(TEXT, nullable=False)
    source: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, server_default="chat")
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        Index("idx_entry_notes_entry_id", "entry_id"),
        Index("idx_entry_notes_user_id", USER_ID_COLUMN),
    )


class Goal(Base):
    """Personal growth goal (canonical store in PostgreSQL, mirrored in Neo4j)."""
    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[str] = mapped_column(
        TEXT,
        ForeignKey(USER_TABLE_FK, ondelete=CASCADE_DELETE),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(VARCHAR(500))
    description: Mapped[str] = mapped_column(TEXT, nullable=False)
    status: Mapped[str] = mapped_column(VARCHAR(50), server_default="active", nullable=False)
    priority: Mapped[str | None] = mapped_column(VARCHAR(50), server_default="medium")
    target_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    achieved_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    life_area: Mapped[str | None] = mapped_column(VARCHAR(32))

    __table_args__ = (
        Index("idx_goals_user_id", USER_ID_COLUMN),
        Index("idx_goals_status", "status"),
    )


class Experiment(Base):
    """Growth experiment (canonical store in PostgreSQL, mirrored in Neo4j)."""
    __tablename__ = "experiments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[str] = mapped_column(
        TEXT,
        ForeignKey(USER_TABLE_FK, ondelete=CASCADE_DELETE),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(VARCHAR(500))
    description: Mapped[str] = mapped_column(TEXT, nullable=False)
    status: Mapped[str] = mapped_column(VARCHAR(50), server_default="active", nullable=False)
    success: Mapped[int] = mapped_column(server_default="0", nullable=False)
    outcome: Mapped[str | None] = mapped_column(TEXT, server_default="")
    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("goals.id", ondelete=CASCADE_DELETE),
        nullable=True,
    )
    phase: Mapped[str] = mapped_column(VARCHAR(20), server_default="now", nullable=False)
    due_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(VARCHAR(20), server_default="user", nullable=False)
    started_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    ended_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index("idx_experiments_user_id", USER_ID_COLUMN),
        Index("idx_experiments_status", "status"),
        Index("idx_experiments_goal_id", "goal_id"),
    )


class EntryThread(Base):
    """Relationship between diary entries and conversation threads."""
    __tablename__ = "entry_threads"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(
        TEXT, 
        ForeignKey(USER_TABLE_FK, ondelete=CASCADE_DELETE), 
        nullable=False
    )
    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey(ENTRIES_TABLE_FK, ondelete=CASCADE_DELETE), 
        nullable=False
    )
    thread_id: Mapped[str] = mapped_column(TEXT, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint("entry_id", THREAD_ID_COLUMN),
        Index("idx_entry_threads_user_entry_thread", USER_ID_COLUMN, "entry_id", THREAD_ID_COLUMN),
    )


class GoalThread(Base):
    """Relationship between goals and conversation threads."""
    __tablename__ = "goal_threads"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(
        TEXT, 
        ForeignKey(USER_TABLE_FK, ondelete=CASCADE_DELETE), 
        nullable=False
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(GOALS_TABLE_FK, ondelete=CASCADE_DELETE),
        nullable=False,
    )
    thread_id: Mapped[str] = mapped_column(TEXT, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint("goal_id", THREAD_ID_COLUMN),
        Index("idx_goal_threads_user_goal_thread", USER_ID_COLUMN, "goal_id", THREAD_ID_COLUMN),
    )


class ExperimentThread(Base):
    """Relationship between experiments and conversation threads."""
    __tablename__ = "experiment_threads"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(
        TEXT, 
        ForeignKey(USER_TABLE_FK, ondelete=CASCADE_DELETE), 
        nullable=False
    )
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(EXPERIMENTS_TABLE_FK, ondelete=CASCADE_DELETE),
        nullable=False,
    )
    thread_id: Mapped[str] = mapped_column(TEXT, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint("experiment_id", THREAD_ID_COLUMN),
        Index("idx_experiment_threads_user_experiment_thread", USER_ID_COLUMN, "experiment_id", THREAD_ID_COLUMN),
    )


class AnalysisThread(Base):
    """Relationship between analyses and conversation threads."""
    __tablename__ = "analysis_threads"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(
        TEXT, 
        ForeignKey(USER_TABLE_FK, ondelete=CASCADE_DELETE), 
        nullable=False
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    thread_id: Mapped[str] = mapped_column(TEXT, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint("analysis_id", THREAD_ID_COLUMN),
        Index("idx_analysis_threads_user_analysis_thread", USER_ID_COLUMN, "analysis_id", THREAD_ID_COLUMN),
    )


class Account(Base):
    """Authentication account model (NextAuth/Better-Auth compatible)."""
    __tablename__ = "account"
    
    id: Mapped[str] = mapped_column(TEXT, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        TEXT, 
        ForeignKey(USER_TABLE_FK, ondelete=CASCADE_DELETE), 
        nullable=False
    )
    account_id: Mapped[str] = mapped_column(TEXT, nullable=False)
    provider_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)
    password: Mapped[str | None] = mapped_column(TEXT)
    access_token: Mapped[str | None] = mapped_column(TEXT)
    access_token_expires_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    refresh_token: Mapped[str | None] = mapped_column(TEXT)
    id_token: Mapped[str | None] = mapped_column(TEXT)
    scope: Mapped[str | None] = mapped_column(TEXT)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint("provider_id", "account_id"),
        Index("idx_account_user_id", USER_ID_COLUMN),
        Index("idx_account_provider", "provider_id", "account_id"),
    )


class Session(Base):
    """User session model for authentication."""
    __tablename__ = "session"
    
    id: Mapped[str] = mapped_column(TEXT, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        TEXT, 
        ForeignKey(USER_TABLE_FK, ondelete=CASCADE_DELETE), 
        nullable=False
    )
    token: Mapped[str] = mapped_column(TEXT, unique=True, nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(VARCHAR(45))
    user_agent: Mapped[str | None] = mapped_column(TEXT)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    
    __table_args__ = (
        Index("idx_session_user_id", USER_ID_COLUMN),
        Index("idx_session_token", "token"),
        Index("idx_session_expires_at", "expires_at"),
    )


# =============================================================================
# Новые таблицы для agent-chat-ui и аналитики
# =============================================================================

class Message(Base):
    """
    Сообщения диалога для agent-chat-ui.
    Синхронизируется с LangGraph checkpoints через thread_id.
    """
    __tablename__ = "messages"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=func.gen_random_uuid()
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey(CONVERSATIONS_TABLE_FK, ondelete=CASCADE_DELETE), 
        nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        TEXT, 
        ForeignKey(USER_TABLE_FK, ondelete=CASCADE_DELETE), 
        nullable=False
    )
    role: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)  # 'user', 'assistant', 'system', 'tool'
    content: Mapped[str] = mapped_column(TEXT, nullable=False)
    meta_data: Mapped[str | None] = mapped_column("metadata", TEXT, nullable=True)  # JSON для tool_calls и прочего
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=func.now()
    )
    
    __table_args__ = (
        Index("idx_messages_conversation_id", "conversation_id"),
        Index("idx_messages_user_id", USER_ID_COLUMN),
        Index("idx_messages_created_at", CREATED_AT_COLUMN),
    )


class MessageReaction(Base):
    """Реакции на сообщения (лайки, emoji и т.д.)."""
    __tablename__ = "message_reactions"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=func.gen_random_uuid()
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey(MESSAGES_TABLE_FK, ondelete=CASCADE_DELETE), 
        nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        TEXT, 
        ForeignKey(USER_TABLE_FK, ondelete=CASCADE_DELETE), 
        nullable=False
    )
    reaction_type: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)  # 'heart', 'thumbs_up', etc.
    emoji: Mapped[str | None] = mapped_column(VARCHAR(10))  # '❤️', '👍', etc.
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=func.now()
    )
    
    __table_args__ = (
        UniqueConstraint("message_id", USER_ID_COLUMN, "reaction_type"),
        Index("idx_message_reactions_message_id", "message_id"),
    )


class IntensityMetric(Base):
    """
    Метрики интенсивности для графиков на страницах анализа и экспериментов.
    entity_type: 'entry', 'experiment', 'goal', etc.
    """
    __tablename__ = "intensity_metrics"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(
        TEXT, 
        ForeignKey(USER_TABLE_FK, ondelete=CASCADE_DELETE), 
        nullable=False
    )
    entity_type: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)  # 'entry', 'experiment'
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    intensity_value: Mapped[float] = mapped_column(nullable=False)  # -10.0 до +10.0
    metric_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(TEXT)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=func.now()
    )
    
    __table_args__ = (
        Index("idx_intensity_metrics_user_id", USER_ID_COLUMN),
        Index("idx_intensity_metrics_entity", "entity_type", "entity_id"),
        Index("idx_intensity_metrics_date", "metric_date"),
    )


class RelatedSituation(Base):
    """
    Связанные ситуации для страницы анализа опыта.
    'На что это повлияло потом?' и 'Связанные ситуации'.
    """
    __tablename__ = "related_situations"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(
        TEXT, 
        ForeignKey(USER_TABLE_FK, ondelete=CASCADE_DELETE), 
        nullable=False
    )
    source_type: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)  # 'entry', 'experiment'
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_type: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)  # 'entry', 'experiment'
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_title: Mapped[str | None] = mapped_column(TEXT)
    relation_type: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)  # 'influenced', 'related', 'caused'
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=func.now()
    )
    
    __table_args__ = (
        Index("idx_related_situations_source", SOURCE_TYPE_COLUMN, SOURCE_ID_COLUMN),
        Index("idx_related_situations_user_id", USER_ID_COLUMN),
    )


class NegativeImpact(Base):
    """
    Негативные последствия для страницы анализа опыта.
    Например: 'Плохая организация', 'Обесценивание работы'.
    """
    __tablename__ = "negative_impacts"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(
        TEXT, 
        ForeignKey(USER_TABLE_FK, ondelete=CASCADE_DELETE), 
        nullable=False
    )
    source_type: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)  # 'entry', 'experiment'
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(TEXT, nullable=False)
    description: Mapped[str | None] = mapped_column(TEXT)
    severity: Mapped[int | None] = mapped_column()  # 1-10
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=func.now()
    )
    
    __table_args__ = (
        Index("idx_negative_impacts_source", SOURCE_TYPE_COLUMN, SOURCE_ID_COLUMN),
        Index("idx_negative_impacts_user_id", USER_ID_COLUMN),
    )


class Transformation(Base):
    """
    Трансформации/уроки для страницы анализа опыта.
    Например: 'Больше не участвуем в проектах с плохой организацией'.
    """
    __tablename__ = "transformations"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(
        TEXT, 
        ForeignKey(USER_TABLE_FK, ondelete=CASCADE_DELETE), 
        nullable=False
    )
    source_type: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)  # 'entry', 'experiment', 'analysis'
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(TEXT, nullable=False)
    description: Mapped[str | None] = mapped_column(TEXT)
    category: Mapped[str | None] = mapped_column(VARCHAR(50))  # 'behavior_change', 'mindset_shift', 'boundary'
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now()
    )
    
    __table_args__ = (
        Index("idx_transformations_source", SOURCE_TYPE_COLUMN, SOURCE_ID_COLUMN),
        Index("idx_transformations_user_id", USER_ID_COLUMN),
    )


class BetaTest(Base):
    """
    Заявка на бета-тестирование (форма на https://delez.tech/beta-test).
    Таблица в БД: beta_test.
    """
    __tablename__ = "beta_test"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    telegram: Mapped[str] = mapped_column(TEXT, nullable=False)
    email: Mapped[str] = mapped_column(TEXT, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (Index("idx_beta_test_email", "email"),)
