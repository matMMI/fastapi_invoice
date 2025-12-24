from sqlmodel import Session, create_engine
from core.config import settings
engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    connect_args={
        "connect_timeout": 10,
        "options": "-c timezone=utc"
    }
)
def get_session():

    with Session(engine) as session:
        yield session
