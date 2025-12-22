from sqlmodel import Session, create_engine
from api.core.config import settings

# Create engine with connection pooling optimized for serverless
engine = create_engine(
    settings.database_url,
    echo=settings.debug,  # Log SQL queries in debug mode
    pool_pre_ping=True,   # Verify connections before using
    pool_size=5,          # Small pool for serverless
    max_overflow=0,       # No overflow connections
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
