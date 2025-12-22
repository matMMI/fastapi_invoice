
"""Pydantic schemas for Client API endpoints."""

from pydantic import BaseModel, Field
from datetime import datetime


class ClientBase(BaseModel):
    """Base schema for client data."""
    name: str = Field(..., max_length=100)
    email: str = Field(..., max_length=255, pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    phone: str | None = Field(None, max_length=50)
    address: str | None = Field(None)
    city: str | None = Field(None, max_length=100)
    postal_code: str | None = Field(None, max_length=20)
    country: str | None = Field(None, max_length=100)
    vat_number: str | None = Field(None, max_length=50)
    notes: str | None = Field(None)


class ClientCreate(ClientBase):
    """Schema for creating a new client."""
    # Inherits fields from ClientBase
    pass


class ClientUpdate(BaseModel):
    """Schema for updating an existing client."""
    name: str | None = Field(None, max_length=100)
    email: str | None = Field(None, max_length=255, pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    phone: str | None = Field(None, max_length=50)
    address: str | None = Field(None)
    city: str | None = Field(None, max_length=100)
    postal_code: str | None = Field(None, max_length=20)
    country: str | None = Field(None, max_length=100)
    vat_number: str | None = Field(None, max_length=50)
    notes: str | None = Field(None)


class ClientResponse(BaseModel):
    """Schema for client API responses."""
    id: str
    user_id: str
    name: str
    email: str
    company: str | None
    address: str | None
    phone: str | None
    vat_number: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ClientListResponse(BaseModel):
    """Schema for paginated client list responses."""
    clients: list[ClientResponse]
    total: int
