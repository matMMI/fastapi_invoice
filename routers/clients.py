"""API routes for client management."""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlmodel import Session, select, func, or_
from core.rate_limit import limiter
from db.session import get_session
from core.security import get_current_user
from models.user import User
from models.client import Client
from schemas.client import ClientCreate, ClientUpdate, ClientResponse, ClientListResponse
from datetime import datetime, timezone
router = APIRouter()


@router.post("/clients", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_client(
    request: Request,
    client_data: ClientCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Create a new client for the current user."""
    client = Client(
        **client_data.model_dump(),
        user_id=current_user.id
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("/clients", response_model=ClientListResponse)
async def list_clients(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    search: str | None = Query(default=None, description="Search by name or email"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """List all clients for the current user with optional search and pagination."""
    # Base query for filtering
    query = select(Client).where(Client.user_id == current_user.id)
    
    if search:
        safe_search = search.replace("%", "\\%").replace("_", "\\_")
        search_filter = f"%{safe_search}%"
        query = query.where(
            or_(
                Client.name.ilike(search_filter, escape="\\"),
                Client.email.ilike(search_filter, escape="\\")
            )
        )
    
    # Get total count first
    count_query = select(func.count()).select_from(query.subquery())
    total = db.exec(count_query).one()
    
    # Apply pagination
    offset = (page - 1) * limit
    clients = db.exec(query.offset(offset).limit(limit)).all()
    
    return ClientListResponse(clients=clients, total=total)


@router.get("/clients/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Get a specific client by ID."""
    client = db.get(Client, client_id)
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Check ownership
    if client.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    return client


@router.put("/clients/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: str,
    client_data: ClientUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Update a client."""
    client = db.get(Client, client_id)
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Check ownership
    if client.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Update only allowed fields (prevent mass assignment)
    ALLOWED_UPDATE_FIELDS = {"name", "email", "company", "phone", "address", "city", "postal_code", "country", "vat_number", "notes"}
    update_data = client_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key in ALLOWED_UPDATE_FIELDS:
            setattr(client, key, value)
    
    client.updated_at = datetime.now(timezone.utc)
    db.add(client)
    db.commit()
    db.refresh(client)
    
    return client


@router.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Delete a client."""
    client = db.get(Client, client_id)
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Check ownership
    if client.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    db.delete(client)
    db.commit()
