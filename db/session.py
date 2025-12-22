from sqlmodel import Session, create_engine
from core.config import settings

# Create engine with connection pooling optimized for serverless
# Each Lambda instance gets its own engine, so we use minimal pooling
engine = create_engine(
    settings.database_url,
    echo=settings.debug,           # Log SQL queries in debug mode
    pool_pre_ping=True,            # Verify connections before using
    pool_size=1,                   # Minimal pool for serverless
    max_overflow=0,                # No overflow connections
    pool_recycle=3600,             # Recycle connections after 1 hour
    connect_args={
        "connect_timeout": 10,     # Connection timeout in seconds
        "options": "-c timezone=utc"  # Set timezone to UTC
    }
)


def get_session():
    """
    Dependency to get database session.
    
    Usage:
        @router.get("/items")
        def get_items(session: Session = Depends(get_session)):
            ...
    """
    with Session(engine) as session:
        yield session
