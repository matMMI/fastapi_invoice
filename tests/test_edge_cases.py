"""Edge case tests for quotes, signature workflow, and boundary conditions.

Covers: double signing, token revocation, expired tokens, payment workflow,
pagination edge cases, and special character handling.
"""

import base64
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from models.auth import Session as AuthSession
from models.client import Client
from models.enums import Currency, QuoteStatus, TaxStatus
from models.quote import Quote, QuoteItem
from models.user import User

# Minimal valid 1x1 white PNG
_MINI_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
    b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
    b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)
VALID_SIGNATURE = f"data:image/png;base64,{base64.b64encode(_MINI_PNG).decode()}"


@pytest.fixture
def full_setup(client: TestClient, session: Session):
    """Complete setup with user, client, auth, and a draft quote."""
    user = User(
        id="edge-user",
        email="edge@example.com",
        name="Edge User",
        tax_status=TaxStatus.ASSUJETTI,
        email_verified=False,
    )
    session.add(user)

    db_client = Client(
        id="edge-client", user_id=user.id, name="Edge Client", email="edge@client.com"
    )
    session.add(db_client)

    quote = Quote(
        id="edge-quote",
        user_id=user.id,
        client_id=db_client.id,
        quote_number="Q-EDGE-001",
        status=QuoteStatus.DRAFT,
        currency=Currency.EUR,
        tax_rate=Decimal("20.00"),
        tax_status=TaxStatus.ASSUJETTI,
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("20.00"),
        total=Decimal("120.00"),
    )
    session.add(quote)

    item = QuoteItem(
        id="edge-item",
        quote_id=quote.id,
        description="Edge Service",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        total=Decimal("100.00"),
        order=0,
    )
    session.add(item)

    auth_session = AuthSession(
        id="edge-session",
        user_id=user.id,
        token="edge-token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        ip_address="127.0.0.1",
        user_agent="test",
    )
    session.add(auth_session)
    session.commit()

    client.headers = {"Authorization": "Bearer edge-token"}
    return client, user, db_client, quote


# ────────────────────────────────────────────────
# Signature: Double Signing Prevention
# ────────────────────────────────────────────────


def test_double_signing_rejected(full_setup, session: Session):
    """Test that signing an already-signed quote returns 400."""
    client, user, db_client, quote = full_setup

    # First: set up token and sign
    quote.share_token = "double-sign-token"
    quote.status = QuoteStatus.SENT
    session.add(quote)
    session.commit()

    client.headers = {}

    # First sign
    payload = {
        "signer_name": "First Signer",
        "signer_email": "first@test.com",
        "signature_data": VALID_SIGNATURE,
    }
    r1 = client.post("/api/public/quotes/double-sign-token/sign", json=payload)
    assert r1.status_code == 200

    # Quote should now have share_token revoked
    session.refresh(quote)
    assert quote.share_token is None  # Token revoked after signing
    assert quote.status == QuoteStatus.SIGNED


def test_share_token_revoked_after_signing(full_setup, session: Session):
    """Test that the share token is set to None after signing."""
    client, user, db_client, quote = full_setup

    quote.share_token = "revoke-token"
    quote.status = QuoteStatus.SENT
    session.add(quote)
    session.commit()

    client.headers = {}

    payload = {
        "signer_name": "Signer",
        "signer_email": "signer@test.com",
        "signature_data": VALID_SIGNATURE,
    }
    response = client.post("/api/public/quotes/revoke-token/sign", json=payload)
    assert response.status_code == 200

    session.refresh(quote)
    assert quote.share_token is None
    assert quote.share_token_expires_at is None


# ────────────────────────────────────────────────
# Signature: Token Expiration
# ────────────────────────────────────────────────


def test_expired_token_returns_410(full_setup, session: Session):
    """Test that an expired share token returns 410 Gone."""
    client, user, db_client, quote = full_setup

    quote.share_token = "expired-token"
    quote.share_token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    session.add(quote)
    session.commit()

    client.headers = {}
    response = client.get("/api/public/quotes/expired-token")
    assert response.status_code == 410


def test_expired_token_sign_rejected(full_setup, session: Session):
    """Test that signing with an expired token returns 410."""
    client, user, db_client, quote = full_setup

    quote.share_token = "expired-sign-token"
    quote.share_token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    session.add(quote)
    session.commit()

    client.headers = {}
    payload = {
        "signer_name": "Late Signer",
        "signer_email": "late@test.com",
        "signature_data": VALID_SIGNATURE,
    }
    response = client.post("/api/public/quotes/expired-sign-token/sign", json=payload)
    assert response.status_code == 410


def test_invalid_token_returns_404(full_setup):
    """Test that a nonexistent token returns 404."""
    client, user, db_client, quote = full_setup

    client.headers = {}
    response = client.get("/api/public/quotes/nonexistent-token")
    assert response.status_code == 404


# ────────────────────────────────────────────────
# Signature: Validation
# ────────────────────────────────────────────────


def test_sign_invalid_email(full_setup, session: Session):
    """Test that signing with an invalid email is rejected."""
    client, user, db_client, quote = full_setup

    quote.share_token = "validate-email-token"
    quote.status = QuoteStatus.SENT
    session.add(quote)
    session.commit()

    client.headers = {}
    response = client.post(
        "/api/public/quotes/validate-email-token/sign",
        json={
            "signer_name": "Test",
            "signer_email": "not-an-email",
            "signature_data": VALID_SIGNATURE,
        },
    )
    assert response.status_code == 422


def test_sign_invalid_signature_data(full_setup, session: Session):
    """Test that non-PNG signature data is rejected."""
    client, user, db_client, quote = full_setup

    quote.share_token = "validate-sig-token"
    quote.status = QuoteStatus.SENT
    session.add(quote)
    session.commit()

    client.headers = {}

    # Not valid base64
    response = client.post(
        "/api/public/quotes/validate-sig-token/sign",
        json={
            "signer_name": "Test",
            "signer_email": "test@test.com",
            "signature_data": "not-base64-data!!!",
        },
    )
    assert response.status_code == 422

    # Valid base64 but not a PNG
    fake_data = base64.b64encode(b"this is not a PNG image").decode()
    response = client.post(
        "/api/public/quotes/validate-sig-token/sign",
        json={
            "signer_name": "Test",
            "signer_email": "test@test.com",
            "signature_data": f"data:image/png;base64,{fake_data}",
        },
    )
    assert response.status_code == 422


def test_sign_empty_name_rejected(full_setup, session: Session):
    """Test that empty signer name is rejected (min_length=1)."""
    client, user, db_client, quote = full_setup

    quote.share_token = "validate-name-token"
    quote.status = QuoteStatus.SENT
    session.add(quote)
    session.commit()

    client.headers = {}
    response = client.post(
        "/api/public/quotes/validate-name-token/sign",
        json={
            "signer_name": "",
            "signer_email": "test@test.com",
            "signature_data": VALID_SIGNATURE,
        },
    )
    assert response.status_code == 422


# ────────────────────────────────────────────────
# Payment Workflow
# ────────────────────────────────────────────────


def test_mark_as_paid_sets_payment_date(full_setup, session: Session):
    """Test that marking a quote as paid sets the payment_date automatically."""
    client, user, db_client, quote = full_setup

    response = client.put(f"/api/quotes/{quote.id}", json={"is_paid": True})
    assert response.status_code == 200
    data = response.json()
    assert data["is_paid"] is True
    assert data["payment_date"] is not None


def test_mark_as_paid_then_cannot_modify(full_setup, session: Session):
    """Test the full workflow: mark as paid, then try to modify."""
    client, user, db_client, quote = full_setup

    # Mark as paid
    r1 = client.put(f"/api/quotes/{quote.id}", json={"is_paid": True})
    assert r1.status_code == 200

    # Try to modify - should be blocked
    r2 = client.put(f"/api/quotes/{quote.id}", json={"notes": "Can't change this"})
    assert r2.status_code == 403


# ────────────────────────────────────────────────
# Pagination Edge Cases
# ────────────────────────────────────────────────


def test_quotes_pagination(full_setup, session: Session):
    """Test quote pagination with multiple pages."""
    client, user, db_client, quote = full_setup

    # Create 14 more quotes (15 total with the one from fixture)
    for i in range(14):
        q = Quote(
            user_id=user.id,
            client_id=db_client.id,
            quote_number=f"Q-PAGE-{i:03d}",
            status=QuoteStatus.DRAFT,
            subtotal=Decimal("100"),
            total=Decimal("120"),
        )
        session.add(q)
    session.commit()

    # Page 1, limit 5
    res = client.get("/api/quotes?page=1&limit=5")
    assert res.status_code == 200
    data = res.json()
    assert len(data["quotes"]) == 5
    assert data["total"] == 15

    # Page beyond data
    res = client.get("/api/quotes?page=100&limit=5")
    data = res.json()
    assert len(data["quotes"]) == 0
    assert data["total"] == 15  # Total still accurate


def test_quotes_default_pagination(full_setup):
    """Test that default pagination parameters work."""
    client, user, db_client, quote = full_setup

    res = client.get("/api/quotes")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert len(data["quotes"]) >= 1


# ────────────────────────────────────────────────
# Quote Auto-Generated Number
# ────────────────────────────────────────────────


def test_quote_number_auto_generated(full_setup):
    """Test that quote number is auto-generated when not provided."""
    client, user, db_client, quote = full_setup

    response = client.post(
        "/api/quotes",
        json={
            "client_id": db_client.id,
            "items": [{"description": "Service", "quantity": 1, "unit_price": "100.00"}],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["quote_number"].startswith("Q-")
    assert len(data["quote_number"]) > 2


# ────────────────────────────────────────────────
# Multiple Items Calculation
# ────────────────────────────────────────────────


def test_multiple_items_total_calculation(full_setup):
    """Test that totals are correct with multiple items of varying quantities/prices."""
    client, user, db_client, quote = full_setup

    response = client.post(
        "/api/quotes",
        json={
            "client_id": db_client.id,
            "tax_rate": "20.00",
            "items": [
                {"description": "Item A", "quantity": 3, "unit_price": "100.00", "order": 1},
                {"description": "Item B", "quantity": 2, "unit_price": "50.00", "order": 2},
                {"description": "Item C", "quantity": 1, "unit_price": "200.00", "order": 3},
            ],
        },
    )
    assert response.status_code == 201
    data = response.json()

    # 300 + 100 + 200 = 600
    assert Decimal(str(data["subtotal"])) == Decimal("600.00")
    # 600 * 0.20 = 120
    assert Decimal(str(data["tax_amount"])) == Decimal("120.00")
    # 600 + 120 = 720
    assert Decimal(str(data["total"])) == Decimal("720.00")


# ────────────────────────────────────────────────
# Search with Special Characters
# ────────────────────────────────────────────────


def test_search_with_sql_wildcards(full_setup, session: Session):
    """Test that SQL wildcards % and _ in search terms are escaped."""
    client, user, db_client, quote = full_setup

    # Create a client whose name literally contains %
    special_client = Client(
        id="special-client", user_id=user.id, name="100% Organic Corp", email="organic@test.com"
    )
    session.add(special_client)

    normal_client = Client(
        id="normal-client", user_id=user.id, name="Normal Corp", email="normal@test.com"
    )
    session.add(normal_client)
    session.commit()

    # Search for "100%" - should not match everything (% is not a wildcard)
    res = client.get("/api/clients?search=100%25")  # URL-encoded %
    assert res.status_code == 200
    data = res.json()
    # Should only find the one with "100%" in the name
    assert data["total"] <= 1


def test_search_with_underscore(full_setup, session: Session):
    """Test that underscore in search is treated literally, not as SQL single-char wildcard."""
    client, user, db_client, quote = full_setup

    c1 = Client(id="underscore-client", user_id=user.id, name="test_client", email="u@test.com")
    c2 = Client(id="other-5char", user_id=user.id, name="test5client", email="o@test.com")
    session.add(c1)
    session.add(c2)
    session.commit()

    res = client.get("/api/clients?search=test_client")
    assert res.status_code == 200
    data = res.json()
    # Should match "test_client" literally, not "test5client"
    names = [c["name"] for c in data["clients"]]
    assert "test_client" in names


# ────────────────────────────────────────────────
# Share Link Generation
# ────────────────────────────────────────────────


def test_share_link_sets_status_to_sent(full_setup, session: Session):
    """Test that generating a share link changes status to SENT."""
    client, user, db_client, quote = full_setup

    assert quote.status == QuoteStatus.DRAFT

    response = client.post(f"/api/quotes/{quote.id}/share")
    assert response.status_code == 200

    session.refresh(quote)
    assert quote.status == QuoteStatus.SENT
    assert quote.sent_at is not None


def test_share_link_regeneration_overwrites(full_setup, session: Session):
    """Test that regenerating a share link overwrites the old token."""
    client, user, db_client, quote = full_setup

    # First share
    r1 = client.post(f"/api/quotes/{quote.id}/share")
    assert r1.status_code == 200
    token1 = r1.json()["share_url"]

    session.refresh(quote)
    old_token = quote.share_token

    # Second share (regenerate)
    r2 = client.post(f"/api/quotes/{quote.id}/share")
    assert r2.status_code == 200
    token2 = r2.json()["share_url"]

    session.refresh(quote)
    new_token = quote.share_token

    assert token1 != token2
    assert old_token != new_token


def test_share_other_users_quote_rejected(full_setup, session: Session):
    """Test that sharing another user's quote returns 404."""
    client, user, db_client, quote = full_setup

    other_user = User(
        id="other-share-user", email="other-share@test.com", name="Other", email_verified=False
    )
    session.add(other_user)
    other_client = Client(
        id="other-share-client", user_id=other_user.id, name="OC", email="oc@test.com"
    )
    session.add(other_client)
    other_quote = Quote(
        id="other-share-quote",
        user_id=other_user.id,
        client_id=other_client.id,
        quote_number="Q-OTHER-SHARE",
        status=QuoteStatus.DRAFT,
        subtotal=Decimal("100"),
        total=Decimal("120"),
    )
    session.add(other_quote)
    session.commit()

    response = client.post("/api/quotes/other-share-quote/share")
    assert response.status_code == 404
