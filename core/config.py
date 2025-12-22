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
    cors_origins: list[str] = ["http://localhost:3000"]
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
