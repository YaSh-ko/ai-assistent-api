"""
Whisper Streaming client for audio transcription.
Infrastructure layer for Whisper integration (Вариант 2).
"""
import asyncio
import logging
import os
import tempfile
from typing import AsyncGenerator, BinaryIO, Optional

from src.core.config import settings

logger = logging.getLogger(__name__)


class WhisperStreamingClient:
    """Client for Whisper audio transcription."""
    
    def __init__(self):
        """Initialize Whisper model."""
        self.model = None
        self.model_name = settings.WHISPER_MODEL
        self.device = settings.WHISPER_DEVICE
        self.language = settings.WHISPER_LANGUAGE
        self._load_model()
    
    def _load_model(self):
        """Load Whisper model."""
        import whisper  # type: ignore[import-untyped]  # lazy to allow tests without whisper
        try:
            logger.info(f"Loading Whisper model: {self.model_name} on {self.device}")
            self.model = whisper.load_model(
                self.model_name,
                device=self.device
            )
            logger.info(f"Whisper model {self.model_name} loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise
    
    def _transcribe_file_sync(
        self,
        audio_file: BinaryIO,
        language: Optional[str],
        kwargs: dict,
    ) -> dict:
        """Blocking transcription (run in executor)."""
        if self.model is None:
            raise RuntimeError("Whisper model not loaded")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            tmp_path = tmp_file.name
            audio_file.seek(0)
            tmp_file.write(audio_file.read())
        try:
            result = self.model.transcribe(
                tmp_path,
                language=language or self.language,
                **kwargs
            )
            return {
                "text": result.get("text", "").strip(),
                "language": result.get("language", "unknown"),
                "segments": result.get("segments", []),
                "duration": self._calculate_duration(result.get("segments", [])),
            }
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    async def transcribe_file(
        self,
        audio_file: BinaryIO,
        language: Optional[str] = None,
        **kwargs
    ) -> dict:
        """
        Transcribe audio file (batch mode).
        Runs blocking Whisper work in executor to avoid blocking the event loop.
        """
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: self._transcribe_file_sync(audio_file, language, kwargs),
            )
        except Exception as e:
            logger.error("Error transcribing audio file: %s", e)
            raise
    
    def _transcribe_chunk(
        self,
        chunk_bytes: bytes,
        language: Optional[str],
        segment_index: int,
        is_final: bool,
        **kwargs
    ) -> Optional[dict]:
        """Транскрибирует один чанк через временный файл и возвращает результат или None."""
        if self.model is None:
            raise RuntimeError("Whisper model not loaded")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            tmp_path = tmp_file.name
            tmp_file.write(chunk_bytes)
        try:
            result = self.model.transcribe(
                tmp_path,
                language=language or self.language,
                **kwargs
            )
            text = result.get("text", "").strip()
            if not text:
                return None
            return {
                "text": text,
                "is_final": is_final,
                "language": result.get("language", "unknown"),
                "segment_index": segment_index,
            }
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    async def transcribe_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language: Optional[str] = None,
        chunk_size: int = 16000,  # ~1 second of audio at 16kHz
        **kwargs
    ) -> AsyncGenerator[dict, None]:
        """
        Transcribe audio stream (streaming mode).

        Note: Whisper doesn't natively support streaming, so we process chunks
        and yield partial results. For true streaming, consider whisper_streaming library.
        """
        audio_chunks = []
        segment_index = 0

        async for chunk in audio_stream:
            audio_chunks.append(chunk)
            total = len(b"".join(audio_chunks))
            if total < chunk_size:
                continue

            out = self._transcribe_chunk(
                b"".join(audio_chunks),
                language,
                segment_index,
                is_final=False,
                **kwargs,
            )
            if out:
                yield out
                segment_index += 1
            audio_chunks = []

        if not audio_chunks:
            return
        out = self._transcribe_chunk(
            b"".join(audio_chunks),
            language,
            segment_index,
            is_final=True,
            **kwargs,
        )
        if out:
            yield out
    
    def _calculate_duration(self, segments: list) -> float:
        """Calculate total duration from segments."""
        if not segments:
            return 0.0
        return max(segment.get("end", 0) for segment in segments)
    
    def get_model_info(self) -> dict:
        """Get information about loaded model."""
        return {
            "model": self.model_name,
            "device": self.device,
            "language": self.language or "auto",
            "is_loaded": self.model is not None
        }


# Singleton instance
_whisper_client: Optional[WhisperStreamingClient] = None


def get_whisper_client() -> WhisperStreamingClient:
    """Get or create Whisper client singleton."""
    global _whisper_client
    if _whisper_client is None:
        _whisper_client = WhisperStreamingClient()
    return _whisper_client
