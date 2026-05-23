"""
Custom exceptions for the API service.
"""
from fastapi import HTTPException, status


class AuthException(HTTPException):
    """Base authentication exception."""
    def __init__(self, detail: str, status_code: int = status.HTTP_401_UNAUTHORIZED):
        super().__init__(status_code=status_code, detail=detail)


class InvalidCredentialsException(AuthException):
    """Raised when credentials are invalid."""
    def __init__(self, detail: str = "Invalid email or password"):
        super().__init__(detail=detail, status_code=status.HTTP_401_UNAUTHORIZED)


class UserAlreadyExistsException(AuthException):
    """Raised when user already exists."""
    def __init__(self, detail: str = "User with this email already exists"):
        super().__init__(detail=detail, status_code=status.HTTP_409_CONFLICT)


class UserNotFoundException(AuthException):
    """Raised when user is not found."""
    def __init__(self, detail: str = "User not found"):
        super().__init__(detail=detail, status_code=status.HTTP_404_NOT_FOUND)


class InvalidTokenException(AuthException):
    """Raised when token is invalid or expired."""
    def __init__(self, detail: str = "Invalid or expired token"):
        super().__init__(detail=detail, status_code=status.HTTP_401_UNAUTHORIZED)


class SessionExpiredException(AuthException):
    """Raised when session is expired."""
    def __init__(self, detail: str = "Session expired"):
        super().__init__(detail=detail, status_code=status.HTTP_401_UNAUTHORIZED)


class UnauthorizedException(AuthException):
    """Raised when user is not authorized."""
    def __init__(self, detail: str = "No active session"):
        super().__init__(detail=detail, status_code=status.HTTP_401_UNAUTHORIZED)


class BadRequestException(HTTPException):
    """Raised for bad requests."""
    def __init__(self, detail: str = "Bad request"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class JwtConfigurationException(HTTPException):
    """Сервис не может создавать сессии: не заданы ключи RS256 или некорректная конфигурация JWT."""
    def __init__(
        self,
        detail: str = "Authentication service is not fully configured (JWT RS256 keys missing)",
    ):
        super().__init__(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)


class TooManyRequestsException(HTTPException):
    """Raised when request rate exceeds configured limit."""

    def __init__(self, detail: str = "Too many requests. Please try again later."):
        super().__init__(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)
