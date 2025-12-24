from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str
    
    # Better Auth
    better_auth_secret: str
    
    # Vercel Blob
    blob_read_write_token: str | None = None
    
    # Environment
    environment: str = "development"
    debug: bool = False
    
    # CORS
    # Read as string first to avoid Pydantic trying to parse comma-separated list as JSON
    cors_origins_raw: str = Field(default="http://localhost:3000", validation_alias="CORS_ORIGINS")
    
    # Admin Credentials (Hardening)
    admin_email: str
    admin_username: str
    admin_name: str
    admin_password: str
    
    @property
    def cors_origins(self) -> list[str]:
        """Parse CORS origins from raw string (comma-separated or JSON)."""
        value = self.cors_origins_raw
        if not value:
            return []
        
        # Try JSON first
        if value.strip().startswith("["):
            import json
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
                
        # Fallback to comma-separated
        return [i.strip() for i in value.split(",")]
    
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
