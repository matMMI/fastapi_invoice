"""Security utilities for authentication and authorization."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session, select
from db.session import get_session
from models.user import User
from models.auth import Session as AuthSession
from datetime import datetime, timezone

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_session)
) -> User:
    """
    Verify session token and return the current user.
    Raises 401 if token is invalid or expired.
    """
    token = credentials.credentials
    
    # Query session by token
    statement = select(AuthSession).where(AuthSession.token == token)
    session = db.exec(statement).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    
    # Check if session is expired
    expires_at = session.expires_at
    # Ensure expires_at is timezone aware (as UTC) if it comes as naive from DB
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
        
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired"
        )
    
    # Get user
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return user
