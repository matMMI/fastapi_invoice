"""Tests for client management API."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from models.user import User
from models.client import Client
from models.auth import Session as AuthSession
from datetime import datetime, timedelta, timezone


@pytest.fixture
def authenticated_client(client: TestClient, session: Session):
    """Create an authenticated test client."""
    # Create user
    user = User(
        id="test-user-id",
        email="test@example.com",
        name="Test User",
        email_verified=False
    )
    session.add(user)
    
    # Create session
    auth_session = AuthSession(
        id="test-session-id",
        user_id=user.id,
        token="test-token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        ip_address="127.0.0.1",
        user_agent="test"
    )
    session.add(auth_session)
    session.commit()
    
    # Add auth header to client
    client.headers = {"Authorization": "Bearer test-token"}
    return client, user


def test_create_client(authenticated_client, session: Session):
    """Test creating a new client."""
    client, user = authenticated_client
    
    response = client.post("/api/clients", json={
        "name": "John Doe",
        "email": "john@example.com",
        "company": "Acme Corp"
    })
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "John Doe"
    assert data["email"] == "john@example.com"
    assert data["user_id"] == user.id


def test_list_clients(authenticated_client, session: Session):
    """Test listing clients."""
    client, user = authenticated_client
    
    # Create test clients
    test_client = Client(
        user_id=user.id,
        name="Test Client",
        email="test@client.com"
    )
    session.add(test_client)
    session.commit()
    
    response = client.get("/api/clients")
    assert response.status_code == 200
    data = response.json()
    assert len(data["clients"]) == 1
    assert data["clients"][0]["name"] == "Test Client"


def test_cannot_access_other_users_clients(authenticated_client, session: Session):
    """Test that users can only see their own clients."""
    client, user = authenticated_client
    
    # Create another user's client
    other_user = User(
        id="other-user-id",
        email="other@example.com",
        name="Other User",
        email_verified=False
    )
    session.add(other_user)
    
    other_client = Client(
        user_id=other_user.id,
        name="Other Client",
        email="other@client.com"
    )
    session.add(other_client)
    session.commit()
    
    # Try to list clients
    response = client.get("/api/clients")
    assert response.status_code == 200
    data = response.json()
    assert len(data["clients"]) == 0  # Should not see other user's clients
