"""Tests for settings management API (GET + PUT)."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from models.auth import Session as AuthSession
from models.enums import TaxStatus
from models.settings import Settings
from models.user import User


@pytest.fixture
def authenticated_client(client: TestClient, session: Session):
    """Create an authenticated test client with user and settings."""
    user = User(
        id="test-user-settings",
        email="settings@example.com",
        name="Settings User",
        business_name="Test SAS",
        siret="12345678901234",
        address="10 Rue Test, 75000 Paris",
        tax_status=TaxStatus.FRANCHISE,
        email_verified=False,
    )
    session.add(user)

    auth_session = AuthSession(
        id="test-session-settings",
        user_id=user.id,
        token="test-token-settings",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        ip_address="127.0.0.1",
        user_agent="test",
    )
    session.add(auth_session)
    session.commit()

    client.headers = {"Authorization": "Bearer test-token-settings"}
    return client, user


# ────────────────────────────────────────────────
# GET /api/settings
# ────────────────────────────────────────────────


def test_get_settings_creates_defaults(authenticated_client, session: Session):
    """Test that GET /settings creates default settings if none exist."""
    client, user = authenticated_client

    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()

    # User identity fields
    assert data["name"] == "Settings User"
    assert data["business_name"] == "Test SAS"
    assert data["email"] == "settings@example.com"
    assert data["siret"] == "12345678901234"
    assert data["tax_status"] == "FRANCHISE"

    # Default settings values
    assert data["default_currency"] == "EUR"
    assert data["default_tax_rate"] == 20.0


def test_get_settings_with_existing(authenticated_client, session: Session):
    """Test GET /settings when settings record already exists."""
    client, user = authenticated_client

    # Pre-create settings
    settings = Settings(
        user_id=user.id,
        company_name="Test SAS",
        company_email="company@test.com",
        company_phone="+33600000000",
        company_website="https://test.com",
        default_currency="EUR",
        default_tax_rate=10.0,
        pdf_footer_text="Merci",
        vat_exemption_text="TVA non applicable",
        late_payment_penalties="3x taux BCE",
    )
    session.add(settings)
    session.commit()

    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()

    assert data["company_email"] == "company@test.com"
    assert data["company_phone"] == "+33600000000"
    assert data["company_website"] == "https://test.com"
    assert data["default_tax_rate"] == 10.0
    assert data["pdf_footer_text"] == "Merci"
    assert data["vat_exemption_text"] == "TVA non applicable"
    assert data["late_payment_penalties"] == "3x taux BCE"


# ────────────────────────────────────────────────
# PUT /api/settings
# ────────────────────────────────────────────────


def test_update_settings(authenticated_client, session: Session):
    """Test updating settings with valid data."""
    client, user = authenticated_client

    payload = {
        "name": "Updated Name",
        "business_name": "Updated SAS",
        "email": "updated@example.com",
        "siret": "98765432101234",
        "address": "20 Rue Updated",
        "tax_status": "ASSUJETTI",
        "default_currency": "EUR",
        "default_tax_rate": 10.0,
        "pdf_footer_text": "Footer text",
        "vat_exemption_text": "Custom exemption",
        "late_payment_penalties": "Custom penalties",
    }

    response = client.put("/api/settings", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["name"] == "Updated Name"
    assert data["business_name"] == "Updated SAS"
    assert data["siret"] == "98765432101234"
    assert data["tax_status"] == "ASSUJETTI"
    assert data["default_tax_rate"] == 10.0


# ────────────────────────────────────────────────
# SIRET Validation
# ────────────────────────────────────────────────


def test_update_settings_siret_valid_14_digits(authenticated_client):
    """Test that a valid 14-digit SIRET passes."""
    client, user = authenticated_client

    response = client.put(
        "/api/settings",
        json={
            "name": "Test",
            "email": "test@test.com",
            "siret": "12345678901234",
            "default_currency": "EUR",
            "default_tax_rate": 20.0,
        },
    )
    assert response.status_code == 200
    assert response.json()["siret"] == "12345678901234"


def test_update_settings_siret_with_spaces_rejected(authenticated_client):
    """Test that SIRET with spaces is rejected by schema max_length=14.

    The schema enforces max_length=14 at the Pydantic level, so "123 456 789 01234"
    (17 chars with spaces) is rejected before the router logic can strip spaces.
    Users must submit the SIRET without spaces.
    """
    client, user = authenticated_client

    response = client.put(
        "/api/settings",
        json={
            "name": "Test",
            "email": "test@test.com",
            "siret": "123 456 789 01234",  # 17 chars > max_length=14
            "default_currency": "EUR",
            "default_tax_rate": 20.0,
        },
    )
    assert response.status_code == 422


def test_update_settings_siret_too_short(authenticated_client):
    """Test that SIRET with fewer than 14 digits is rejected."""
    client, user = authenticated_client

    response = client.put(
        "/api/settings",
        json={
            "name": "Test",
            "email": "test@test.com",
            "siret": "1234567890",  # Only 10 digits
            "default_currency": "EUR",
            "default_tax_rate": 20.0,
        },
    )
    assert response.status_code == 422


def test_update_settings_siret_too_long(authenticated_client):
    """Test that SIRET with more than 14 digits is rejected.

    The schema has max_length=14, so Pydantic rejects before the router logic.
    """
    client, user = authenticated_client

    response = client.put(
        "/api/settings",
        json={
            "name": "Test",
            "email": "test@test.com",
            "siret": "123456789012345",  # 15 digits
            "default_currency": "EUR",
            "default_tax_rate": 20.0,
        },
    )
    assert response.status_code == 422


def test_update_settings_siret_non_numeric(authenticated_client):
    """Test that SIRET with non-digit characters (after space removal) is rejected."""
    client, user = authenticated_client

    response = client.put(
        "/api/settings",
        json={
            "name": "Test",
            "email": "test@test.com",
            "siret": "ABCDE678901234",
            "default_currency": "EUR",
            "default_tax_rate": 20.0,
        },
    )
    assert response.status_code == 422


def test_update_settings_siret_null_allowed(authenticated_client):
    """Test that null SIRET is allowed (optional field)."""
    client, user = authenticated_client

    response = client.put(
        "/api/settings",
        json={
            "name": "Test",
            "email": "test@test.com",
            "siret": None,
            "default_currency": "EUR",
            "default_tax_rate": 20.0,
        },
    )
    assert response.status_code == 200


# ────────────────────────────────────────────────
# Logo URL Validation
# ────────────────────────────────────────────────


def test_update_settings_logo_url_https(authenticated_client):
    """Test that HTTPS logo URL is accepted."""
    client, user = authenticated_client

    response = client.put(
        "/api/settings",
        json={
            "name": "Test",
            "email": "test@test.com",
            "logo_url": "https://example.com/logo.png",
            "default_currency": "EUR",
            "default_tax_rate": 20.0,
        },
    )
    assert response.status_code == 200
    assert response.json()["logo_url"] == "https://example.com/logo.png"


def test_update_settings_logo_url_http(authenticated_client):
    """Test that HTTP logo URL is accepted."""
    client, user = authenticated_client

    response = client.put(
        "/api/settings",
        json={
            "name": "Test",
            "email": "test@test.com",
            "logo_url": "http://example.com/logo.png",
            "default_currency": "EUR",
            "default_tax_rate": 20.0,
        },
    )
    assert response.status_code == 200


def test_update_settings_logo_url_relative_path(authenticated_client):
    """Test that relative paths (starting with /) are accepted."""
    client, user = authenticated_client

    response = client.put(
        "/api/settings",
        json={
            "name": "Test",
            "email": "test@test.com",
            "logo_url": "/uploads/logo.png",
            "default_currency": "EUR",
            "default_tax_rate": 20.0,
        },
    )
    assert response.status_code == 200


def test_update_settings_logo_url_invalid_scheme(authenticated_client):
    """Test that non-http(s) URLs are rejected (e.g., ftp://, file://, javascript:)."""
    client, user = authenticated_client

    for bad_url in ["ftp://example.com/logo.png", "file:///etc/passwd", "javascript:alert(1)"]:
        response = client.put(
            "/api/settings",
            json={
                "name": "Test",
                "email": "test@test.com",
                "logo_url": bad_url,
                "default_currency": "EUR",
                "default_tax_rate": 20.0,
            },
        )
        assert response.status_code == 422, f"Expected 422 for logo_url={bad_url}"


def test_update_settings_logo_url_null_allowed(authenticated_client):
    """Test that null logo URL is allowed."""
    client, user = authenticated_client

    response = client.put(
        "/api/settings",
        json={
            "name": "Test",
            "email": "test@test.com",
            "logo_url": None,
            "default_currency": "EUR",
            "default_tax_rate": 20.0,
        },
    )
    assert response.status_code == 200


# ────────────────────────────────────────────────
# Field Length Validation
# ────────────────────────────────────────────────


def test_update_settings_name_too_long(authenticated_client):
    """Test that name exceeding max_length=200 is rejected."""
    client, user = authenticated_client

    response = client.put(
        "/api/settings",
        json={
            "name": "A" * 201,
            "email": "test@test.com",
            "default_currency": "EUR",
            "default_tax_rate": 20.0,
        },
    )
    assert response.status_code == 422


def test_update_settings_pdf_footer_too_long(authenticated_client):
    """Test that pdf_footer_text exceeding max_length=2000 is rejected."""
    client, user = authenticated_client

    response = client.put(
        "/api/settings",
        json={
            "name": "Test",
            "email": "test@test.com",
            "pdf_footer_text": "X" * 2001,
            "default_currency": "EUR",
            "default_tax_rate": 20.0,
        },
    )
    assert response.status_code == 422
