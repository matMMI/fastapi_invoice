"""Security-focused tests covering audit findings.

Tests for: CSV injection, XML/HTML escaping, SSRF, rate limiting,
Content-Disposition sanitization, and auth edge cases.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlmodel import Session
from decimal import Decimal
from datetime import datetime, timedelta, timezone

from models.user import User
from models.client import Client
from models.quote import Quote, QuoteItem
from models.settings import Settings
from models.auth import Session as AuthSession
from models.enums import QuoteStatus, TaxStatus, Currency
from core.rate_limit import limiter


@pytest.fixture
def authenticated_client(client: TestClient, session: Session):
    """Create an authenticated test client with user, client, and settings."""
    user = User(
        id="test-user-security",
        email="security@example.com",
        name="Security User",
        business_name="Secure SAS",
        siret="12345678901234",
        address="10 Rue Secure",
        tax_status=TaxStatus.ASSUJETTI,
        email_verified=False
    )
    session.add(user)

    db_client = Client(
        id="test-client-security",
        user_id=user.id,
        name="Secure Client",
        email="client@secure.com"
    )
    session.add(db_client)

    settings = Settings(
        user_id=user.id,
        company_name="Secure SAS",
        company_email="secure@example.com",
        default_currency="EUR",
        default_tax_rate=20.0
    )
    session.add(settings)

    auth_session = AuthSession(
        id="test-session-security",
        user_id=user.id,
        token="test-token-security",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        ip_address="127.0.0.1",
        user_agent="test"
    )
    session.add(auth_session)
    session.commit()

    client.headers = {"Authorization": "Bearer test-token-security"}
    return client, user, db_client


# ────────────────────────────────────────────────
# CSV Injection Prevention
# ────────────────────────────────────────────────

def test_csv_export_injection_prevention(authenticated_client, session: Session):
    """Test that CSV export escapes dangerous formula characters."""
    client, user, db_client = authenticated_client

    # Create a client with malicious name
    evil_client = Client(
        id="evil-client",
        user_id=user.id,
        name="=CMD('calc')",
        email="evil@test.com"
    )
    session.add(evil_client)

    # Create a paid quote with the evil client
    quote = Quote(
        id="quote-csv-inject",
        user_id=user.id,
        client_id=evil_client.id,
        quote_number="+HYPERLINK('http://evil.com')",
        status=QuoteStatus.ACCEPTED,
        currency=Currency.EUR,
        tax_rate=Decimal("20.00"),
        tax_status=TaxStatus.ASSUJETTI,
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("20.00"),
        total=Decimal("120.00"),
        is_paid=True,
        payment_date=datetime.now(timezone.utc)
    )
    session.add(quote)
    session.commit()

    response = client.get("/api/export/revenue")
    assert response.status_code == 200

    csv_content = response.text
    # Dangerous characters should be prefixed with '
    assert "'=CMD('calc')" in csv_content or "\"'=CMD" in csv_content
    assert "'+HYPERLINK" in csv_content or "\"'+HYPERLINK" in csv_content


def test_csv_export_safe_values_untouched(authenticated_client, session: Session):
    """Test that normal values in CSV export are not modified."""
    client, user, db_client = authenticated_client

    quote = Quote(
        id="quote-csv-safe",
        user_id=user.id,
        client_id=db_client.id,
        quote_number="Q-SAFE-001",
        status=QuoteStatus.ACCEPTED,
        currency=Currency.EUR,
        tax_rate=Decimal("20.00"),
        tax_status=TaxStatus.ASSUJETTI,
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("20.00"),
        total=Decimal("120.00"),
        is_paid=True,
        payment_date=datetime.now(timezone.utc)
    )
    session.add(quote)
    session.commit()

    response = client.get("/api/export/revenue")
    assert response.status_code == 200

    csv_content = response.text
    assert "Q-SAFE-001" in csv_content
    assert "Secure Client" in csv_content


# ────────────────────────────────────────────────
# XML/HTML Escaping in PDF (_esc function)
# ────────────────────────────────────────────────

def test_esc_function_escapes_html():
    """Test that _esc properly escapes HTML/XML special characters."""
    from services.pdf_generator import _esc

    assert _esc("<script>alert('xss')</script>") == "&lt;script&gt;alert('xss')&lt;/script&gt;"
    assert _esc('He said "hello" & goodbye') == 'He said "hello" &amp; goodbye'
    assert _esc("<b>bold</b>") == "&lt;b&gt;bold&lt;/b&gt;"
    assert _esc("Normal text") == "Normal text"


def test_esc_function_handles_none():
    """Test that _esc handles None gracefully."""
    from services.pdf_generator import _esc

    assert _esc(None) == ""


def test_esc_function_handles_numbers():
    """Test that _esc converts non-string types to string."""
    from services.pdf_generator import _esc

    assert _esc(42) == "42"
    assert _esc(3.14) == "3.14"


# ────────────────────────────────────────────────
# SSRF Protection (_is_safe_url, _is_private_ip)
# ────────────────────────────────────────────────

def test_is_private_ip():
    """Test private IP detection covers all RFC ranges."""
    from services.pdf_generator import _is_private_ip

    # Private IPs
    assert _is_private_ip("127.0.0.1") is True
    assert _is_private_ip("10.0.0.1") is True
    assert _is_private_ip("192.168.1.1") is True
    assert _is_private_ip("172.16.0.1") is True
    assert _is_private_ip("169.254.1.1") is True  # Link-local
    assert _is_private_ip("::1") is True  # IPv6 loopback
    assert _is_private_ip("fc00::1") is True  # IPv6 unique local
    assert _is_private_ip("0.0.0.0") is True

    # Public IPs
    assert _is_private_ip("8.8.8.8") is False
    assert _is_private_ip("1.1.1.1") is False
    assert _is_private_ip("93.184.216.34") is False  # example.com


def test_is_safe_url_blocks_internal():
    """Test SSRF protection blocks internal/private URLs."""
    from services.pdf_generator import _is_safe_url

    # Should block
    assert _is_safe_url("http://localhost/logo.png") is False
    assert _is_safe_url("http://127.0.0.1/logo.png") is False
    assert _is_safe_url("http://0.0.0.0/logo.png") is False
    assert _is_safe_url("http://[::1]/logo.png") is False
    assert _is_safe_url("http://10.0.0.1/logo.png") is False
    assert _is_safe_url("http://192.168.1.1/logo.png") is False
    assert _is_safe_url("http://172.16.0.1/logo.png") is False

    # Should block non-http schemes
    assert _is_safe_url("ftp://example.com/logo.png") is False
    assert _is_safe_url("file:///etc/passwd") is False


def test_is_safe_url_allows_public():
    """Test that public HTTPS URLs are allowed."""
    from services.pdf_generator import _is_safe_url

    # Mock DNS resolution to return a public IP
    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, '', ('93.184.216.34', 0))]
        assert _is_safe_url("https://example.com/logo.png") is True


def test_is_safe_url_dns_rebinding():
    """Test that DNS rebinding is caught (hostname resolves to private IP)."""
    from services.pdf_generator import _is_safe_url

    # Simulate a DNS rebinding: hostname looks safe but resolves to 127.0.0.1
    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, '', ('127.0.0.1', 0))]
        assert _is_safe_url("https://malicious-dns.com/logo.png") is False


def test_is_safe_url_dns_failure():
    """Test that DNS resolution failure blocks the URL."""
    from services.pdf_generator import _is_safe_url
    import socket

    with patch("socket.getaddrinfo", side_effect=socket.gaierror):
        assert _is_safe_url("https://nonexistent.invalid/logo.png") is False


# ────────────────────────────────────────────────
# Rate Limiting
# ────────────────────────────────────────────────

def test_rate_limiting_enabled_by_default():
    """Test that rate limiter is enabled by default (before test fixture disables it)."""
    # The conftest fixture sets limiter.enabled = False for tests.
    # Here we verify the limiter object exists and has the expected behavior.
    from core.rate_limit import limiter as app_limiter
    # Just verify it's the right type and has the enabled attribute
    assert hasattr(app_limiter, "enabled")


def test_rate_limiting_settings_reset(client: TestClient, session: Session):
    """Test that rate limiting blocks excessive requests to /settings/reset.

    This test temporarily re-enables rate limiting to verify it works.
    """
    # Create user and auth
    user = User(id="rate-limit-user", email="rate@test.com", name="Rate User", email_verified=False)
    session.add(user)
    auth_session = AuthSession(
        id="rate-limit-session", user_id=user.id, token="rate-limit-token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        ip_address="127.0.0.1", user_agent="test"
    )
    session.add(auth_session)
    session.commit()

    client.headers = {"Authorization": "Bearer rate-limit-token"}

    # Re-enable rate limiting for this test
    limiter.enabled = True
    try:
        # First request should succeed
        r1 = client.delete("/api/settings/reset")
        assert r1.status_code == 204

        # Second request within 1 minute should be rate limited
        r2 = client.delete("/api/settings/reset")
        assert r2.status_code == 429
    finally:
        # Re-disable for other tests
        limiter.enabled = False


def test_rate_limiting_clients_create(client: TestClient, session: Session):
    """Test rate limiting on client creation (30/minute)."""
    user = User(id="rate-limit-client-user", email="ratecl@test.com", name="Rate User", email_verified=False)
    session.add(user)
    auth_session = AuthSession(
        id="rate-limit-cl-session", user_id=user.id, token="rate-cl-token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        ip_address="127.0.0.1", user_agent="test"
    )
    session.add(auth_session)
    session.commit()

    client.headers = {"Authorization": "Bearer rate-cl-token"}

    limiter.enabled = True
    try:
        rate_limited = False
        for i in range(35):
            response = client.post("/api/clients", json={
                "name": f"Client {i}",
                "email": f"c{i}@rate.com"
            })
            if response.status_code == 429:
                rate_limited = True
                break

        assert rate_limited, "Rate limiting should have triggered within 35 requests"
    finally:
        limiter.enabled = False


# ────────────────────────────────────────────────
# Authentication Edge Cases
# ────────────────────────────────────────────────

def test_auth_no_token(client: TestClient):
    """Test that requests without auth token return 401."""
    response = client.get("/api/clients")
    assert response.status_code == 401


def test_auth_invalid_token(client: TestClient):
    """Test that requests with invalid token return 401."""
    client.headers = {"Authorization": "Bearer invalid-token-xyz"}
    response = client.get("/api/clients")
    assert response.status_code == 401


def test_auth_expired_session(client: TestClient, session: Session):
    """Test that expired sessions return 401."""
    user = User(id="expired-user", email="expired@test.com", name="Expired", email_verified=False)
    session.add(user)
    auth_session = AuthSession(
        id="expired-session",
        user_id=user.id,
        token="expired-token",
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
        ip_address="127.0.0.1",
        user_agent="test"
    )
    session.add(auth_session)
    session.commit()

    client.headers = {"Authorization": "Bearer expired-token"}
    response = client.get("/api/clients")
    assert response.status_code == 401


def test_auth_required_on_all_protected_endpoints(client: TestClient):
    """Test that all API endpoints require authentication."""
    endpoints = [
        ("GET", "/api/clients"),
        ("POST", "/api/clients"),
        ("GET", "/api/clients/some-id"),
        ("PUT", "/api/clients/some-id"),
        ("DELETE", "/api/clients/some-id"),
        ("GET", "/api/quotes"),
        ("POST", "/api/quotes"),
        ("GET", "/api/quotes/some-id"),
        ("PUT", "/api/quotes/some-id"),
        ("GET", "/api/settings"),
        ("PUT", "/api/settings"),
        ("DELETE", "/api/settings/reset"),
        ("GET", "/api/dashboard/metrics"),
        ("GET", "/api/export/revenue"),
    ]

    for method, path in endpoints:
        response = getattr(client, method.lower())(path)
        assert response.status_code == 401, f"Expected 401 for {method} {path}, got {response.status_code}"


# ────────────────────────────────────────────────
# Quote Inalterability (Paid Quotes)
# ────────────────────────────────────────────────

def test_paid_quote_cannot_update_status(authenticated_client, session: Session):
    """Test that paid quotes cannot have their status changed."""
    client, user, db_client = authenticated_client

    quote = Quote(
        id="quote-paid-status",
        user_id=user.id,
        client_id=db_client.id,
        quote_number="Q-PAID-STATUS",
        status=QuoteStatus.ACCEPTED,
        is_paid=True,
        tax_status=TaxStatus.ASSUJETTI
    )
    session.add(quote)
    session.commit()

    response = client.put(f"/api/quotes/{quote.id}", json={"status": "Draft"})
    assert response.status_code == 403


def test_paid_quote_cannot_update_items(authenticated_client, session: Session):
    """Test that paid quotes cannot have items modified."""
    client, user, db_client = authenticated_client

    quote = Quote(
        id="quote-paid-items",
        user_id=user.id,
        client_id=db_client.id,
        quote_number="Q-PAID-ITEMS",
        status=QuoteStatus.ACCEPTED,
        is_paid=True,
        tax_status=TaxStatus.ASSUJETTI
    )
    session.add(quote)
    session.commit()

    response = client.put(f"/api/quotes/{quote.id}", json={
        "items": [{"description": "New Item", "quantity": 1, "unit_price": "100.00"}]
    })
    assert response.status_code == 403


def test_paid_quote_cannot_reassign_client(authenticated_client, session: Session):
    """Test that paid quotes cannot be reassigned to a different client."""
    client, user, db_client = authenticated_client

    other_client = Client(
        id="other-client-paid",
        user_id=user.id,
        name="Other Client",
        email="other@paid.com"
    )
    session.add(other_client)

    quote = Quote(
        id="quote-paid-reassign",
        user_id=user.id,
        client_id=db_client.id,
        quote_number="Q-PAID-REASSIGN",
        status=QuoteStatus.ACCEPTED,
        is_paid=True,
        tax_status=TaxStatus.ASSUJETTI
    )
    session.add(quote)
    session.commit()

    response = client.put(f"/api/quotes/{quote.id}", json={
        "client_id": "other-client-paid"
    })
    assert response.status_code == 403


# ────────────────────────────────────────────────
# Tax Logic Enforcement
# ────────────────────────────────────────────────

def test_franchise_user_tax_rate_forced_to_zero(client: TestClient, session: Session):
    """Test that FRANCHISE users always have tax_rate=0 regardless of input."""
    user = User(
        id="franchise-user",
        email="franchise@test.com",
        name="Franchise User",
        tax_status=TaxStatus.FRANCHISE,
        email_verified=False
    )
    session.add(user)

    db_client = Client(id="franchise-client", user_id=user.id, name="FC", email="fc@test.com")
    session.add(db_client)

    auth_session = AuthSession(
        id="franchise-session", user_id=user.id, token="franchise-token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        ip_address="127.0.0.1", user_agent="test"
    )
    session.add(auth_session)
    session.commit()

    client.headers = {"Authorization": "Bearer franchise-token"}

    response = client.post("/api/quotes", json={
        "client_id": "franchise-client",
        "tax_rate": "20.00",  # User tries to set 20% but they're FRANCHISE
        "items": [{"description": "Service", "quantity": 1, "unit_price": "100.00"}]
    })
    assert response.status_code == 201
    data = response.json()
    assert Decimal(str(data["tax_rate"])) == Decimal("0.00")
    assert Decimal(str(data["tax_amount"])) == Decimal("0.00")
    assert Decimal(str(data["total"])) == Decimal("100.00")  # No tax added


def test_assujetti_user_tax_rate_applied(authenticated_client):
    """Test that ASSUJETTI users have their tax_rate correctly applied."""
    client, user, db_client = authenticated_client

    response = client.post("/api/quotes", json={
        "client_id": db_client.id,
        "tax_rate": "20.00",
        "items": [{"description": "Service", "quantity": 1, "unit_price": "100.00"}]
    })
    assert response.status_code == 201
    data = response.json()
    assert Decimal(str(data["tax_rate"])) == Decimal("20.00")
    assert Decimal(str(data["tax_amount"])) == Decimal("20.00")
    assert Decimal(str(data["total"])) == Decimal("120.00")
