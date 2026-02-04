"""Tests for input validation across all schemas.

Covers max_length enforcement, regex patterns, enum validation,
numeric constraints, and edge cases that could cause data corruption.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from models.auth import Session as AuthSession
from models.client import Client
from models.enums import QuoteStatus, TaxStatus
from models.quote import Quote
from models.user import User


@pytest.fixture
def authenticated_client(client: TestClient, session: Session):
    """Create an authenticated test client with user and client."""
    user = User(
        id="test-user-validation",
        email="validation@example.com",
        name="Validation User",
        email_verified=False,
        tax_status=TaxStatus.ASSUJETTI,
    )
    session.add(user)

    db_client = Client(
        id="test-client-validation",
        user_id=user.id,
        name="Validation Client",
        email="client@validation.com",
    )
    session.add(db_client)

    auth_session = AuthSession(
        id="test-session-validation",
        user_id=user.id,
        token="test-token-validation",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        ip_address="127.0.0.1",
        user_agent="test",
    )
    session.add(auth_session)
    session.commit()

    client.headers = {"Authorization": "Bearer test-token-validation"}
    return client, user, db_client


# ────────────────────────────────────────────────
# Quote Number Pattern Validation
# ────────────────────────────────────────────────


def test_quote_number_valid_patterns(authenticated_client):
    """Test that valid quote number patterns are accepted."""
    client, user, db_client = authenticated_client

    for qn in ["Q-001", "Q_2025_001", "ABC123", "Q-2025-001"]:
        response = client.post(
            "/api/quotes",
            json={
                "client_id": db_client.id,
                "quote_number": qn,
                "items": [{"description": "Service", "quantity": 1, "unit_price": "100.00"}],
            },
        )
        assert response.status_code == 201, f"Expected 201 for quote_number={qn}"


def test_quote_number_invalid_characters(authenticated_client):
    """Test that quote numbers with special characters are rejected."""
    client, user, db_client = authenticated_client

    for bad_qn in ["Q/001", "Q 001", "Q#001", "Q@001", "Q;DROP TABLE"]:
        response = client.post(
            "/api/quotes",
            json={
                "client_id": db_client.id,
                "quote_number": bad_qn,
                "items": [{"description": "Service", "quantity": 1, "unit_price": "100.00"}],
            },
        )
        assert response.status_code == 422, f"Expected 422 for quote_number={bad_qn}"


def test_quote_number_too_long(authenticated_client):
    """Test that quote number exceeding max_length=50 is rejected."""
    client, user, db_client = authenticated_client

    response = client.post(
        "/api/quotes",
        json={
            "client_id": db_client.id,
            "quote_number": "Q" * 51,
            "items": [{"description": "Service", "quantity": 1, "unit_price": "100.00"}],
        },
    )
    assert response.status_code == 422


# ────────────────────────────────────────────────
# Quote Item Numeric Constraints
# ────────────────────────────────────────────────


def test_quote_item_quantity_must_be_positive(authenticated_client):
    """Test that quantity <= 0 is rejected (gt=0)."""
    client, user, db_client = authenticated_client

    for bad_qty in [0, -1, "-5.00"]:
        response = client.post(
            "/api/quotes",
            json={
                "client_id": db_client.id,
                "items": [{"description": "Service", "quantity": bad_qty, "unit_price": "100.00"}],
            },
        )
        assert response.status_code == 422, f"Expected 422 for quantity={bad_qty}"


def test_quote_item_unit_price_non_negative(authenticated_client):
    """Test that unit_price < 0 is rejected (ge=0), but 0 is allowed."""
    client, user, db_client = authenticated_client

    # Negative price should fail
    response = client.post(
        "/api/quotes",
        json={
            "client_id": db_client.id,
            "items": [{"description": "Service", "quantity": 1, "unit_price": "-10.00"}],
        },
    )
    assert response.status_code == 422

    # Zero price should succeed
    response = client.post(
        "/api/quotes",
        json={
            "client_id": db_client.id,
            "items": [{"description": "Free Service", "quantity": 1, "unit_price": "0.00"}],
        },
    )
    assert response.status_code == 201


def test_quote_item_description_required(authenticated_client):
    """Test that empty description is rejected (min_length=1)."""
    client, user, db_client = authenticated_client

    response = client.post(
        "/api/quotes",
        json={
            "client_id": db_client.id,
            "items": [{"description": "", "quantity": 1, "unit_price": "100.00"}],
        },
    )
    assert response.status_code == 422


def test_quote_item_description_too_long(authenticated_client):
    """Test that description exceeding max_length=2000 is rejected."""
    client, user, db_client = authenticated_client

    response = client.post(
        "/api/quotes",
        json={
            "client_id": db_client.id,
            "items": [{"description": "A" * 2001, "quantity": 1, "unit_price": "100.00"}],
        },
    )
    assert response.status_code == 422


# ────────────────────────────────────────────────
# Quote Text Fields Length
# ────────────────────────────────────────────────


def test_quote_notes_too_long(authenticated_client):
    """Test that notes exceeding max_length=5000 is rejected."""
    client, user, db_client = authenticated_client

    response = client.post(
        "/api/quotes",
        json={
            "client_id": db_client.id,
            "notes": "X" * 5001,
            "items": [{"description": "Service", "quantity": 1, "unit_price": "100.00"}],
        },
    )
    assert response.status_code == 422


def test_quote_payment_terms_too_long(authenticated_client):
    """Test that payment_terms exceeding max_length=2000 is rejected."""
    client, user, db_client = authenticated_client

    response = client.post(
        "/api/quotes",
        json={
            "client_id": db_client.id,
            "payment_terms": "X" * 2001,
            "items": [{"description": "Service", "quantity": 1, "unit_price": "100.00"}],
        },
    )
    assert response.status_code == 422


# ────────────────────────────────────────────────
# Quote Tax Rate Validation
# ────────────────────────────────────────────────


def test_quote_tax_rate_non_negative(authenticated_client):
    """Test that negative tax_rate is rejected (ge=0)."""
    client, user, db_client = authenticated_client

    response = client.post(
        "/api/quotes",
        json={
            "client_id": db_client.id,
            "tax_rate": "-5.00",
            "items": [{"description": "Service", "quantity": 1, "unit_price": "100.00"}],
        },
    )
    assert response.status_code == 422


# ────────────────────────────────────────────────
# Client Email Validation
# ────────────────────────────────────────────────


def test_client_email_patterns(authenticated_client):
    """Test various email format validations."""
    client, user, db_client = authenticated_client

    # Valid
    for valid_email in ["user@example.com", "user.name@domain.co.uk", "user+tag@test.com"]:
        response = client.post("/api/clients", json={"name": "Test", "email": valid_email})
        assert response.status_code == 201, f"Expected 201 for email={valid_email}"

    # Invalid
    for invalid_email in ["not-email", "@missing.com", "missing@", "spaces in@email.com"]:
        response = client.post("/api/clients", json={"name": "Test", "email": invalid_email})
        assert response.status_code == 422, f"Expected 422 for email={invalid_email}"


# ────────────────────────────────────────────────
# Client Field Lengths
# ────────────────────────────────────────────────


def test_client_field_max_lengths(authenticated_client):
    """Test max_length enforcement on all client fields."""
    client, user, db_client = authenticated_client

    field_limits = {
        "phone": 50,
        "city": 100,
        "postal_code": 20,
        "country": 100,
        "vat_number": 50,
        "address": 1000,
        "company": 255,
    }

    for field, max_len in field_limits.items():
        response = client.post(
            "/api/clients",
            json={"name": "Test", "email": f"{field}@test.com", field: "X" * (max_len + 1)},
        )
        assert response.status_code == 422, f"Expected 422 for {field} with length {max_len + 1}"


# ────────────────────────────────────────────────
# Quote IDOR Prevention
# ────────────────────────────────────────────────


def test_create_quote_with_other_users_client(authenticated_client, session: Session):
    """Test that creating a quote with another user's client_id is rejected."""
    client, user, db_client = authenticated_client

    other_user = User(
        id="other-user-idor", email="other@idor.com", name="Other", email_verified=False
    )
    session.add(other_user)
    other_client = Client(
        id="other-client-idor", user_id=other_user.id, name="Other's Client", email="oc@test.com"
    )
    session.add(other_client)
    session.commit()

    response = client.post(
        "/api/quotes",
        json={
            "client_id": "other-client-idor",
            "items": [{"description": "Service", "quantity": 1, "unit_price": "100.00"}],
        },
    )
    assert response.status_code == 404  # Client not found for this user


def test_update_quote_reassign_to_other_users_client(authenticated_client, session: Session):
    """Test that reassigning a quote to another user's client_id is rejected."""
    client, user, db_client = authenticated_client

    # Create a quote owned by the current user
    quote = Quote(
        id="quote-reassign-test",
        user_id=user.id,
        client_id=db_client.id,
        quote_number="Q-REASSIGN",
        status=QuoteStatus.DRAFT,
        tax_status=TaxStatus.ASSUJETTI,
    )
    session.add(quote)

    other_user = User(
        id="other-user-reassign", email="other@reassign.com", name="Other", email_verified=False
    )
    session.add(other_user)
    other_client = Client(
        id="other-client-reassign",
        user_id=other_user.id,
        name="Other's Client",
        email="oc@test.com",
    )
    session.add(other_client)
    session.commit()

    response = client.put(f"/api/quotes/{quote.id}", json={"client_id": "other-client-reassign"})
    assert response.status_code == 404


# ────────────────────────────────────────────────
# Quote Empty Items List
# ────────────────────────────────────────────────


def test_create_quote_empty_items(authenticated_client):
    """Test that creating a quote with empty items list still works."""
    client, user, db_client = authenticated_client

    response = client.post("/api/quotes", json={"client_id": db_client.id, "items": []})
    # Empty items list is valid - creates a quote with 0 items and 0 totals
    assert response.status_code == 201
    data = response.json()
    assert len(data["items"]) == 0
    assert Decimal(str(data["subtotal"])) == Decimal("0")
    assert Decimal(str(data["total"])) == Decimal("0")


def test_create_quote_nonexistent_client(authenticated_client):
    """Test that creating a quote with a nonexistent client_id is rejected."""
    client, user, db_client = authenticated_client

    response = client.post(
        "/api/quotes",
        json={
            "client_id": "nonexistent-client-id",
            "items": [{"description": "Service", "quantity": 1, "unit_price": "100.00"}],
        },
    )
    assert response.status_code == 404


# ────────────────────────────────────────────────
# Enum Validation
# ────────────────────────────────────────────────


def test_quote_invalid_status_enum(authenticated_client, session: Session):
    """Test that invalid QuoteStatus values are rejected."""
    client, user, db_client = authenticated_client

    quote = Quote(
        id="quote-enum-test",
        user_id=user.id,
        client_id=db_client.id,
        quote_number="Q-ENUM",
        status=QuoteStatus.DRAFT,
        tax_status=TaxStatus.ASSUJETTI,
    )
    session.add(quote)
    session.commit()

    response = client.put(f"/api/quotes/{quote.id}", json={"status": "InvalidStatus"})
    assert response.status_code == 422


def test_quote_invalid_currency_enum(authenticated_client):
    """Test that invalid Currency values are rejected."""
    client, user, db_client = authenticated_client

    response = client.post(
        "/api/quotes",
        json={
            "client_id": db_client.id,
            "currency": "BTC",
            "items": [{"description": "Service", "quantity": 1, "unit_price": "100.00"}],
        },
    )
    assert response.status_code == 422
