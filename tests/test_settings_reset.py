"""Tests for the account reset endpoint (DELETE /api/settings/reset)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from models.auth import Session as AuthSession
from models.client import Client
from models.quote import Quote, QuoteItem
from models.user import User


@pytest.fixture
def authenticated_client(client: TestClient, session: Session):
    """Create an authenticated test client with a user."""
    user = User(
        id="test-user-id",
        email="test@example.com",
        name="Test User",
        email_verified=False,
    )
    session.add(user)

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

    client.headers = {"Authorization": "Bearer test-token"}
    return client, user


@pytest.fixture
def user_with_data(authenticated_client, session: Session):
    """Create a user with clients, quotes, and quote items."""
    client, user = authenticated_client

    # Create clients
    client1 = Client(
        id="client-1",
        user_id=user.id,
        name="Client One",
        email="client1@example.com",
        company="Company One",
    )
    client2 = Client(
        id="client-2",
        user_id=user.id,
        name="Client Two",
        email="client2@example.com",
    )
    session.add(client1)
    session.add(client2)
    session.commit()

    # Create quotes
    quote1 = Quote(
        id="quote-1",
        quote_number="DEV-001",
        user_id=user.id,
        client_id=client1.id,
        subtotal=Decimal("100.00"),
        total=Decimal("100.00"),
    )
    quote2 = Quote(
        id="quote-2",
        quote_number="DEV-002",
        user_id=user.id,
        client_id=client2.id,
        subtotal=Decimal("200.00"),
        total=Decimal("200.00"),
    )
    session.add(quote1)
    session.add(quote2)
    session.commit()

    # Create quote items
    item1 = QuoteItem(
        id="item-1",
        quote_id=quote1.id,
        description="Service A",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        total=Decimal("100.00"),
    )
    item2 = QuoteItem(
        id="item-2",
        quote_id=quote2.id,
        description="Service B",
        quantity=Decimal("2"),
        unit_price=Decimal("100.00"),
        total=Decimal("200.00"),
    )
    session.add(item1)
    session.add(item2)
    session.commit()

    return client, user


def test_reset_returns_204(user_with_data):
    """Test that the reset endpoint returns 204 No Content."""
    client, user = user_with_data
    response = client.delete("/api/settings/reset")
    assert response.status_code == 204


def test_reset_deletes_quotes(user_with_data, session: Session):
    """Test that reset deletes all quotes for the user."""
    client, user = user_with_data

    # Verify quotes exist before reset
    quotes_before = session.exec(select(Quote).where(Quote.user_id == user.id)).all()
    assert len(quotes_before) == 2

    response = client.delete("/api/settings/reset")
    assert response.status_code == 204

    # Verify quotes are deleted
    session.expire_all()
    quotes_after = session.exec(select(Quote).where(Quote.user_id == user.id)).all()
    assert len(quotes_after) == 0


def test_reset_deletes_quote_items(user_with_data, session: Session):
    """Test that reset cascade-deletes all quote items."""
    client, user = user_with_data

    # Verify items exist before reset
    items_before = session.exec(select(QuoteItem)).all()
    assert len(items_before) == 2

    response = client.delete("/api/settings/reset")
    assert response.status_code == 204

    # Verify items are cascade-deleted
    session.expire_all()
    items_after = session.exec(select(QuoteItem)).all()
    assert len(items_after) == 0


def test_reset_deletes_clients(user_with_data, session: Session):
    """Test that reset deletes all clients for the user."""
    client, user = user_with_data

    # Verify clients exist before reset
    clients_before = session.exec(select(Client).where(Client.user_id == user.id)).all()
    assert len(clients_before) == 2

    response = client.delete("/api/settings/reset")
    assert response.status_code == 204

    # Verify clients are deleted
    session.expire_all()
    clients_after = session.exec(select(Client).where(Client.user_id == user.id)).all()
    assert len(clients_after) == 0


def test_reset_preserves_user_account(user_with_data, session: Session):
    """Test that reset does NOT delete the user account."""
    client, user = user_with_data

    response = client.delete("/api/settings/reset")
    assert response.status_code == 204

    # Verify user still exists
    session.expire_all()
    db_user = session.get(User, user.id)
    assert db_user is not None
    assert db_user.email == "test@example.com"


def test_reset_unauthenticated(client: TestClient):
    """Test that reset requires authentication."""
    response = client.delete("/api/settings/reset")
    assert response.status_code == 401


def test_reset_empty_account(authenticated_client, session: Session):
    """Test that reset works when user has no data."""
    client, user = authenticated_client
    response = client.delete("/api/settings/reset")
    assert response.status_code == 204


def test_reset_does_not_affect_other_users(user_with_data, session: Session):
    """Test that reset only deletes data for the authenticated user."""
    client, user = user_with_data

    # Create another user with data
    other_user = User(
        id="other-user-id",
        email="other@example.com",
        name="Other User",
        email_verified=False,
    )
    session.add(other_user)
    session.commit()

    other_client = Client(
        id="other-client",
        user_id=other_user.id,
        name="Other Client",
        email="other-client@example.com",
    )
    session.add(other_client)
    session.commit()

    other_quote = Quote(
        id="other-quote",
        quote_number="DEV-999",
        user_id=other_user.id,
        client_id=other_client.id,
        subtotal=Decimal("500.00"),
        total=Decimal("500.00"),
    )
    session.add(other_quote)
    session.commit()

    # Reset the first user's data
    response = client.delete("/api/settings/reset")
    assert response.status_code == 204

    # Verify other user's data is intact
    session.expire_all()
    other_clients = session.exec(select(Client).where(Client.user_id == other_user.id)).all()
    assert len(other_clients) == 1

    other_quotes = session.exec(select(Quote).where(Quote.user_id == other_user.id)).all()
    assert len(other_quotes) == 1
