"""Authentication system for Anvil API."""

from __future__ import annotations

import hashlib
import hmac
import jwt
import secrets
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field


# ============================================================================
# Configuration
# ============================================================================

SECRET_KEY = "your-secret-key-change-in-production"  # TODO: Use environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 30


# ============================================================================
# Models
# ============================================================================

class User(BaseModel):
    """User model."""
    id: str
    email: EmailStr
    username: str
    hashed_password: str
    is_active: bool = True
    is_admin: bool = False
    created_at: datetime = Field(default_factory=datetime.now)
    last_login: Optional[datetime] = None


class UserCreate(BaseModel):
    """User creation request."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    """User login request."""
    email: EmailStr
    password: str


class Token(BaseModel):
    """JWT token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """JWT token data."""
    user_id: str
    email: str
    exp: datetime


class APIKey(BaseModel):
    """API key model."""
    id: str
    user_id: str
    key: str
    name: str
    created_at: datetime = Field(default_factory=datetime.now)
    last_used: Optional[datetime] = None
    is_active: bool = True


# ============================================================================
# Password Hashing
# ============================================================================

def hash_password(password: str) -> str:
    """Hash a password using PBKDF2."""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return f"{salt}:{pwd_hash.hex()}"


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    try:
        salt, hash_hex = hashed_password.split(':')
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        return hmac.compare_digest(pwd_hash.hex(), hash_hex)
    except Exception:
        return False


# ============================================================================
# JWT Token Management
# ============================================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> TokenData:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("user_id")
        email: str = payload.get("email")
        exp: datetime = payload.get("exp")
        
        if user_id is None or email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
        
        return TokenData(user_id=user_id, email=email, exp=exp)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


# ============================================================================
# API Key Management
# ============================================================================

def generate_api_key() -> str:
    """Generate a secure API key."""
    return f"anvil_{secrets.token_urlsafe(32)}"


def validate_api_key(api_key: str) -> bool:
    """Validate an API key format."""
    return api_key.startswith("anvil_") and len(api_key) > 40


# ============================================================================
# Authentication Dependencies
# ============================================================================

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenData:
    """Get current user from JWT token."""
    token = credentials.credentials
    return verify_token(token)


async def get_current_active_user(
    current_user: TokenData = Depends(get_current_user),
) -> TokenData:
    """Get current active user."""
    # TODO: Check if user is active in database
    return current_user


async def get_current_admin_user(
    current_user: TokenData = Depends(get_current_active_user),
) -> TokenData:
    """Get current admin user."""
    # TODO: Check if user is admin in database
    # For now, just return the user
    return current_user


# ============================================================================
# OAuth2 Integration (Placeholder)
# ============================================================================

class OAuth2Provider:
    """OAuth2 provider configuration."""
    
    def __init__(self, name: str, client_id: str, client_secret: str, auth_url: str, token_url: str):
        self.name = name
        self.client_id = client_id
        self.client_secret = client_secret
        self.auth_url = auth_url
        self.token_url = token_url


# GitHub OAuth2
github_oauth = OAuth2Provider(
    name="github",
    client_id="your-github-client-id",  # TODO: Use environment variable
    client_secret="your-github-client-secret",  # TODO: Use environment variable
    auth_url="https://github.com/login/oauth/authorize",
    token_url="https://github.com/login/oauth/access_token",
)

# Google OAuth2
google_oauth = OAuth2Provider(
    name="google",
    client_id="your-google-client-id",  # TODO: Use environment variable
    client_secret="your-google-client-secret",  # TODO: Use environment variable
    auth_url="https://accounts.google.com/o/oauth2/v2/auth",
    token_url="https://oauth2.googleapis.com/token",
)


# ============================================================================
# Rate Limiting
# ============================================================================

class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict[str, list[datetime]] = {}
    
    def is_allowed(self, user_id: str) -> bool:
        """Check if a request is allowed."""
        now = datetime.now()
        
        # Clean old requests
        if user_id in self.requests:
            self.requests[user_id] = [
                req for req in self.requests[user_id]
                if (now - req).total_seconds() < self.window_seconds
            ]
        else:
            self.requests[user_id] = []
        
        # Check if limit exceeded
        if len(self.requests[user_id]) >= self.max_requests:
            return False
        
        # Add request
        self.requests[user_id].append(now)
        return True


# Global rate limiter
rate_limiter = RateLimiter(max_requests=100, window_seconds=60)


async def check_rate_limit(current_user: TokenData = Depends(get_current_user)):
    """Check rate limit for current user."""
    if not rate_limiter.is_allowed(current_user.user_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )
    return current_user
