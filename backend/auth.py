"""
Authentication Service - JWT Token Management and Password Hashing
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from .database import UserManager
from .security import get_jwt_secret

logger = logging.getLogger("nepse-alpha")

# Configuration — signing key resolved via security.get_jwt_secret(), which fails
# closed in production (no committed fallback secret an attacker could forge with).
SECRET_KEY = get_jwt_secret()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))  # default 12h

# Bcrypt configuration
BCRYPT_ROUNDS = 12

# Security
security = HTTPBearer()


class AuthService:
    """
    Authentication service for token and password management
    """
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash password using bcrypt (max 72 bytes)
        
        Args:
            password: Plain text password
        
        Returns:
            Hashed password string
        """
        # Truncate to 72 bytes (bcrypt limit)
        truncated_password = password[:72].encode()
        hashed = bcrypt.hashpw(truncated_password, bcrypt.gensalt(rounds=BCRYPT_ROUNDS))
        return hashed.decode()
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify password using bcrypt (max 72 bytes)
        
        Args:
            plain_password: Plain text password
            hashed_password: Hashed password string
        
        Returns:
            True if password matches, False otherwise
        """
        # Truncate to 72 bytes (bcrypt limit)
        truncated_password = plain_password[:72].encode()
        hashed_bytes = hashed_password.encode()
        return bcrypt.checkpw(truncated_password, hashed_bytes)
    
    @staticmethod
    def create_access_token(email: str, expires_delta: Optional[timedelta] = None) -> str:
        """
        Create JWT access token
        
        Args:
            email: User email
            expires_delta: Token expiration time
        
        Returns:
            JWT token
        """
        if expires_delta is None:
            expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        expire = datetime.now(timezone.utc).replace(tzinfo=None) + expires_delta
        to_encode = {"sub": email, "exp": expire}
        
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str) -> Optional[str]:
        """
        Verify JWT token
        
        Args:
            token: JWT token
        
        Returns:
            Email from token if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email: str = payload.get("sub")
            if email is None:
                return None
            return email
        except JWTError:
            return None
    
    @staticmethod
    def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate user with email and password
        
        Args:
            email: User email
            password: Plain text password
        
        Returns:
            User document if authentication successful, None otherwise
        """
        user = UserManager.get_user_by_email(email)
        if not user:
            logger.warning(f"Login attempt with non-existent email: {email}")
            return None
        
        if not AuthService.verify_password(password, user.get("password", "")):
            logger.warning(f"Login attempt with wrong password: {email}")
            return None
        
        if not user.get("is_active", True):
            logger.warning(f"Login attempt with inactive user: {email}")
            return None
        
        logger.info(f"✓ User authenticated: {email}")
        return user


async def get_current_user(credentials = Depends(security)) -> Dict[str, Any]:
    """
    Dependency to get current authenticated user
    
    Args:
        credentials: HTTP Bearer credentials from security scheme
    
    Returns:
        User document
    
    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    email = AuthService.verify_token(token)
    
    if email is None:
        logger.warning(f"Invalid token attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = UserManager.get_user_by_email(email)
    if user is None:
        logger.warning(f"User not found for token: {email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.get("is_active", True):
        logger.warning(f"Inactive user token: {email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user
