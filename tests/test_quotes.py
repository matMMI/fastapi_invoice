"""Tests for quote management API."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from decimal import Decimal
from datetime import datetime, timedelta, timezone

from models.user import User
from models.client import Client
from models.quote import Quote, QuoteItem
from models.enums import QuoteStatus, Currency, TaxStatus
from models.auth import Session as AuthSession


@pytest.fixture
def authenticated_client(client: TestClient, session: Session):
    """Create an authenticated test client."""
    # Create user
    user = User(
        id="test-user-id",
        email="test@example.com",
        name="Test User",
        email_verified=False,
        tax_status=TaxStatus.ASSUJETTI # Required for tax calc test
    )
    session.add(user)
    
    # Create client for quotes
    db_client = Client(
        id="test-client-id",
        user_id=user.id,
        name="Test Client",
        email="client@test.com"
    )
    session.add(db_client)

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
    return client, user, db_client


def test_create_quote(authenticated_client, session: Session):
    """Test creating a new quote with items and verification of calculations."""
    client, user, db_client = authenticated_client
    
    payload = {
        "client_id": db_client.id,
        "quote_number": "Q-001",
        "currency": "EUR",
        "tax_rate": "20.00",
        "items": [
            {
                "description": "Service A",
                "quantity": 2,
                "unit_price": "100.00",
                "order": 1
            },
            {
                "description": "Service B",
                "quantity": 1,
                "unit_price": "50.00",
                "order": 2
            }
        ]
    }

    response = client.post("/api/quotes", json=payload)
    assert response.status_code == 201
    data = response.json()
    
    assert data["quote_number"] == "Q-001"
    assert data["client_id"] == db_client.id
    assert data["user_id"] == user.id
    assert len(data["items"]) == 2
    
    # Verify Calculations
    # Item 1: 2 * 100 = 200
    # Item 2: 1 * 50 = 50
    # Subtotal: 250
    # Tax: 250 * 20% = 50
    # Total: 300
    
    assert Decimal(str(data["subtotal"])) == Decimal("250.00")
    assert Decimal(str(data["tax_amount"])) == Decimal("50.00")
    assert Decimal(str(data["total"])) == Decimal("300.00")


def test_list_quotes(authenticated_client, session: Session):
    """Test listing quotes with user isolation."""
    client, user, db_client = authenticated_client
    
    # Create a quote for the test user
    quote1 = Quote(
        user_id=user.id,
        client_id=db_client.id,
        quote_number="Q-USER-1",
        subtotal=Decimal("100"),
        total=Decimal("120"),
        status=QuoteStatus.DRAFT
    )
    session.add(quote1)
    
    # Create another user and quote
    other_user = User(id="other-user", email="other@test.com", name="Other")
    session.add(other_user)
    
    other_quote = Quote(
        user_id=other_user.id,
        client_id=db_client.id, # Technically ID constraints might fail strictly but here we just check visibility
        quote_number="Q-OTHER-1",
        subtotal=Decimal("100"),
        total=Decimal("120")
    )
    session.add(other_quote)
    session.commit()
    
    response = client.get("/api/quotes")
    assert response.status_code == 200
    data = response.json()
    
    assert data["total"] == 1
    assert len(data["quotes"]) == 1
    assert data["quotes"][0]["quote_number"] == "Q-USER-1"


def test_update_quote_status(authenticated_client, session: Session):
    """Test updating quote status."""
    client, user, db_client = authenticated_client
    
    quote = Quote(
        user_id=user.id,
        client_id=db_client.id,
        quote_number="Q-UPDATE",
        status=QuoteStatus.DRAFT
    )
    session.add(quote)
    session.commit()
    
    response = client.put(f"/api/quotes/{quote.id}", json={
        "status": "Sent"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "Sent"


def test_access_other_user_quote(authenticated_client, session: Session):
    """Test accessing another user's quote returns 404."""
    client, user, db_client = authenticated_client
    
    other_user = User(id="other-user", email="other@test.com", name="Other")
    session.add(other_user)
    
    other_quote = Quote(
        id="quote-other-id",
        user_id=other_user.id,
        client_id=db_client.id,
        quote_number="Q-OTHER-ACCESS",
        status=QuoteStatus.DRAFT
    )
    session.add(other_quote)
    session.commit()
    
    response = client.get(f"/api/quotes/{other_quote.id}")
    assert response.status_code == 404
