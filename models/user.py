from sqlmodel import SQLModel, Field
from uuid import uuid4
from datetime import datetime, timezone

class User(SQLModel, table=True):
    """User account for authentication and quote ownership."""
    
    __tablename__ = "user"  # type: ignore
    
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)
    username: str | None = Field(default=None, unique=True, index=True, max_length=255)
    password_hash: str | None = Field(default=None, max_length=255) # Optional for OAuth users
    name: str = Field(max_length=255)
    business_name: str | None = Field(default=None, max_length=255)
    logo_url: str | None = Field(default=None, max_length=500)
    image: str | None = Field(default=None, max_length=500)
    email_verified: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
