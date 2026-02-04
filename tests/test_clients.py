"""Tests for client management API."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from models.auth import Session as AuthSession
from models.client import Client
from models.user import User


@pytest.fixture
def authenticated_client(client: TestClient, session: Session):
    """Create an authenticated test client."""
    # Create user
    user = User(id="test-user-id", email="test@example.com", name="Test User", email_verified=False)
    session.add(user)

    # Create session
    auth_session = AuthSession(
        id="test-session-id",
        user_id=user.id,
        token="test-token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        ip_address="127.0.0.1",
        user_agent="test",
    )
    session.add(auth_session)
    session.commit()

    # Add auth header to client
    client.headers = {"Authorization": "Bearer test-token"}
    return client, user


def test_create_client(authenticated_client, session: Session):
    """Test creating a new client."""
    client, user = authenticated_client

    response = client.post(
        "/api/clients",
        json={"name": "John Doe", "email": "john@example.com", "company": "Acme Corp"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "John Doe"
    assert data["email"] == "john@example.com"
    assert data["user_id"] == user.id


def test_list_clients(authenticated_client, session: Session):
    """Test listing clients."""
    client, user = authenticated_client

    # Create test clients
    test_client = Client(user_id=user.id, name="Test Client", email="test@client.com")
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
        id="other-user-id", email="other@example.com", name="Other User", email_verified=False
    )
    session.add(other_user)

    other_client = Client(user_id=other_user.id, name="Other Client", email="other@client.com")
    session.add(other_client)
    session.commit()

    # Try to list clients
    response = client.get("/api/clients")
    assert response.status_code == 200
    data = response.json()
    assert len(data["clients"]) == 0  # Should not see other user's clients


def test_search_clients(authenticated_client, session: Session):
    """Test searching clients by name or email."""
    client, user = authenticated_client

    # Create clients
    # 1. Matches "Alpha" in name
    c1 = Client(user_id=user.id, name="Alpha Industries", email="info@alpha.com")
    session.add(c1)

    # 2. Matches "Alpha" in email
    c2 = Client(user_id=user.id, name="Beta Corp", email="contact@alpha-beta.com")
    session.add(c2)

    # 3. No match
    c3 = Client(user_id=user.id, name="Gamma Inc", email="gamma@test.com")
    session.add(c3)
    session.commit()

    # Search by "Alpha" (matches name of c1 and email of c2)
    res = client.get("/api/clients?search=Alpha")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert len(data["clients"]) == 2

    names = {c["name"] for c in data["clients"]}
    assert "Alpha Industries" in names
    assert "Beta Corp" in names

    # Search by "Gamma" (matches c3 only)
    res = client.get("/api/clients?search=Gamma")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["clients"][0]["name"] == "Gamma Inc"

    # Search with no results
    res = client.get("/api/clients?search=Omega")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert len(data["clients"]) == 0


# ────────────────────────────────────────────────
# GET /api/clients/{client_id}
# ────────────────────────────────────────────────


def test_get_client_by_id(authenticated_client, session: Session):
    """Test retrieving a single client by ID."""
    client, user = authenticated_client

    db_client = Client(
        id="client-get-id", user_id=user.id, name="Get Me", email="get@test.com", company="GetCo"
    )
    session.add(db_client)
    session.commit()

    response = client.get("/api/clients/client-get-id")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "client-get-id"
    assert data["name"] == "Get Me"
    assert data["email"] == "get@test.com"


def test_get_client_not_found(authenticated_client):
    """Test 404 for non-existent client."""
    client, user = authenticated_client
    response = client.get("/api/clients/nonexistent-id")
    assert response.status_code == 404


def test_get_client_other_user(authenticated_client, session: Session):
    """Test that accessing another user's client returns 404 (IDOR prevention)."""
    client, user = authenticated_client

    other_user = User(
        id="other-user-get", email="other-get@test.com", name="Other", email_verified=False
    )
    session.add(other_user)
    other_client = Client(
        id="other-client-id", user_id=other_user.id, name="Secret", email="secret@test.com"
    )
    session.add(other_client)
    session.commit()

    response = client.get("/api/clients/other-client-id")
    assert response.status_code == 404


# ────────────────────────────────────────────────
# PUT /api/clients/{client_id}
# ────────────────────────────────────────────────


def test_update_client(authenticated_client, session: Session):
    """Test updating a client's fields."""
    client, user = authenticated_client

    db_client = Client(
        id="client-update-id", user_id=user.id, name="Old Name", email="old@test.com"
    )
    session.add(db_client)
    session.commit()

    response = client.put(
        "/api/clients/client-update-id",
        json={
            "name": "New Name",
            "email": "new@test.com",
            "company": "New Corp",
            "phone": "+33612345678",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["email"] == "new@test.com"


def test_update_client_partial(authenticated_client, session: Session):
    """Test partial update (only name, email untouched)."""
    client, user = authenticated_client

    db_client = Client(
        id="client-partial-id", user_id=user.id, name="Original", email="original@test.com"
    )
    session.add(db_client)
    session.commit()

    response = client.put("/api/clients/client-partial-id", json={"name": "Updated"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated"
    assert data["email"] == "original@test.com"  # Unchanged


def test_update_client_not_found(authenticated_client):
    """Test 404 when updating non-existent client."""
    client, user = authenticated_client
    response = client.put("/api/clients/nonexistent-id", json={"name": "X"})
    assert response.status_code == 404


def test_update_client_other_user(authenticated_client, session: Session):
    """Test that updating another user's client returns 404."""
    client, user = authenticated_client

    other_user = User(
        id="other-user-upd", email="other-upd@test.com", name="Other", email_verified=False
    )
    session.add(other_user)
    other_client = Client(
        id="other-client-upd", user_id=other_user.id, name="Secret", email="secret@test.com"
    )
    session.add(other_client)
    session.commit()

    response = client.put("/api/clients/other-client-upd", json={"name": "Hacked"})
    assert response.status_code == 404


def test_update_client_mass_assignment_blocked(authenticated_client, session: Session):
    """Test that fields outside ALLOWED_UPDATE_FIELDS are rejected by extra='forbid'."""
    client, user = authenticated_client

    db_client = Client(id="client-mass-id", user_id=user.id, name="Safe", email="safe@test.com")
    session.add(db_client)
    session.commit()

    # user_id is not in ALLOWED_UPDATE_FIELDS and extra="forbid" rejects unknown fields
    response = client.put(
        "/api/clients/client-mass-id", json={"name": "Still Safe", "user_id": "attacker-id"}
    )
    assert response.status_code == 422  # Rejected by Pydantic


def test_update_client_extra_field_rejected(authenticated_client, session: Session):
    """Test that unknown extra fields are rejected by extra='forbid'."""
    client, user = authenticated_client

    db_client = Client(id="client-extra-id", user_id=user.id, name="Test", email="test@test.com")
    session.add(db_client)
    session.commit()

    response = client.put("/api/clients/client-extra-id", json={"name": "Test", "is_admin": True})
    assert response.status_code == 422


# ────────────────────────────────────────────────
# DELETE /api/clients/{client_id}
# ────────────────────────────────────────────────


def test_delete_client(authenticated_client, session: Session):
    """Test deleting a client."""
    client, user = authenticated_client

    db_client = Client(
        id="client-delete-id", user_id=user.id, name="Delete Me", email="delete@test.com"
    )
    session.add(db_client)
    session.commit()

    response = client.delete("/api/clients/client-delete-id")
    assert response.status_code == 204

    # Verify client is gone
    session.expire_all()
    assert session.get(Client, "client-delete-id") is None


def test_delete_client_not_found(authenticated_client):
    """Test 404 when deleting non-existent client."""
    client, user = authenticated_client
    response = client.delete("/api/clients/nonexistent-id")
    assert response.status_code == 404


def test_delete_client_other_user(authenticated_client, session: Session):
    """Test that deleting another user's client returns 404."""
    client, user = authenticated_client

    other_user = User(
        id="other-user-del", email="other-del@test.com", name="Other", email_verified=False
    )
    session.add(other_user)
    other_client = Client(
        id="other-client-del", user_id=other_user.id, name="Secret", email="secret@test.com"
    )
    session.add(other_client)
    session.commit()

    response = client.delete("/api/clients/other-client-del")
    assert response.status_code == 404

    # Verify client still exists
    session.expire_all()
    assert session.get(Client, "other-client-del") is not None


# ────────────────────────────────────────────────
# Input Validation
# ────────────────────────────────────────────────


def test_create_client_invalid_email(authenticated_client):
    """Test that invalid email format is rejected."""
    client, user = authenticated_client
    response = client.post("/api/clients", json={"name": "Test", "email": "not-an-email"})
    assert response.status_code == 422


def test_create_client_name_too_long(authenticated_client):
    """Test that name exceeding max_length is rejected."""
    client, user = authenticated_client
    response = client.post(
        "/api/clients",
        json={
            "name": "A" * 101,  # max_length=100
            "email": "test@test.com",
        },
    )
    assert response.status_code == 422


def test_create_client_extra_fields_rejected(authenticated_client):
    """Test that extra fields in create payload are rejected."""
    client, user = authenticated_client
    response = client.post(
        "/api/clients",
        json={
            "name": "Test",
            "email": "test@test.com",
            "is_admin": True,  # Unknown field
        },
    )
    assert response.status_code == 422


def test_create_client_missing_required_fields(authenticated_client):
    """Test that missing required fields are rejected."""
    client, user = authenticated_client

    # Missing email
    response = client.post("/api/clients", json={"name": "Test"})
    assert response.status_code == 422

    # Missing name
    response = client.post("/api/clients", json={"email": "test@test.com"})
    assert response.status_code == 422


def test_create_client_notes_too_long(authenticated_client):
    """Test that notes exceeding max_length is rejected."""
    client, user = authenticated_client
    response = client.post(
        "/api/clients",
        json={
            "name": "Test",
            "email": "test@test.com",
            "notes": "X" * 5001,  # max_length=5000
        },
    )
    assert response.status_code == 422


def test_pagination_clients(authenticated_client, session: Session):
    """Test client list pagination."""
    client, user = authenticated_client

    for i in range(15):
        session.add(Client(user_id=user.id, name=f"Client {i:02d}", email=f"c{i}@test.com"))
    session.commit()

    # Page 1, limit 5
    res = client.get("/api/clients?page=1&limit=5")
    assert res.status_code == 200
    data = res.json()
    assert len(data["clients"]) == 5
    assert data["total"] == 15

    # Page 3, limit 5
    res = client.get("/api/clients?page=3&limit=5")
    data = res.json()
    assert len(data["clients"]) == 5

    # Page 4, limit 5 (only 0 left)
    res = client.get("/api/clients?page=4&limit=5")
    data = res.json()
    assert len(data["clients"]) == 0
