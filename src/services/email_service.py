"""
Email service for sending emails via SMTP.
Uses Mail.ru SMTP for password reset and other notifications.
"""
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr
from typing import Optional

import aiosmtplib

from src.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via SMTP."""
    
    def __init__(self):
        self.smtp_host = settings.EmailConfiguration.SmtpServer
        self.smtp_port = settings.EmailConfiguration.Port
        self.smtp_username = settings.EmailConfiguration.Username
        self.smtp_password = settings.EmailConfiguration.Password
        self.from_email = settings.EmailConfiguration.From
        self.from_name = "delez"  # ASCII only for Mail.ru compatibility
    
    async def send_email(
        self, 
        to_email: str, 
        subject: str, 
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send an email via SMTP.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML content of the email
            text_content: Optional plain text fallback
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        if not self.smtp_username or not self.smtp_password:
            logger.warning("SMTP credentials not configured, skipping email send")
            return False
        
        # Debug logging
        logger.info(f"Attempting to send email to {to_email}")
        logger.info(f"SMTP config: host={self.smtp_host}, port={self.smtp_port}, from={self.from_email}")
        
        try:
            # Create message
            message = MIMEMultipart("alternative")
            # Use formataddr with Header for proper RFC 2047 encoding
            message["From"] = formataddr((str(Header(self.from_name, "utf-8")), self.from_email))
            message["To"] = to_email
            message["Subject"] = str(Header(subject, "utf-8"))
            
            # Add text part if provided
            if text_content:
                text_part = MIMEText(text_content, "plain", "utf-8")
                message.attach(text_part)
            
            # Add HTML part
            html_part = MIMEText(html_content, "html", "utf-8")
            message.attach(html_part)
            
            # Send email via SMTP
            # Port 465 usually uses implicit TLS (SSL), while 587 uses STARTTLS
            use_tls = self.smtp_port == 465
            start_tls = self.smtp_port != 465
            
            logger.info(f"Connecting to SMTP: use_tls={use_tls}, start_tls={start_tls}")
            
            await aiosmtplib.send(
                message,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_username,
                password=self.smtp_password,
                use_tls=use_tls,
                start_tls=start_tls,
            )
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except aiosmtplib.SMTPException as e:
            logger.error(f"SMTP error sending email to {to_email}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {str(e)}")
            return False
    
    async def send_password_reset_email(
        self, 
        to_email: str, 
        user_name: str,
        reset_token: str,
        reset_url_base: str = "https://delez.tech/reset-password"
    ) -> bool:
        """
        Send password reset email with styled template.
        
        Args:
            to_email: User's email address
            user_name: User's display name for personalization
            reset_token: Password reset token
            reset_url_base: Base URL for reset password page
            
        Returns:
            True if email was sent successfully
        """
        reset_link = f"{reset_url_base}?token={reset_token}"
        
        subject = "Сброс пароля - Delёz"
        
        html_content = self._get_password_reset_template(
            user_name=user_name,
            reset_link=reset_link
        )
        
        text_content = f"""
Здравствуйте, {user_name}!

Вы запросили сброс пароля для вашего аккаунта delëz.

Перейдите по ссылке для создания нового пароля:
{reset_link}

Ссылка действительна в течение 1 часа.

Если вы не запрашивали сброс пароля, просто проигнорируйте это письмо.

С уважением,
Команда delëz
        """.strip()
        
        return await self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content
        )
    
    async def send_verification_email(
        self, 
        to_email: str, 
        user_name: str,
        verification_token: str,
        verify_url_base: str = "https://delez.tech/verify-email"
    ) -> bool:
        """
        Send email verification email with styled template.
        """
        verify_link = f"{verify_url_base}?token={verification_token}"
        
        subject = "Подтверждение почты - Delёz"
        
        html_content = self._get_verification_template(
            user_name=user_name,
            verify_link=verify_link
        )
        
        text_content = f"""
Здравствуйте, {user_name}!

Благодарим вас за регистрацию в delëz.

Для завершения регистрации, пожалуйста, подтвердите ваш адрес электронной почты, перейдя по ссылке:
{verify_link}

С уважением,
Команда delëz
        """.strip()
        
        return await self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content
        )
    
    def _email_layout(
        self,
        page_title: str,
        logo_text: str,
        heading: str,
        user_name: str,
        message: str,
        button_text: str,
        button_link: str,
        extra_rows: str = "",
        footer_text: str = "&copy; 2026 DELEZ. Все права защищены.",
    ) -> str:
        """Общая разметка письма (убирает дублирование HTML)."""
        return f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page_title}</title>
    <style>
        @keyframes float {{
            0%, 100% {{ transform: translateY(0px); }}
            50% {{ transform: translateY(-10px); }}
        }}
        .particle {{
            position: absolute;
            width: 3px;
            height: 3px;
            background: rgba(0, 212, 255, 0.6);
            border-radius: 50%;
            animation: float 3s ease-in-out infinite;
        }}
    </style>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 100%); position: relative; overflow: hidden;">
    <!-- Particle Background -->
    <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 0;">
        <svg width="100%" height="100%" style="position: absolute; top: 0; left: 0;">
            <defs>
                <filter id="glow">
                    <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                    <feMerge>
                        <feMergeNode in="coloredBlur"/>
                        <feMergeNode in="SourceGraphic"/>
                    </feMerge>
                </filter>
            </defs>
            <!-- Particles -->
            <circle cx="10%" cy="15%" r="2" fill="rgba(0, 212, 255, 0.4)" filter="url(#glow)"/>
            <circle cx="85%" cy="20%" r="2" fill="rgba(0, 212, 255, 0.4)" filter="url(#glow)"/>
            <circle cx="15%" cy="75%" r="2" fill="rgba(0, 212, 255, 0.4)" filter="url(#glow)"/>
            <circle cx="90%" cy="80%" r="2" fill="rgba(0, 212, 255, 0.4)" filter="url(#glow)"/>
            <circle cx="50%" cy="10%" r="2" fill="rgba(0, 212, 255, 0.4)" filter="url(#glow)"/>
            <circle cx="30%" cy="40%" r="2" fill="rgba(0, 212, 255, 0.4)" filter="url(#glow)"/>
            <circle cx="70%" cy="50%" r="2" fill="rgba(0, 212, 255, 0.4)" filter="url(#glow)"/>
            <circle cx="20%" cy="90%" r="2" fill="rgba(0, 212, 255, 0.4)" filter="url(#glow)"/>
            <!-- Connection Lines -->
            <line x1="10%" y1="15%" x2="50%" y2="10%" stroke="rgba(0, 212, 255, 0.2)" stroke-width="1"/>
            <line x1="50%" y1="10%" x2="85%" y2="20%" stroke="rgba(0, 212, 255, 0.2)" stroke-width="1"/>
            <line x1="10%" y1="15%" x2="30%" y2="40%" stroke="rgba(0, 212, 255, 0.2)" stroke-width="1"/>
            <line x1="30%" y1="40%" x2="70%" y2="50%" stroke="rgba(0, 212, 255, 0.2)" stroke-width="1"/>
            <line x1="70%" y1="50%" x2="85%" y2="20%" stroke="rgba(0, 212, 255, 0.2)" stroke-width="1"/>
            <line x1="30%" y1="40%" x2="15%" y2="75%" stroke="rgba(0, 212, 255, 0.2)" stroke-width="1"/>
            <line x1="15%" y1="75%" x2="20%" y2="90%" stroke="rgba(0, 212, 255, 0.2)" stroke-width="1"/>
            <line x1="70%" y1="50%" x2="90%" y2="80%" stroke="rgba(0, 212, 255, 0.2)" stroke-width="1"/>
        </svg>
    </div>
    
    <table role="presentation" style="width: 100%; border-collapse: collapse; position: relative; z-index: 1;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" style="width: 100%; max-width: 600px; border-collapse: collapse; background: rgba(10, 14, 39, 0.8); border-radius: 12px; backdrop-filter: blur(10px); border: 1px solid rgba(0, 212, 255, 0.1);">
                    <tr>
                        <td align="center" style="padding: 40px 30px 30px 30px;">
                            <div style="font-size: 32px; font-weight: 700; color: #00d4ff; letter-spacing: 2px; text-shadow: 0 0 20px rgba(0, 212, 255, 0.5);">{logo_text}</div>
                        </td>
                    </tr>
                    <tr>
                        <td align="center" style="padding: 0 30px 20px 30px;">
                            <h1 style="margin: 0; font-size: 24px; font-weight: 700; color: #ffffff;">{heading}</h1>
                        </td>
                    </tr>
                    <tr>
                        <td align="center" style="padding: 0 30px 15px 30px;">
                            <p style="margin: 0; font-size: 16px; color: #cbd5e0;">Здравствуйте, {user_name}!</p>
                        </td>
                    </tr>
                    <tr>
                        <td align="center" style="padding: 0 30px 30px 30px;">
                            <p style="margin: 0; font-size: 15px; color: #a0aec0; line-height: 1.6;">{message}</p>
                        </td>
                    </tr>
                    <tr>
                        <td align="center" style="padding: 0 30px 25px 30px;">
                            <a href="{button_link}" style="display: inline-block; padding: 16px 48px; background: linear-gradient(135deg, #00d4ff 0%, #0099cc 100%); color: #0a0e27; text-decoration: none; font-size: 15px; font-weight: 700; border-radius: 8px; box-shadow: 0 4px 15px rgba(0, 212, 255, 0.3); transition: all 0.3s ease;">{button_text}</a>
                        </td>
                    </tr>
                    {extra_rows}
                    <tr>
                        <td align="center" style="padding: 30px 30px 40px 30px; border-top: 1px solid rgba(0, 212, 255, 0.1);">
                            <p style="margin: 0; font-size: 12px; color: #718096;">{footer_text}</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
        """.strip()

    def _get_password_reset_template(self, user_name: str, reset_link: str) -> str:
        """Generate HTML template for password reset email."""
        extra = """
                    <tr>
                        <td align="center" style="padding: 0 0 25px 0;">
                            <p style="margin: 0; font-size: 14px; color: #38b2ac;">Ссылка действительна в течение 1 часа.</p>
                        </td>
                    </tr>
                    <tr>
                        <td align="center" style="padding: 0 0 30px 0;">
                            <p style="margin: 0; font-size: 13px; color: #718096;">Если вы не запрашивали сброс пароля, просто проигнорируйте это письмо.</p>
                        </td>
                    </tr>
        """
        return self._email_layout(
            page_title="Сброс пароля - Delёz",
            logo_text="DELEZ",
            heading="Сброс пароля",
            user_name=user_name,
            message="Вы запросили сброс пароля для вашего аккаунта. Нажмите на кнопку ниже, чтобы создать новый пароль:",
            button_text="Сбросить пароль",
            button_link=reset_link,
            extra_rows=extra,
        )

    def _get_verification_template(self, user_name: str, verify_link: str) -> str:
        """Generate HTML template for email verification."""
        return self._email_layout(
            page_title="Подтверждение почты - Delёz",
            logo_text="Delёz",
            heading="Подтверждение почты",
            user_name=user_name,
            message="Благодарим вас за регистрацию. Нажмите на кнопку ниже, чтобы подтвердить ваш адрес электронной почты:",
            button_text="Подтвердить почту",
            button_link=verify_link,
            footer_text="&copy; 2026 Delёz. Все права защищены.",
        )


# Singleton instance
email_service = EmailService()
