"""Tests for quote signature workflow."""

import base64
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from models.auth import Session as AuthSession
from models.client import Client
from models.enums import QuoteStatus
from models.quote import Quote
from models.user import User

# Minimal valid 1x1 white PNG (67 bytes)
_MINI_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
    b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
    b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)
VALID_SIGNATURE_DATA = f"data:image/png;base64,{base64.b64encode(_MINI_PNG).decode()}"


@pytest.fixture
def signature_setup(client: TestClient, session: Session):
    """Setup a quote ready for signature testing."""
    # Create user
    user = User(id="sig-user-id", email="sig@example.com", name="Sig User", email_verified=False)
    session.add(user)

    # Create client
    db_client = Client(
        id="sig-client-id", user_id=user.id, name="Sig Client", email="sig@client.com"
    )
    session.add(db_client)

    # Create Initial Quote
    quote = Quote(
        id="quote-to-sign",
        user_id=user.id,
        client_id=db_client.id,
        quote_number="Q-SIG-001",
        status=QuoteStatus.DRAFT,
        subtotal=Decimal("100"),
        total=Decimal("120"),
    )
    session.add(quote)

    # Authenticated Session
    auth_session = AuthSession(
        id="sig-session-id",
        user_id=user.id,
        token="sig-token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        ip_address="127.0.0.1",
        user_agent="test",
    )
    session.add(auth_session)
    session.commit()

    return client, quote


def test_generate_share_link(signature_setup, session: Session):
    """Test generating a share token."""
    client, quote = signature_setup

    # Must be authenticated
    client.headers = {"Authorization": "Bearer sig-token"}

    response = client.post(f"/api/quotes/{quote.id}/share")
    assert response.status_code == 200
    data = response.json()

    assert "share_url" in data
    assert "/sign/" in data["share_url"]

    # Check DB update
    session.refresh(quote)
    assert quote.share_token is not None


def test_public_access_valid_token(signature_setup, session: Session):
    """Test accessing quote via public token."""
    client, quote = signature_setup

    # Manually set token in DB
    quote.share_token = "valid-public-token"
    session.add(quote)
    session.commit()

    # Access without auth header
    client.headers = {}

    response = client.get("/api/public/quotes/valid-public-token")
    assert response.status_code == 200
    data = response.json()

    assert data["quote_number"] == "Q-SIG-001"
    # Should not expose internal IDs ideally, but schema might return them.
    # Check key business data
    assert Decimal(str(data["total"])) == Decimal("120")


def test_sign_action(signature_setup, session: Session):
    """Test signing the quote."""
    client, quote = signature_setup

    quote.share_token = "token-to-sign"
    quote.status = QuoteStatus.SENT  # Usually needs to be sent first
    session.add(quote)
    session.commit()

    client.headers = {}

    payload = {
        "signer_name": "Jean Dupont",
        "signer_email": "jean.dupont@example.com",
        "signature_data": VALID_SIGNATURE_DATA,
    }

    response = client.post("/api/public/quotes/token-to-sign/sign", json=payload)
    assert response.status_code == 200

    # Check DB
    session.refresh(quote)
    assert quote.status == QuoteStatus.SIGNED
    assert quote.signer_name == "Jean Dupont"
    assert quote.signed_at is not None
