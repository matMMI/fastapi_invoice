"""Tests for authentication and session management."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from models.user import User
from models.auth import Session as AuthSession
from datetime import datetime, timedelta, timezone


def test_health_endpoint(client: TestClient):
    """Test that health endpoint returns 200."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_protected_route_without_auth(client: TestClient):
    """Test that protected routes return 401 without authentication."""
    response = client.get("/api/clients")
    assert response.status_code == 401


def test_protected_route_with_invalid_token(client: TestClient):
    """Test that protected routes return 401 with invalid token."""
    response = client.get(
        "/api/clients",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401


def test_protected_route_with_expired_session(client: TestClient, session: Session):
    """Test that expired sessions are rejected."""
    # Create a user
    user = User(
        id="test-user-id",
        email="test@example.com",
        name="Test User",
        email_verified=False
    )
    session.add(user)
    
    # Create an expired session
    expired_session = AuthSession(
        id="test-session-id",
        user_id=user.id,
        token="expired-token",
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        ip_address="127.0.0.1",
        user_agent="test"
    )
    session.add(expired_session)
    session.commit()
    
    # Try to access protected route
    response = client.get(
        "/api/clients",
        headers={"Authorization": "Bearer expired-token"}
    )
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


def test_protected_route_with_valid_session(client: TestClient, session: Session):
    """Test that valid sessions allow access to protected routes."""
    # Create a user
    user = User(
        id="test-user-id",
        email="test@example.com",
        name="Test User",
        email_verified=False
    )
    session.add(user)
    
    # Create a valid session
    valid_session = AuthSession(
        id="test-session-id",
        user_id=user.id,
        token="valid-token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        ip_address="127.0.0.1",
        user_agent="test"
    )
    session.add(valid_session)
    session.commit()
    
    # Access protected route
    response = client.get(
        "/api/clients",
        headers={"Authorization": "Bearer valid-token"}
    )
    assert response.status_code == 200
