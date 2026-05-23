# Resend Verification Endpoint

## Overview
Added the missing `/auth/resend-verification` endpoint to fix the 405 Method Not Allowed error from the frontend.

## Changes Made

### 1. Schema Addition (`src/api/v1/schemas/auth.py`)
- Added `ResendVerificationRequest` schema with email field

### 2. Service Method (`src/services/auth_service.py`)
- Added `resend_verification_email(email: str)` method
- Generates verification token (24-hour expiry)
- Stores token in Account model using access_token field
- Returns None for non-existent users (prevents email enumeration)
- Returns None for already verified users
- Includes proper error handling with database rollback

### 3. Route Endpoint (`src/api/v1/routes/auth.py`)
- Added POST `/auth/resend-verification` endpoint
- Uses `ResendVerificationRequest` schema for validation
- Returns `SuccessResponse` with success message
- Always returns success to prevent email enumeration attacks
- Includes proper error handling for database and unexpected errors

## API Usage

### Request
```http
POST /auth/resend-verification
Content-Type: application/json

{
  "email": "user@example.com"
}
```

### Response
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "success": true,
  "message": "Verification email sent"
}
```

## Security Features
- Always returns success response to prevent email enumeration
- Verification tokens expire after 24 hours
- Proper error handling with database rollback
- No sensitive information leaked in responses

## Notes
- In production, this would send an actual email instead of just storing the token
- Uses the same token storage mechanism as password reset (access_token field)
- Follows the same patterns as other auth endpoints for consistency