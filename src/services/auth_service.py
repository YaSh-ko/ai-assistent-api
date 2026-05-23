"""
Authentication service - business logic for user authentication.
"""
import hashlib
import secrets
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

import jwt as pyjwt

from common.database.models import User, Account, Session
from src.core.config import settings
from src.core.jwt_auth import (
    decode_session_jwt,
    encode_session_jwt,
    looks_like_jwt,
    tokens_equal_constant_time,
)
from src.core.exceptions import (
    InvalidCredentialsException,
    UserAlreadyExistsException,
    UserNotFoundException,
    InvalidTokenException,
    SessionExpiredException,
    UnauthorizedException,
    BadRequestException,
    JwtConfigurationException,
)

logger = logging.getLogger(__name__)


class AuthService:
    """Service for handling authentication operations."""
    
    # Session lifetime from config
    SESSION_LIFETIME_DAYS = settings.SESSION_LIFETIME_DAYS
    # Password reset token lifetime in hours
    RESET_TOKEN_LIFETIME_HOURS = 1
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ========================================================================
    # Password Hashing
    # ========================================================================
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using SHA256 with salt."""
        salt = secrets.token_hex(16)
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return f"{salt}:{password_hash}"
    
    @staticmethod
    def verify_password(password: str, stored_hash: str) -> bool:
        """Verify password against stored hash."""
        if not password or not stored_hash:
            return False
        try:
            if ":" not in stored_hash:
                return False
            salt, password_hash = stored_hash.split(":", 1)
            if not salt or not password_hash:
                return False
            return hashlib.sha256((password + salt).encode()).hexdigest() == password_hash
        except (ValueError, AttributeError):
            return False
    
    # ========================================================================
    # Token Generation
    # ========================================================================
    
    @staticmethod
    def generate_session_token() -> str:
        """Случайная строка для не-JWT токенов (сброс пароля, верификация почты)."""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def generate_reset_token() -> str:
        """Generate a password reset token."""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def generate_id() -> str:
        """Generate a unique ID."""
        return str(uuid.uuid4())
    
    # ========================================================================
    # User Operations
    # ========================================================================
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def create_user(self, email: str, password: str, name: Optional[str] = None) -> User:
        """Create a new user with credential account."""
        # Validate inputs
        if not email or not email.strip():
            raise BadRequestException("Email is required")
        if not password or len(password) < 6:
            raise BadRequestException("Password must be at least 6 characters")
        
        email = email.strip().lower()
        
        # Check if user exists
        existing_user = await self.get_user_by_email(email)
        if existing_user:
            raise UserAlreadyExistsException()
        
        user_id = self.generate_id()
        account_id = self.generate_id()
        
        try:
            # Create user
            user = User(
                id=user_id,
                email=email,
                name=(name or email.split("@")[0]).strip() if name else email.split("@")[0],
                emailVerified=False,
            )
            self.db.add(user)
            await self.db.flush()  # Force insert User first to satisfy FK
            
            # Create credential account
            account = Account(
                id=account_id,
                user_id=user_id,
                account_id=user_id,
                provider_id="credential",
                password=self.hash_password(password),
            )
            self.db.add(account)
            
            await self.db.commit()
            await self.db.refresh(user)
            
            return user
        except IntegrityError as e:
            # Ошибка целостности данных (например, нарушение уникального ограничения)
            await self.db.rollback()
            logger.warning(f"Integrity error in create_user: {str(e)}")
            # Проверяем, является ли это нарушением уникального ограничения
            if "unique" in str(e).lower() or "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                raise UserAlreadyExistsException()
            # Для других ошибок целостности пробрасываем дальше
            raise
        except SQLAlchemyError as e:
            # Другие ошибки базы данных - логируем и пробрасываем
            await self.db.rollback()
            logger.error(f"Database error in create_user: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            # Неожиданные ошибки - логируем и пробрасываем
            await self.db.rollback()
            logger.error(f"Unexpected error in create_user: {str(e)}", exc_info=True)
            raise
    
    # ========================================================================
    # Session Operations
    # ========================================================================
    
    async def create_session(
        self, 
        user_id: str, 
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Session:
        """Create a new session for user."""
        if not user_id:
            raise BadRequestException("User ID is required")
        
        session_id = self.generate_id()
        expires_at = datetime.now(timezone.utc) + timedelta(days=self.SESSION_LIFETIME_DAYS)
        if not settings.JWT_PRIVATE_KEY_PEM or not settings.JWT_PUBLIC_KEY_PEM:
            logger.error("JWT_PRIVATE_KEY_PEM / JWT_PUBLIC_KEY_PEM не заданы — RS256 сессии недоступны")
            raise JwtConfigurationException()
        token = encode_session_jwt(
            settings.JWT_PRIVATE_KEY_PEM,
            session_id=session_id,
            user_id=user_id,
            expires_at=expires_at,
            issuer=settings.JWT_ISSUER or None,
            audience=settings.JWT_AUDIENCE or None,
        )
        
        try:
            session = Session(
                id=session_id,
                user_id=user_id,
                token=token,
                expires_at=expires_at,
                ip_address=ip_address[:45] if ip_address else None,  # Limit IP length
                user_agent=user_agent,
            )
            self.db.add(session)
            await self.db.commit()
            await self.db.refresh(session)
            
            return session
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Database error in create_session: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Unexpected error in create_session: {str(e)}", exc_info=True)
            raise
    
    async def get_session_by_token(self, token: str) -> Optional[Session]:
        """Get session by token."""
        result = await self.db.execute(
            select(Session).where(Session.token == token)
        )
        return result.scalar_one_or_none()

    async def get_session_by_id(self, session_id: str) -> Optional[Session]:
        """Get session by primary key."""
        result = await self.db.execute(select(Session).where(Session.id == session_id))
        return result.scalar_one_or_none()
    
    async def validate_session(self, token: str) -> Tuple[User, Session]:
        """Validate session: JWT RS256 или устаревший opaque-токен в БД."""
        if looks_like_jwt(token):
            if not settings.JWT_PUBLIC_KEY_PEM:
                raise UnauthorizedException("Invalid session token")
            return await self._validate_session_rs256(token)
        return await self._validate_session_opaque(token)

    async def _validate_session_rs256(self, token: str) -> Tuple[User, Session]:
        now = datetime.now(timezone.utc)
        try:
            claims = decode_session_jwt(
                settings.JWT_PUBLIC_KEY_PEM,
                token,
                issuer=settings.JWT_ISSUER or None,
                audience=settings.JWT_AUDIENCE or None,
                leeway_seconds=settings.JWT_LEEWAY_SECONDS,
            )
        except pyjwt.PyJWTError as e:
            logger.debug("JWT decode failed: %s", e)
            raise UnauthorizedException() from e

        session_id = claims.get("sid")
        user_id = claims.get("sub")
        if not session_id or not user_id:
            raise UnauthorizedException()

        session = await self.get_session_by_id(session_id)
        if not session or session.user_id != user_id:
            raise UnauthorizedException()
        if not tokens_equal_constant_time(session.token, token):
            raise UnauthorizedException()

        if session.expires_at < now:
            await self.db.execute(delete(Session).where(Session.id == session.id))
            await self.db.commit()
            raise SessionExpiredException()

        user = await self.get_user_by_id(user_id)
        if not user:
            raise UnauthorizedException()
        return user, session

    async def _validate_session_opaque(self, token: str) -> Tuple[User, Session]:
        """Legacy: непрозрачный токен, поиск в БД."""
        now = datetime.now(timezone.utc)
        session = await self.get_session_by_token(token)

        if not session:
            raise UnauthorizedException()

        if session.expires_at < now:
            await self.db.execute(
                delete(Session).where(Session.id == session.id)
            )
            await self.db.commit()
            raise SessionExpiredException()

        user = await self.get_user_by_id(session.user_id)
        if not user:
            raise UnauthorizedException()

        return user, session
    
    async def delete_session(self, token: str) -> bool:
        """Delete session by token (полное совпадение строки в БД или JWT + сверка по sid)."""
        session = await self.get_session_by_token(token)
        if session:
            await self.db.execute(
                delete(Session).where(Session.id == session.id)
            )
            await self.db.commit()
            return True
        if looks_like_jwt(token) and settings.JWT_PUBLIC_KEY_PEM:
            try:
                claims = decode_session_jwt(
                    settings.JWT_PUBLIC_KEY_PEM,
                    token,
                    issuer=settings.JWT_ISSUER or None,
                    audience=settings.JWT_AUDIENCE or None,
                    leeway_seconds=settings.JWT_LEEWAY_SECONDS,
                )
            except pyjwt.PyJWTError:
                return False
            sid = claims.get("sid")
            if isinstance(sid, str) and sid.strip():
                row = await self.get_session_by_id(sid)
                if row and tokens_equal_constant_time(row.token, token):
                    await self.db.execute(delete(Session).where(Session.id == row.id))
                    await self.db.commit()
                    return True
        return False
    
    async def delete_all_user_sessions(self, user_id: str) -> None:
        """Delete all sessions for a user."""
        await self.db.execute(
            delete(Session).where(Session.user_id == user_id)
        )
        await self.db.commit()
    
    # ========================================================================
    # Authentication Operations
    # ========================================================================
    
    async def sign_up(
        self,
        email: str,
        password: str,
        name: Optional[str] = None,
    ) -> User:
        """Register a new user (no session until email verified)."""
        user = await self.create_user(email, password, name)
        
        # Send verification email
        try:
            # Get account to store verification token
            result = await self.db.execute(
                select(Account).where(
                    Account.user_id == user.id,
                    Account.provider_id == "credential"
                )
            )
            account = result.scalar_one_or_none()
            
            if account:
                # Generate verification token
                verification_token = self.generate_reset_token()
                account.access_token = verification_token
                account.access_token_expires_at = datetime.now(timezone.utc) + timedelta(
                    hours=24  # Verification tokens valid for 24 hours
                )
                await self.db.commit()
                
                # Send verification email
                from src.services.email_service import email_service
                user_name = user.name or email.split("@")[0]
                
                await email_service.send_verification_email(
                    to_email=email,
                    user_name=user_name,
                    verification_token=verification_token
                )
                logger.info(f"Verification email sent to {email}")
        except Exception as e:
            # Don't fail registration if email fails
            logger.error(f"Failed to send verification email to {email}: {str(e)}")
        
        return user
    
    async def sign_in(
        self, 
        email: str, 
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[User, Session]:
        """Authenticate user and create session."""
        # Validate inputs
        if not email or not email.strip():
            raise BadRequestException("Email is required")
        if not password:
            raise BadRequestException("Password is required")
        
        email = email.strip().lower()
        
        user = await self.get_user_by_email(email)
        if not user:
            raise InvalidCredentialsException()
        
        # Get credential account
        result = await self.db.execute(
            select(Account).where(
                Account.user_id == user.id,
                Account.provider_id == "credential"
            )
        )
        account = result.scalar_one_or_none()
        
        if not account or not account.password:
            raise InvalidCredentialsException()
        
        if not self.verify_password(password, account.password):
            raise InvalidCredentialsException()
        
        # Check if email is verified
        if not user.emailVerified:
            raise BadRequestException("Email не подтвержден. Проверьте почту для подтверждения аккаунта.")
        
        session = await self.create_session(user.id, ip_address, user_agent)
        return user, session
    
    async def sign_out(self, token: str) -> bool:
        """Sign out user by deleting session."""
        return await self.delete_session(token)
    
    async def get_current_session(self, token: str) -> Tuple[User, Session]:
        """Get current user and session from token."""
        return await self.validate_session(token)
    
    # ========================================================================
    # Password Reset Operations
    # ========================================================================
    
    async def initiate_password_reset(self, email: str, redirect_to: Optional[str] = None) -> Optional[str]:
        """
        Initiate password reset process.
        Sends password reset email to user.
        Returns reset token if user exists, None otherwise.
        """
        from src.services.email_service import email_service
        
        user = await self.get_user_by_email(email)
        if not user:
            # Don't reveal if user exists
            return None
        
        # Generate reset token
        reset_token = self.generate_reset_token()
        
        # Store reset token in account (using access_token field temporarily)
        result = await self.db.execute(
            select(Account).where(
                Account.user_id == user.id,
                Account.provider_id == "credential"
            )
        )
        account = result.scalar_one_or_none()
        
        if account:
            account.access_token = reset_token
            account.access_token_expires_at = datetime.now(timezone.utc) + timedelta(
                hours=self.RESET_TOKEN_LIFETIME_HOURS
            )
            await self.db.commit()
            
            # Send password reset email
            user_name = user.name or email.split("@")[0]
            reset_url_base = redirect_to or "https://delez.tech/reset-password"
            
            try:
                email_sent = await email_service.send_password_reset_email(
                    to_email=email,
                    user_name=user_name,
                    reset_token=reset_token,
                    reset_url_base=reset_url_base
                )
                if email_sent:
                    import logging
                    logging.info(f"Password reset email sent successfully to {email}")
                else:
                    import logging
                    logging.warning(f"Password reset email returned False for {email}")
            except Exception as e:
                import logging
                import traceback
                logging.error(f"Failed to send password reset email to {email}: {str(e)}")
                logging.error(f"Full traceback: {traceback.format_exc()}")
        
        return reset_token
    
    async def reset_password(self, token: str, new_password: str) -> bool:
        """Reset password using reset token."""
        # Validate inputs
        if not token or not token.strip():
            raise BadRequestException("Reset token is required")
        if not new_password or len(new_password) < 6:
            raise BadRequestException("Password must be at least 6 characters")
        
        token = token.strip()
        
        # Find account with this reset token
        result = await self.db.execute(
            select(Account).where(
                Account.access_token == token,
                Account.provider_id == "credential"
            )
        )
        account = result.scalar_one_or_none()
        
        if not account:
            raise InvalidTokenException()
        
        # Check if token is expired
        if account.access_token_expires_at and account.access_token_expires_at < datetime.now(timezone.utc):
            # Clear expired token
            try:
                account.access_token = None
                account.access_token_expires_at = None
                await self.db.commit()
            except Exception:
                await self.db.rollback()
            raise InvalidTokenException("Reset token has expired")
        
        try:
            # Update password
            account.password = self.hash_password(new_password)
            account.access_token = None
            account.access_token_expires_at = None
            await self.db.commit()
            
            # Delete all existing sessions for security
            await self.delete_all_user_sessions(account.user_id)
            
            return True
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Database error in reset_password: {str(e)}", exc_info=True)
            raise

    async def update_profile(
        self,
        user_id: str,
        *,
        name: Optional[str] = None,
        email: Optional[str] = None,
        bio: Optional[str] = None,
    ) -> User:
        """Update editable profile fields for current user."""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise UserNotFoundException()

        if name is not None:
            clean_name = name.strip()
            if not clean_name:
                raise BadRequestException("Name cannot be empty")
            user.name = clean_name

        if email is not None:
            clean_email = email.strip().lower()
            if not clean_email:
                raise BadRequestException("Email cannot be empty")
            if clean_email != user.email:
                existing_user = await self.get_user_by_email(clean_email)
                if existing_user and existing_user.id != user.id:
                    raise UserAlreadyExistsException("User with this email already exists")
                user.email = clean_email

        if bio is not None:
            user.bio = bio.strip() if bio else None

        try:
            await self.db.commit()
            await self.db.refresh(user)
            return user
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Database error in update_profile: {str(e)}", exc_info=True)
            raise

    async def change_password(self, user_id: str, current_password: str, new_password: str) -> None:
        """Change password for authenticated user with current password check."""
        if not current_password:
            raise BadRequestException("Current password is required")
        if not new_password or len(new_password) < 8:
            raise BadRequestException("New password must be at least 8 characters")

        result = await self.db.execute(
            select(Account).where(
                Account.user_id == user_id,
                Account.provider_id == "credential",
            )
        )
        account = result.scalar_one_or_none()
        if not account or not account.password:
            raise InvalidCredentialsException()

        if not self.verify_password(current_password, account.password):
            raise InvalidCredentialsException("Current password is incorrect")

        account.password = self.hash_password(new_password)

        try:
            await self.db.commit()
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Database error in change_password: {str(e)}", exc_info=True)
            raise
    
    # ========================================================================
    # Email Verification Operations
    # ========================================================================
    
    async def resend_verification_email(self, email: str) -> Optional[str]:
        """
        Resend email verification.
        Returns verification token if user exists, None otherwise.
        In production, this would send an email instead of returning the token.
        """
        try:
            user = await self.get_user_by_email(email)
            if not user:
                # Don't reveal if user exists
                return None
            
            # Check if user is already verified
            if user.emailVerified:
                # User already verified, but don't reveal this
                return None
            
            # Generate verification token
            verification_token = self.generate_reset_token()  # Reuse same token generation
            
            # Store verification token in account (using access_token field)
            result = await self.db.execute(
                select(Account).where(
                    Account.user_id == user.id,
                    Account.provider_id == "credential"
                )
            )
            account = result.scalar_one_or_none()
            
            if account:
                account.access_token = verification_token
                account.access_token_expires_at = datetime.now(timezone.utc) + timedelta(
                    hours=24  # Verification tokens valid for 24 hours
                )
                await self.db.commit()
                
                # Send verification email
                from src.services.email_service import email_service
                user_name = user.name or email.split("@")[0]
                
                try:
                    # In production, this would use a proper verification URL
                    await email_service.send_verification_email(
                        to_email=email,
                        user_name=user_name,
                        verification_token=verification_token
                    )
                except Exception as e:
                    logger.error(f"Failed to send verification email: {str(e)}")
            
            return verification_token
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Database error in resend_verification_email: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Unexpected error in resend_verification_email: {str(e)}", exc_info=True)
            raise

    async def verify_email(self, token: str) -> bool:
        """
        Verify user's email using verification token.
        Returns True if verification successful, False otherwise.
        """
        if not token or not token.strip():
            return False
        
        try:
            # Find account with this verification token
            result = await self.db.execute(
                select(Account).where(
                    Account.access_token == token,
                    Account.provider_id == "credential"
                )
            )
            account = result.scalar_one_or_none()
            
            if not account:
                logger.warning("Verification token not found")
                return False
            
            # Check if token is expired
            if account.access_token_expires_at:
                if account.access_token_expires_at < datetime.now(timezone.utc):
                    logger.warning(f"Verification token expired for user {account.user_id}")
                    return False
            
            # Get user and mark as verified
            user_result = await self.db.execute(
                select(User).where(User.id == account.user_id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                logger.warning(f"User not found for account {account.id}")
                return False
            
            # Mark user as verified
            user.emailVerified = True
            
            # Clear the verification token
            account.access_token = None
            account.access_token_expires_at = None
            
            await self.db.commit()
            logger.info(f"Email verified successfully for user {user.email}")
            
            return True
            
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Database error in verify_email: {str(e)}", exc_info=True)
            return False
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Unexpected error in verify_email: {str(e)}", exc_info=True)
            return False
