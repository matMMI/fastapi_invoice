import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from models.user import User
from models.settings import Settings
from models.enums import TaxStatus, QuoteStatus
from models.client import Client
from models.quote import Quote
from datetime import datetime, timedelta, timezone
from models.auth import Session as AuthSession
from uuid import uuid4

def get_auth_headers(client: TestClient, session: Session, tax_status: TaxStatus = TaxStatus.FRANCHISE) -> dict:
    """Helper to create user and get token."""
    user = User(
        email=f"test_{uuid4()}@compliance.com", # Randomize email to avoid unique constraint if db persists
        hashed_password="hashedsecret",
        name="Test Compliance",
        tax_status=tax_status,
        siret="12345678900012",
        address="123 Test St"
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # Create required Settings
    settings = Settings(user_id=user.id, company_name="Test Corp")
    session.add(settings)
    
    # Create a Client
    db_client = Client(user_id=user.id, name="Test Customer", email="customer@test.com")
    session.add(db_client)
    
    # Create Auth Session
    token = str(uuid4())
    expires = datetime.now(timezone.utc) + timedelta(days=1)
    auth_session = AuthSession(
        user_id=user.id,
        token=token,
        expires_at=expires,
        ip_address="127.0.0.1",
        user_agent="pytest"
    )
    session.add(auth_session)
    session.commit()
    session.refresh(db_client)
    
    return {"Authorization": f"Bearer {token}"}, user, db_client

def test_franchise_vat_logic(client: TestClient, session: Session):
    """Test that FRANCHISE status forces 0% VAT."""
    headers, user, db_client = get_auth_headers(client, session, TaxStatus.FRANCHISE)
    
    payload = {
        "client_id": db_client.id,
        "tax_rate": 20.0, # Attempting to set 20%
        "items": [
            {"description": "Service", "quantity": 1, "unit_price": 100.0}
        ]
    }
    
    response = client.post("/api/quotes", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    
    assert float(data["tax_rate"]) == 0.0 # Must be forced to 0
    assert float(data["tax_amount"]) == 0.0
    assert float(data["total"]) == 100.0 
    assert data["tax_status"] == "FRANCHISE"

def test_assujetti_vat_logic(client: TestClient, session: Session):
    """Test that ASSUJETTI status respects VAT rate."""
    # Use different email for unique constraint if not clean DB, but memory DB is clean per test usually.
    # wait, session fixture yields fresh session but same engine? 
    # conftest says "sqlite:///:memory:" inside fixture? No, create_engine is inside fixture. New DB each time.
    
    headers, user, db_client = get_auth_headers(client, session, TaxStatus.ASSUJETTI)
    
    payload = {
        "client_id": db_client.id,
        "tax_rate": 20.0, 
        "items": [
            {"description": "Service", "quantity": 1, "unit_price": 100.0}
        ]
    }
    
    response = client.post("/api/quotes", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    
    assert float(data["tax_rate"]) == 20.0
    assert float(data["tax_amount"]) == 20.0
    assert float(data["total"]) == 120.0
    assert data["tax_status"] == "ASSUJETTI"

def test_quote_locking_logic(client: TestClient, session: Session):
    """Test that Paid quotes cannot be modified."""
    headers, user, db_client = get_auth_headers(client, session)
    
    # Create Quote
    create_payload = {
        "client_id": db_client.id,
        "items": [{"description": "Service", "quantity": 1, "unit_price": 100.0}]
    }
    resp = client.post("/api/quotes", json=create_payload, headers=headers)
    quote_id = resp.json()["id"]
    
    # Mark as Paid
    update_payload = {"is_paid": True, "status": QuoteStatus.SIGNED}
    resp = client.put(f"/api/quotes/{quote_id}", json=update_payload, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_paid"] is True
    
    # Attempt Modification (Should Fail)
    modify_payload = {"items": [{"description": "Hacked", "quantity": 1, "unit_price": 1.0}]}
    resp = client.put(f"/api/quotes/{quote_id}", json=modify_payload, headers=headers)
    assert resp.status_code == 403 # Forbidden
    assert "Cannot modify a paid invoice" in resp.json()["detail"]

def test_export_revenue(client: TestClient, session: Session):
    """Test CSV Export content."""
    headers, user, db_client = get_auth_headers(client, session)
    
    # Create 2 Paid Quotes
    for i in range(2):
        create_payload = {
            "client_id": db_client.id,
            "items": [{"description": "Service", "quantity": 1, "unit_price": 100.0}]
        }
        res = client.post("/api/quotes", json=create_payload, headers=headers)
        qid = res.json()["id"]
        # Mark paid
        client.put(f"/api/quotes/{qid}", json={"is_paid": True}, headers=headers)
        
    # Export
    response = client.get("/api/export/revenue", headers=headers)
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    
    content = response.text
    lines = content.strip().split("\n")
    assert len(lines) == 3 # Header + 2 rows
    assert "Date Encaissement" in lines[0]
    assert "Montant HT" in lines[0]
