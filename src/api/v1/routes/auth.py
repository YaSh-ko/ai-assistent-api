"""
Authentication endpoints.
"""
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from typing import Annotated, Optional
from datetime import datetime
import logging

from src.core.database import get_db
from src.core.config import settings
from src.core.exceptions import (
    InvalidCredentialsException,
    UserAlreadyExistsException,
    InvalidTokenException,
    UnauthorizedException,
    BadRequestException,
    TooManyRequestsException,
)
from src.core.rate_limit import signup_ip_limiter

logger = logging.getLogger(__name__)
from src.services.auth_service import AuthService
from src.api.v1.schemas.auth import (
    SignUpRequest,
    SignInRequest,
    ForgetPasswordRequest,
    ResetPasswordRequest,
    ResendVerificationRequest,
    VerifyEmailRequest,
    UpdateProfileRequest,
    ChangePasswordRequest,
    AuthResponse,
    UserResponse,
    SessionResponse,
    SignOutResponse,
    SuccessResponse,
    ErrorResponse,
)

router = APIRouter()


def get_token_from_request(request: Request) -> Optional[str]:
    """Extract token from Authorization header or cookie."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]
    return request.cookies.get("session_token")


def get_client_info(request: Request) -> tuple[Optional[str], Optional[str]]:
    """Get client IP and User-Agent from request."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    return ip_address, user_agent


def set_session_cookie(response: JSONResponse, token: str, expires_at: datetime) -> None:
    """Set session cookie with appropriate security settings for cross-site auth."""
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        expires=expires_at,
    )


# ============================================================================
# Sign Up
# ============================================================================

@router.post(
    "/sign-up/email",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
        409: {"model": ErrorResponse, "description": "User already exists"},
    },
    summary="Register new user",
    description="Register a new user with email and password",
)
async def sign_up(
    request: Request,
    body: SignUpRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Register a new user with email and password.
    
    - **email**: Valid email address
    - **password**: Password (min 6 characters)
    - **name**: Optional display name
    """
    try:
        ip_address, _ = get_client_info(request)
        if settings.SIGNUP_IP_LIMIT_ENABLED:
            ip_key = ip_address or "unknown"
            allowed = signup_ip_limiter().allow(
                f"signup:{ip_key}",
                limit=settings.SIGNUP_IP_MAX_REGISTRATIONS,
                window_seconds=settings.SIGNUP_IP_WINDOW_SECONDS,
            )
            if not allowed:
                raise TooManyRequestsException(
                    "Registration limit exceeded for this IP. Please try later.",
                )
        auth_service = AuthService(db)
        await auth_service.sign_up(
            email=body.email,
            password=body.password,
            name=body.name,
        )
    except (UserAlreadyExistsException, BadRequestException, TooManyRequestsException):
        # Re-raise known exceptions - они будут обработаны глобальным обработчиком
        raise
    except SQLAlchemyError as e:
        # Ошибки базы данных должны пройти к глобальному обработчику SQLAlchemyError
        # который вернет правильный 500 статус
        logger.error(f"Database error in sign_up: {str(e)}", exc_info=True)
        raise
    except Exception as e:
        # Для других неожиданных ошибок логируем и пробрасываем дальше
        # чтобы глобальный обработчик Exception вернул 500
        logger.error(f"Unexpected error in sign_up: {str(e)}", exc_info=True)
        # В режиме DEBUG возвращаем более детальное сообщение
        if settings.DEBUG:
            raise BadRequestException(f"Failed to create user account: {str(e)}")
        raise
    
    return {
        "success": True,
        "message": "Регистрация успешна! Проверьте почту для подтверждения аккаунта.",
    }


# ============================================================================
# Sign In
# ============================================================================

@router.post(
    "/sign-in/email",
    response_model=AuthResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
    },
    summary="Sign in with email",
    description="Authenticate user with email and password",
)
async def sign_in(
    request: Request,
    body: SignInRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Sign in with email and password.
    
    - **email**: User's email address
    - **password**: User's password
    """
    try:
        ip_address, user_agent = get_client_info(request)
        
        auth_service = AuthService(db)
        user, session = await auth_service.sign_in(
            email=body.email,
            password=body.password,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except (InvalidCredentialsException, BadRequestException):
        # Re-raise known exceptions - они будут обработаны глобальным обработчиком
        raise
    except SQLAlchemyError as e:
        # Ошибки базы данных должны пройти к глобальному обработчику SQLAlchemyError
        logger.error(f"Database error in sign_in: {str(e)}", exc_info=True)
        raise
    except Exception as e:
        # Для других неожиданных ошибок логируем и пробрасываем дальше
        logger.error(f"Unexpected error in sign_in: {str(e)}", exc_info=True)
        raise
    
    response = JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
            },
            "session": {
                "token": session.token,
                "expiresAt": session.expires_at.isoformat(),
            },
        },
    )
    
    # Set cookie
    set_session_cookie(response, session.token, session.expires_at)
    
    return response


# ============================================================================
# Sign Out
# ============================================================================

@router.post(
    "/sign-out",
    response_model=SignOutResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
    },
    summary="Sign out",
    description="Sign out current user and invalidate session",
)
async def sign_out(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Sign out current user.
    
    Requires Authorization header with Bearer token or session cookie.
    """
    token = get_token_from_request(request)
    
    if not token:
        raise UnauthorizedException()
    
    auth_service = AuthService(db)
    await auth_service.sign_out(token)
    
    response = JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "success": True,
            "message": "Logged out successfully",
        },
    )
    
    # Clear cookie
    response.delete_cookie(key="session_token")
    
    return response


# ============================================================================
# Get Session (Current User)
# ============================================================================

@router.get(
    "/get-session",
    response_model=AuthResponse,
    responses={
        401: {"model": ErrorResponse, "description": "No active session"},
    },
    summary="Get current session",
    description="Get current user and session information",
)
async def get_session(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Get current user and session information.
    
    Requires Authorization header with Bearer token or session cookie.
    """
    token = get_token_from_request(request)
    
    if not token:
        raise UnauthorizedException()
    
    auth_service = AuthService(db)
    user, session = await auth_service.get_current_session(token)
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "createdAt": user.createdAt.isoformat() if user.createdAt else None,
            },
            "session": {
                "expiresAt": session.expires_at.isoformat(),
            },
        },
    )


@router.get(
    "/profile",
    response_model=UserResponse,
    responses={
        401: {"model": ErrorResponse, "description": "No active session"},
    },
    summary="Get current user profile",
    description="Get current authenticated user profile fields",
)
async def get_profile(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    token = get_token_from_request(request)
    if not token:
        raise UnauthorizedException()

    auth_service = AuthService(db)
    user, _ = await auth_service.get_current_session(token)
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        bio=user.bio,
        createdAt=user.createdAt,
    )


@router.patch(
    "/profile",
    response_model=UserResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
        401: {"model": ErrorResponse, "description": "No active session"},
    },
    summary="Update current user profile",
    description="Update editable profile fields for authenticated user",
)
async def update_profile(
    request: Request,
    body: UpdateProfileRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    token = get_token_from_request(request)
    if not token:
        raise UnauthorizedException()

    auth_service = AuthService(db)
    user, _ = await auth_service.get_current_session(token)
    updated = await auth_service.update_profile(
        user.id,
        name=body.name,
        email=body.email,
        bio=body.bio,
    )
    return UserResponse(
        id=updated.id,
        email=updated.email,
        name=updated.name,
        bio=updated.bio,
        createdAt=updated.createdAt,
    )


@router.post(
    "/change-password",
    response_model=SuccessResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
        401: {"model": ErrorResponse, "description": "Unauthorized or invalid current password"},
    },
    summary="Change password for current user",
    description="Change password for authenticated user with current password verification",
)
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    token = get_token_from_request(request)
    if not token:
        raise UnauthorizedException()

    auth_service = AuthService(db)
    user, _ = await auth_service.get_current_session(token)
    await auth_service.change_password(
        user.id,
        current_password=body.currentPassword,
        new_password=body.newPassword,
    )
    return SuccessResponse(success=True, message="Password changed successfully")


# ============================================================================
# Forget Password
# ============================================================================

@router.post(
    "/forget-password",
    response_model=SuccessResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
    summary="Request password reset",
    description="Send password reset email to user",
)
async def forget_password(
    body: ForgetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Request password reset.
    
    - **email**: User's email address
    - **redirectTo**: Optional URL to redirect after reset
    
    Note: In production, this would send an email. For development,
    the reset token is returned in the response (not secure for production).
    """
    auth_service = AuthService(db)
    
    # Always return success to prevent email enumeration
    await auth_service.initiate_password_reset(body.email, redirect_to=body.redirectTo)
    
    return {
        "success": True,
        "message": "Password reset email sent",
    }


# ============================================================================
# Reset Password
# ============================================================================

@router.post(
    "/reset-password",
    response_model=SuccessResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
    },
    summary="Reset password",
    description="Reset password using reset token",
)
async def reset_password(
    body: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Reset password using reset token.
    
    - **token**: Reset token from email
    - **password**: New password (min 6 characters)
    """
    try:
        auth_service = AuthService(db)
        await auth_service.reset_password(body.token, body.password)
        
        return {
            "success": True,
            "message": "Password reset successfully",
        }
    except (InvalidTokenException, BadRequestException):
        # Re-raise known exceptions - они будут обработаны глобальным обработчиком
        raise
    except SQLAlchemyError as e:
        # Ошибки базы данных должны пройти к глобальному обработчику SQLAlchemyError
        logger.error(f"Database error in reset_password: {str(e)}", exc_info=True)
        raise
    except Exception as e:
        # Для других неожиданных ошибок логируем и пробрасываем дальше
        logger.error(f"Unexpected error in reset_password: {str(e)}", exc_info=True)
        raise


# ============================================================================
# Resend Verification
# ============================================================================

@router.post(
    "/resend-verification",
    response_model=SuccessResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
    },
    summary="Resend email verification",
    description="Resend verification email to user",
)
async def resend_verification(
    body: ResendVerificationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Resend email verification.
    
    - **email**: User's email address
    
    Note: In production, this would send an email. For development,
    the verification token is returned in the response (not secure for production).
    Always returns success to prevent email enumeration attacks.
    """
    try:
        auth_service = AuthService(db)
        
        # Always return success to prevent email enumeration
        await auth_service.resend_verification_email(body.email)
        
        return {
            "success": True,
            "message": "Verification email sent",
        }
    except SQLAlchemyError as e:
        # Ошибки базы данных должны пройти к глобальному обработчику SQLAlchemyError
        logger.error(f"Database error in resend_verification: {str(e)}", exc_info=True)
        raise
    except Exception as e:
        # Для других неожиданных ошибок логируем и пробрасываем дальше
        logger.error(f"Unexpected error in resend_verification: {str(e)}", exc_info=True)
        raise


# ============================================================================
# Verify Email
# ============================================================================

@router.post(
    "/verify-email",
    response_model=SuccessResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
    },
    summary="Verify email address",
    description="Verify user's email address using token from email",
)
async def verify_email(
    body: VerifyEmailRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Verify user's email address.
    
    - **token**: Verification token from email
    """
    try:
        auth_service = AuthService(db)
        
        verified = await auth_service.verify_email(body.token)
        
        if verified:
            return {
                "success": True,
                "message": "Email успешно подтвержден",
            }
        else:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "invalid_token",
                    "message": "Недействительная или истекшая ссылка для подтверждения",
                },
            )
    except SQLAlchemyError as e:
        logger.error(f"Database error in verify_email: {str(e)}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error in verify_email: {str(e)}", exc_info=True)
        raise
