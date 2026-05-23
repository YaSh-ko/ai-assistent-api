# tests/unit/test_email_service.py
"""Unit-тесты EmailService."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.services.email_service import EmailService


@pytest.mark.asyncio
async def test_send_email_returns_false_when_no_credentials():
    """Без SMTP credentials send_email возвращает False."""
    with patch("src.services.email_service.settings") as m_settings:
        m_settings.EmailConfiguration = MagicMock()
        m_settings.EmailConfiguration.Username = None
        m_settings.EmailConfiguration.Password = ""
        m_settings.EmailConfiguration.SmtpServer = "smtp.example.com"
        m_settings.EmailConfiguration.Port = 587
        m_settings.EmailConfiguration.From = "noreply@example.com"
        svc = EmailService()
    result = await svc.send_email("to@example.com", "Subject", "<p>Hi</p>")
    assert result is False


@pytest.mark.asyncio
async def test_send_email_success_when_credentials_set():
    """С настроенным SMTP send_email вызывает aiosmtplib.send и возвращает True."""
    with patch("src.services.email_service.settings") as m_settings:
        m_settings.EmailConfiguration = MagicMock()
        m_settings.EmailConfiguration.Username = "user"
        m_settings.EmailConfiguration.Password = "secret"
        m_settings.EmailConfiguration.SmtpServer = "smtp.example.com"
        m_settings.EmailConfiguration.Port = 587
        m_settings.EmailConfiguration.From = "noreply@example.com"
        with patch("src.services.email_service.aiosmtplib.send", new_callable=AsyncMock):
            svc = EmailService()
            result = await svc.send_email("to@example.com", "Subj", "<p>Hi</p>")
    assert result is True


@pytest.mark.asyncio
async def test_send_verification_email_calls_send_email():
    """send_verification_email формирует письмо и вызывает send_email."""
    svc = EmailService()
    svc.send_email = AsyncMock(return_value=True)
    result = await svc.send_verification_email("u@x.com", "User", "token123")
    assert result is True
    svc.send_email.assert_called_once()
    call_kw = svc.send_email.call_args[1]
    assert call_kw["to_email"] == "u@x.com"
    assert "token123" in call_kw["html_content"] or "token123" in (call_kw.get("text_content") or "")


@pytest.mark.asyncio
async def test_send_password_reset_email_calls_send_email():
    """send_password_reset_email формирует письмо и вызывает send_email."""
    svc = EmailService()
    svc.send_email = AsyncMock(return_value=True)
    result = await svc.send_password_reset_email("u@x.com", "User", "reset-tok", "https://app.com")
    assert result is True
    svc.send_email.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_smtp_exception_returns_false():
    """При SMTPException send_email возвращает False (стр. 94-97)."""
    import aiosmtplib
    with patch("src.services.email_service.settings") as m_settings:
        m_settings.EmailConfiguration = MagicMock()
        m_settings.EmailConfiguration.Username = "u"
        m_settings.EmailConfiguration.Password = "p"
        m_settings.EmailConfiguration.SmtpServer = "smtp.x.com"
        m_settings.EmailConfiguration.Port = 587
        m_settings.EmailConfiguration.From = "noreply@x.com"
        with patch("src.services.email_service.aiosmtplib.send", new_callable=AsyncMock, side_effect=aiosmtplib.SMTPException("fail")):
            svc = EmailService()
            result = await svc.send_email("to@x.com", "Subj", "<p>Hi</p>")
    assert result is False
