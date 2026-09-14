"""SQLAlchemy engine/session, shared by the ingestion pipeline and the API."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session():
    """FastAPI dependency / context-manager-friendly session factory."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
