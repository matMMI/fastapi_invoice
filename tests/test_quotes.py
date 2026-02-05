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


@pytest.fixture
def authenticated_client(client: TestClient, session: Session):
    # Create user
    user = User(
        id="test-user-id",
        email="test@example.com",
        name="Test User",
        email_verified=False,
        tax_status=TaxStatus.ASSUJETTI,  # Required for tax calc test
    )
    session.add(user)

    db_client = Client(
        id="test-client-id", user_id=user.id, name="Test Client", email="client@test.com"
    )
    session.add(db_client)

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
    return client, user, db_client


def test_create_quote(authenticated_client, session: Session):
    client, user, db_client = authenticated_client

    payload = {
        "client_id": db_client.id,
        "quote_number": "Q-001",
        "currency": "EUR",
        "tax_rate": "20.00",
        "items": [
            {"description": "Service A", "quantity": 2, "unit_price": "100.00", "order": 1},
            {"description": "Service B", "quantity": 1, "unit_price": "50.00", "order": 2},
        ],
    }

    response = client.post("/api/quotes", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["quote_number"] == "Q-001"
    assert data["client_id"] == db_client.id
    assert data["user_id"] == user.id
    assert len(data["items"]) == 2
    assert Decimal(str(data["subtotal"])) == Decimal("250.00")
    assert Decimal(str(data["tax_amount"])) == Decimal("50.00")
    assert Decimal(str(data["total"])) == Decimal("300.00")


def test_get_quote(authenticated_client, session: Session):
    """Test fetching a single quote by ID returns all expected fields."""
    client, user, db_client = authenticated_client

    quote = Quote(
        id="test-quote-get",
        user_id=user.id,
        client_id=db_client.id,
        quote_number="Q-GET-001",
        status=QuoteStatus.DRAFT,
        currency=Currency.EUR,
        tax_rate=Decimal("20.00"),
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("20.00"),
        total=Decimal("120.00"),
        notes="Test notes",
    )
    session.add(quote)

    item = QuoteItem(
        quote_id=quote.id,
        description="Test Service",
        quantity=Decimal("2"),
        unit_price=Decimal("50.00"),
        total=Decimal("100.00"),
        order=1,
    )
    session.add(item)
    session.commit()

    response = client.get(f"/api/quotes/{quote.id}")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == "test-quote-get"
    assert data["quote_number"] == "Q-GET-001"
    assert data["client_id"] == db_client.id
    assert data["user_id"] == user.id
    assert data["status"] == "Draft"
    assert data["currency"] == "EUR"
    assert Decimal(str(data["subtotal"])) == Decimal("100.00")
    assert Decimal(str(data["tax_rate"])) == Decimal("20.00")
    assert Decimal(str(data["tax_amount"])) == Decimal("20.00")
    assert Decimal(str(data["total"])) == Decimal("120.00")
    assert data["notes"] == "Test notes"

    # Verify items are included
    assert len(data["items"]) == 1
    assert data["items"][0]["description"] == "Test Service"
    assert Decimal(str(data["items"][0]["quantity"])) == Decimal("2")
    assert Decimal(str(data["items"][0]["unit_price"])) == Decimal("50.00")

    # Verify client_name is included (from JOIN)
    assert data["client_name"] == "Test Client"


def test_list_quotes(authenticated_client, session: Session):
    client, user, db_client = authenticated_client
    quote1 = Quote(
        user_id=user.id,
        client_id=db_client.id,
        quote_number="Q-USER-1",
        subtotal=Decimal("100"),
        total=Decimal("120"),
        status=QuoteStatus.DRAFT,
    )
    session.add(quote1)

    # Create another user and quote
    other_user = User(id="other-user", email="other@test.com", name="Other")
    session.add(other_user)

    other_quote = Quote(
        user_id=other_user.id,
        client_id=db_client.id,  # Technically ID constraints might fail strictly but here we just check visibility
        quote_number="Q-OTHER-1",
        subtotal=Decimal("100"),
        total=Decimal("120"),
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
        user_id=user.id, client_id=db_client.id, quote_number="Q-UPDATE", status=QuoteStatus.DRAFT
    )
    session.add(quote)
    session.commit()

    response = client.put(f"/api/quotes/{quote.id}", json={"status": "Sent"})

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
        status=QuoteStatus.DRAFT,
    )
    session.add(other_quote)
    session.commit()

    response = client.get(f"/api/quotes/{other_quote.id}")
    assert response.status_code == 404


def test_search_quotes(authenticated_client, session: Session):
    """Test searching quotes by client name and quote number."""
    client, user, db_client = authenticated_client

    # Create another client
    client2 = Client(id="client-2", user_id=user.id, name="Dupont SA", email="dupont@test.com")
    session.add(client2)

    q1 = Quote(
        user_id=user.id,
        client_id=db_client.id,
        quote_number="Q-001",
        status=QuoteStatus.DRAFT,
        subtotal=Decimal("100"),
        total=Decimal("120"),
    )
    session.add(q1)

    q2 = Quote(
        user_id=user.id,
        client_id=client2.id,
        quote_number="Q-SEARCH-ME",
        status=QuoteStatus.DRAFT,
        subtotal=Decimal("100"),
        total=Decimal("120"),
    )
    session.add(q2)

    q3 = Quote(
        user_id=user.id,
        client_id=client2.id,
        quote_number="Q-OTHER",
        status=QuoteStatus.DRAFT,
        subtotal=Decimal("100"),
        total=Decimal("120"),
    )
    session.add(q3)
    session.commit()

    res = client.get("/api/quotes?search=Test")
    assert res.status_code == 200
    data = res.json()
    assert len(data["quotes"]) == 1
    assert data["quotes"][0]["quote_number"] == "Q-001"

    res = client.get("/api/quotes?search=SEARCH")
    assert res.status_code == 200
    data = res.json()
    assert len(data["quotes"]) == 1
    assert data["quotes"][0]["quote_number"] == "Q-SEARCH-ME"

    res = client.get("/api/quotes?search=XYZ")
    assert res.status_code == 200
    assert len(res.json()["quotes"]) == 0


def test_update_quote_items_with_id(authenticated_client, session: Session):
    """Test that updating a quote with item IDs preserves existing items."""
    client, user, db_client = authenticated_client

    quote = Quote(
        id="quote-update-items",
        user_id=user.id,
        client_id=db_client.id,
        quote_number="Q-UPD-ITEMS",
        status=QuoteStatus.DRAFT,
        tax_status=TaxStatus.ASSUJETTI,
        tax_rate=Decimal("20.00"),
    )
    session.add(quote)
    session.commit()

    item = QuoteItem(
        id="item-existing",
        quote_id=quote.id,
        description="Original Service",
        quantity=Decimal("2"),
        unit_price=Decimal("100.00"),
        total=Decimal("200.00"),
        order=0,
    )
    session.add(item)
    session.commit()

    response = client.put(
        f"/api/quotes/{quote.id}",
        json={
            "items": [
                {
                    "id": "item-existing",
                    "description": "Updated Service",
                    "quantity": 3,
                    "unit_price": "150.00",
                    "order": 0,
                }
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == "item-existing"
    assert data["items"][0]["description"] == "Updated Service"
    assert Decimal(str(data["items"][0]["quantity"])) == Decimal("3")
    assert Decimal(str(data["items"][0]["unit_price"])) == Decimal("150.00")


def test_update_quote_items_without_id(authenticated_client, session: Session):
    """Test that updating with new items (no id) creates them and removes old ones."""
    client, user, db_client = authenticated_client

    quote = Quote(
        id="quote-new-items",
        user_id=user.id,
        client_id=db_client.id,
        quote_number="Q-NEW-ITEMS",
        status=QuoteStatus.DRAFT,
        tax_status=TaxStatus.ASSUJETTI,
        tax_rate=Decimal("20.00"),
    )
    session.add(quote)
    session.commit()

    old_item = QuoteItem(
        id="item-to-remove",
        quote_id=quote.id,
        description="Old Service",
        quantity=Decimal("1"),
        unit_price=Decimal("50.00"),
        total=Decimal("50.00"),
        order=0,
    )
    session.add(old_item)
    session.commit()

    response = client.put(
        f"/api/quotes/{quote.id}",
        json={
            "items": [
                {
                    "description": "Brand New Service",
                    "quantity": 1,
                    "unit_price": "200.00",
                    "order": 0,
                }
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["description"] == "Brand New Service"
    assert data["items"][0]["id"] != "item-to-remove"

    # Verify old item is deleted
    session.expire_all()
    old = session.get(QuoteItem, "item-to-remove")
    assert old is None


def test_update_quote_item_zero_unit_price(authenticated_client, session: Session):
    """Regression: unit_price=0 must be saved (not ignored by falsy check)."""
    client, user, db_client = authenticated_client

    quote = Quote(
        id="quote-zero-price",
        user_id=user.id,
        client_id=db_client.id,
        quote_number="Q-ZERO-PRICE",
        status=QuoteStatus.DRAFT,
        tax_status=TaxStatus.ASSUJETTI,
        tax_rate=Decimal("20.00"),
    )
    session.add(quote)
    session.commit()

    item = QuoteItem(
        id="item-zero-price",
        quote_id=quote.id,
        description="Expensive Service",
        quantity=Decimal("1"),
        unit_price=Decimal("500.00"),
        total=Decimal("500.00"),
        order=0,
    )
    session.add(item)
    session.commit()

    # Update unit_price to 0
    response = client.put(
        f"/api/quotes/{quote.id}",
        json={
            "items": [
                {
                    "id": "item-zero-price",
                    "description": "Free Service",
                    "quantity": 1,
                    "unit_price": "0.00",
                    "order": 0,
                }
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert Decimal(str(data["items"][0]["unit_price"])) == Decimal("0.00")
    assert Decimal(str(data["total"])) == Decimal("0.00")


def test_update_quote_recalculates_totals(authenticated_client, session: Session):
    """Test that updating items recalculates subtotal, tax, and total."""
    client, user, db_client = authenticated_client

    quote = Quote(
        id="quote-recalc",
        user_id=user.id,
        client_id=db_client.id,
        quote_number="Q-RECALC",
        status=QuoteStatus.DRAFT,
        tax_status=TaxStatus.ASSUJETTI,
        tax_rate=Decimal("20.00"),
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("20.00"),
        total=Decimal("120.00"),
    )
    session.add(quote)
    session.commit()

    item = QuoteItem(
        id="item-recalc",
        quote_id=quote.id,
        description="Service",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        total=Decimal("100.00"),
        order=0,
    )
    session.add(item)
    session.commit()

    response = client.put(
        f"/api/quotes/{quote.id}",
        json={
            "items": [
                {
                    "id": "item-recalc",
                    "description": "Service",
                    "quantity": 5,
                    "unit_price": "200.00",
                    "order": 0,
                }
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert Decimal(str(data["subtotal"])) == Decimal("1000.00")
    assert Decimal(str(data["tax_amount"])) == Decimal("200.00")
    assert Decimal(str(data["total"])) == Decimal("1200.00")


def test_update_paid_quote_forbidden(authenticated_client, session: Session):
    """Test that updating a paid quote is forbidden (inalterability rule)."""
    client, user, db_client = authenticated_client

    quote = Quote(
        id="quote-paid",
        user_id=user.id,
        client_id=db_client.id,
        quote_number="Q-PAID",
        status=QuoteStatus.ACCEPTED,
        is_paid=True,
    )
    session.add(quote)
    session.commit()

    response = client.put(f"/api/quotes/{quote.id}", json={"notes": "Try to modify"})

    assert response.status_code == 403


def test_update_quote_notes_and_payment_terms(authenticated_client, session: Session):
    """Regression: notes and payment_terms must be saved on update."""
    client, user, db_client = authenticated_client

    quote = Quote(
        id="quote-notes",
        user_id=user.id,
        client_id=db_client.id,
        quote_number="Q-NOTES",
        status=QuoteStatus.DRAFT,
    )
    session.add(quote)
    session.commit()

    # Update with notes and payment_terms
    response = client.put(
        f"/api/quotes/{quote.id}",
        json={
            "notes": "Merci pour votre confiance",
            "payment_terms": "Paiement à 30 jours",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["notes"] == "Merci pour votre confiance"
    assert data["payment_terms"] == "Paiement à 30 jours"

    # Update notes to empty string (should clear them)
    response = client.put(
        f"/api/quotes/{quote.id}",
        json={
            "notes": "",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["notes"] == ""
    # payment_terms should be preserved (not sent = not modified)
    assert data["payment_terms"] == "Paiement à 30 jours"


def test_client_name_propagation(authenticated_client, session: Session):
    """Test that updating a client's name is reflected in quote responses."""
    client, user, db_client = authenticated_client

    # Create a quote linked to the client
    quote = Quote(
        id="quote-name-prop",
        user_id=user.id,
        client_id=db_client.id,
        quote_number="Q-NAME-PROP",
        status=QuoteStatus.DRAFT,
    )
    session.add(quote)
    session.commit()

    # Verify initial client_name
    response = client.get(f"/api/quotes/{quote.id}")
    assert response.status_code == 200
    assert response.json()["client_name"] == "Test Client"

    # Update the client's name directly in DB
    db_client.name = "Updated Client Name"
    session.add(db_client)
    session.commit()

    # Verify get_quote returns updated name
    response = client.get(f"/api/quotes/{quote.id}")
    assert response.status_code == 200
    assert response.json()["client_name"] == "Updated Client Name"

    # Verify list_quotes also returns updated name
    response = client.get("/api/quotes")
    assert response.status_code == 200
    quotes = response.json()["quotes"]
    assert any(q["client_name"] == "Updated Client Name" for q in quotes)


def test_delete_quote_success(authenticated_client, session: Session):
    """Test successful deletion of a quote."""
    client, user, db_client = authenticated_client

    quote = Quote(
        id="quote-to-delete",
        user_id=user.id,
        client_id=db_client.id,
        quote_number="Q-DELETE",
        status=QuoteStatus.DRAFT,
    )
    session.add(quote)

    item = QuoteItem(
        id="item-to-delete",
        quote_id=quote.id,
        description="Service",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        total=Decimal("100.00"),
        order=0,
    )
    session.add(item)
    session.commit()

    response = client.delete(f"/api/quotes/{quote.id}")
    assert response.status_code == 204

    # Verify quote is deleted
    session.expire_all()
    deleted_quote = session.get(Quote, "quote-to-delete")
    assert deleted_quote is None

    # Verify items are cascade deleted
    deleted_item = session.get(QuoteItem, "item-to-delete")
    assert deleted_item is None


def test_delete_quote_not_found(authenticated_client, session: Session):
    """Test deleting a non-existent quote returns 404."""
    client, user, db_client = authenticated_client

    response = client.delete("/api/quotes/non-existent-id")
    assert response.status_code == 404


def test_delete_other_user_quote_forbidden(authenticated_client, session: Session):
    """Test deleting another user's quote returns 404 (not 403 to avoid info leak)."""
    client, user, db_client = authenticated_client

    other_user = User(id="other-user-delete", email="other-delete@test.com", name="Other")
    session.add(other_user)

    other_quote = Quote(
        id="quote-other-delete",
        user_id=other_user.id,
        client_id=db_client.id,
        quote_number="Q-OTHER-DELETE",
        status=QuoteStatus.DRAFT,
    )
    session.add(other_quote)
    session.commit()

    response = client.delete(f"/api/quotes/{other_quote.id}")
    assert response.status_code == 404

    # Verify quote still exists
    session.expire_all()
    quote = session.get(Quote, "quote-other-delete")
    assert quote is not None


def test_delete_paid_quote_forbidden(authenticated_client, session: Session):
    """Test that deleting a paid quote is forbidden (inalterability rule)."""
    client, user, db_client = authenticated_client

    quote = Quote(
        id="quote-paid-delete",
        user_id=user.id,
        client_id=db_client.id,
        quote_number="Q-PAID-DELETE",
        status=QuoteStatus.ACCEPTED,
        is_paid=True,
    )
    session.add(quote)
    session.commit()

    response = client.delete(f"/api/quotes/{quote.id}")
    assert response.status_code == 403

    # Verify quote still exists
    session.expire_all()
    quote = session.get(Quote, "quote-paid-delete")
    assert quote is not None
