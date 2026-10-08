import logging
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

logger = logging.getLogger("fnad.db")
Base = declarative_base()


def _create_engine():
    db_url = settings.database_url
    # If explicit sqlite or postgres
    if db_url.startswith("sqlite"):
        return create_engine(db_url, connect_args={"check_same_thread": False})

    try:
        eng = create_engine(db_url, pool_pre_ping=True)
        # Test connection quickly
        with eng.connect():
            pass
        logger.info("Connected to PostgreSQL database: %s", db_url.split("@")[-1])
        return eng
    except Exception as exc:
        fallback_path = "./data/fnad.db"
        os.makedirs("./data", exist_ok=True)
        sqlite_url = f"sqlite:///{fallback_path}"
        logger.warning(
            "Could not connect to PostgreSQL at %s (%s). "
            "Falling back to local SQLite database at %s for local development.",
            db_url.split("@")[-1], exc, sqlite_url
        )
        return create_engine(sqlite_url, connect_args={"check_same_thread": False})


engine = _create_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
