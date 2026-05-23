"""
Pydantic schemas for authentication endpoints.
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


# ============================================================================
# Request Schemas
# ============================================================================

class SignUpRequest(BaseModel):
    """Request body for sign up endpoint."""
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters")
    name: Optional[str] = Field(None, description="User's display name")


class SignInRequest(BaseModel):
    """Request body for sign in endpoint."""
    email: EmailStr
    password: str


class ForgetPasswordRequest(BaseModel):
    """Request body for forget password endpoint."""
    email: EmailStr
    redirectTo: Optional[str] = Field(None, description="URL to redirect after password reset")


class ResetPasswordRequest(BaseModel):
    """Request body for reset password endpoint."""
    token: str
    password: str = Field(..., min_length=6, description="New password must be at least 6 characters")


class ResendVerificationRequest(BaseModel):
    """Request body for resend verification endpoint."""
    email: EmailStr


class VerifyEmailRequest(BaseModel):
    """Request body for verify email endpoint."""
    token: str = Field(..., description="Verification token from email")

class UpdateProfileRequest(BaseModel):
    """Request body for profile update endpoint."""
    name: Optional[str] = Field(None, min_length=1, max_length=120, description="User display name")
    email: Optional[EmailStr] = Field(None, description="User email")
    bio: Optional[str] = Field(None, max_length=2000, description="User bio/about text")


class ChangePasswordRequest(BaseModel):
    """Request body for authenticated password change."""
    currentPassword: str = Field(..., min_length=1, description="Current password")
    newPassword: str = Field(..., min_length=8, description="New password (minimum 8 characters)")


# ============================================================================
# Response Schemas
# ============================================================================

class UserResponse(BaseModel):
    """User data in response."""
    id: str
    email: str
    name: Optional[str] = None
    bio: Optional[str] = None
    createdAt: Optional[datetime] = None

    class Config:
        from_attributes = True


class SessionResponse(BaseModel):
    """Session data in response."""
    token: str
    expiresAt: datetime

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    """Response for sign up and sign in endpoints."""
    user: UserResponse
    session: SessionResponse


class SignOutResponse(BaseModel):
    """Response for sign out endpoint."""
    success: bool = True
    message: str = "Logged out successfully"


class SuccessResponse(BaseModel):
    """Generic success response."""
    success: bool = True
    message: str


class ErrorResponse(BaseModel):
    """Error response schema."""
    error: str
    message: str
