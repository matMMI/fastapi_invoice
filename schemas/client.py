"""Pydantic schemas for Client API endpoints."""

from pydantic import BaseModel, EmailStr, Field
from datetime import datetime


class ClientCreate(BaseModel):
    """Schema for creating a new client."""
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr = Field(..., max_length=255)
    company: str | None = Field(None, max_length=255)
    address: str | None = None
    phone: str | None = Field(None, max_length=50)
    vat_number: str | None = Field(None, max_length=50)


class ClientUpdate(BaseModel):
    """Schema for updating an existing client."""
    name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = Field(None, max_length=255)
    company: str | None = Field(None, max_length=255)
    address: str | None = None
    phone: str | None = Field(None, max_length=50)
    vat_number: str | None = Field(None, max_length=50)


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
