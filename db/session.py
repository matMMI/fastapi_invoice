from sqlmodel import Session, create_engine

from core.config import settings

# Optimized pool configuration for Neon PostgreSQL
# - pool_size: base connections per worker (increased for better concurrency)
# - max_overflow: additional connections under load
# - pool_recycle: reduced to 300s (Neon may close idle connections)
# - pool_pre_ping: validates connections before use (important for remote DB)
# - pool_timeout: max wait time to acquire a connection from pool
engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=300,
    pool_timeout=30,
    connect_args={"connect_timeout": 10, "options": "-c timezone=utc"},
)


def get_session():
    with Session(engine) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
