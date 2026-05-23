"""
Audio transcription endpoints.
Вариант 2: Интеграция напрямую в api (delëz-api).
"""
import json
import logging
import asyncio
from collections import deque
from fastapi import APIRouter, Depends, Request, UploadFile, File, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from typing import Annotated, Optional

from src.api.v1.deps import get_current_user_id
from src.core.database import get_db
from src.services.auth_service import AuthService
from src.services.audio_transcription_service import AudioTranscriptionService
from src.api.v1.schemas.audio import (
    TranscriptionResponse,
    TranscriptionStreamResponse,
    TranscriptionRequest
)
from src.api.v1.schemas.entries import EntryResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/audio/transcribe",
    response_model=TranscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Transcribe audio file",
    description="Upload and transcribe an audio file (batch mode)"
)
async def transcribe_audio(
    request: Request,
    file: Annotated[UploadFile, File(description="Audio file to transcribe")],
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    title: Optional[str] = None,
    event_date: Optional[date] = None,
):
    """
    Transcribe audio file and create Entry.
    
    Supported formats: WAV, MP3, M4A, WEBM, OGG
    """
    try:
        # Validate file type
        content_type = file.content_type or ""
        if not any(ct in content_type for ct in ["audio", "video"]):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Invalid file type. Expected audio file."}
            )
        
        # Validate file size (max 100MB) — use underlying file for seek/tell
        inner = file.file
        inner.seek(0, 2)
        file_size = inner.tell()
        inner.seek(0)
        
        if file_size > 100 * 1024 * 1024:  # 100MB
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "File too large. Maximum size is 100MB."}
            )
        
        # Create service and transcribe
        service = AudioTranscriptionService(db)
        entry = await service.transcribe_file(
            audio_file=file.file,
            user_id=user_id,
            title=title,
            event_date=event_date,
        )
        
        return TranscriptionResponse(
            entry_id=entry.id,
            text=entry.description,
            language=entry.transcription_language or "unknown",
            duration=entry.audio_duration or 0.0,
            created_at=entry.created_at.isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Failed to transcribe audio", "message": str(e)}
        )


async def _get_ws_token(websocket: WebSocket) -> Optional[str]:
    """Извлечь токен из query или из первого JSON-сообщения."""
    token = websocket.query_params.get("token")
    if token:
        return token
    try:
        first_msg = await websocket.receive_json()
        if isinstance(first_msg, dict) and first_msg.get("type") == "auth":
            return first_msg.get("token")
    except (json.JSONDecodeError, WebSocketDisconnect, TypeError):
        pass
    return None


async def _audio_queue_stream(audio_queue: deque, stream_active: list):
    """Async-генератор: выдаёт чанки из очереди, пока сессия активна."""
    while stream_active[0] or audio_queue:
        if audio_queue:
            yield audio_queue.popleft()
        else:
            await asyncio.sleep(0.01)


async def _receive_audio_into_queue(
    websocket: WebSocket,
    audio_queue: deque,
    stream_active: list,
) -> None:
    """Принимает байты из WebSocket и складывает в очередь; при ошибке/отключении гасит stream_active."""
    try:
        while True:
            data = await websocket.receive_bytes()
            if not data:
                break
            audio_queue.append(data)
    except WebSocketDisconnect:
        stream_active[0] = False
    except Exception as e:
        logger.error(f"Error receiving audio: {e}")
        stream_active[0] = False


async def _send_stream_results(websocket: WebSocket, stream) -> None:
    """Читает результаты транскрипции из stream и шлёт их в WebSocket; останавливается на is_final."""
    async for result in stream:
        response = TranscriptionStreamResponse(
            text=result.get("text", ""),
            is_final=result.get("is_final", False),
            entry_id=result.get("entry_id"),
        )
        await websocket.send_json(response.model_dump())
        if result.get("is_final"):
            break


async def _run_stream_session(
    websocket: WebSocket,
    user_id: str,
    audio_queue: deque,
    stream_active: list,
):
    """Запуск сессии стриминга: приём аудио и транскрипция."""
    from src.core.database import async_session_maker

    async with async_session_maker() as db:
        service = AudioTranscriptionService(db)
        receive_task = asyncio.create_task(
            _receive_audio_into_queue(websocket, audio_queue, stream_active),
        )
        try:
            stream = service.transcribe_stream(
                _audio_queue_stream(audio_queue, stream_active),
                user_id=user_id,
                title=None,
                event_date=None,
            )
            await _send_stream_results(websocket, stream)
        finally:
            receive_task.cancel()
            await receive_task  # CancelledError propagates


@router.websocket("/audio/stream")
async def stream_audio_transcription(websocket: WebSocket):
    """
    Stream audio transcription in real-time.

    WebSocket protocol:
    - Client sends: binary audio chunks
    - Server sends: JSON messages with transcription updates
    - Authentication: token in query ?token=... or first message {"type":"auth","token":"..."}
    """
    await websocket.accept()
    try:
        token = await _get_ws_token(websocket)
        if not token:
            await websocket.close(code=1008, reason="Authentication required")
            return

        from src.core.database import async_session_maker

        async with async_session_maker() as db:
            auth_service = AuthService(db)
            try:
                user, _ = await auth_service.validate_session(token)
            except Exception:
                await websocket.close(code=1008, reason="Invalid token")
                return
            user_id = user.id

        audio_queue = deque()
        stream_active = [True]
        await _run_stream_session(websocket, user_id, audio_queue, stream_active)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in audio stream: {e}")
        try:
            await websocket.close(code=1011, reason=str(e))
        except Exception:
            pass
