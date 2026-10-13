from typing import Generator
import urllib.parse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings

# Engine setup
# pool_pre_ping=True checks connection health before handing it out, preventing stale socket errors
engine = create_engine(
    settings.get_database_url(),
    connect_args=settings.get_database_connect_args(),
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a transactional database session per request.
    Automatically closes the session when the request lifecycle ends.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_connection() -> bool:
    """Safely verifies database connectivity by executing a lightweight ping."""
    success, _ = check_database_connection()
    return success


def check_database_connection() -> tuple[bool, str]:
    """
    Safely tests database connectivity.
    Returns (True, message) on success, or (False, sanitized_error) on failure.
    Never exposes plain passwords in error messages or logs.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "Successfully connected to MySQL server and database."
    except Exception as exc:
        err_msg = str(exc)
        if settings.DB_PASSWORD and settings.DB_PASSWORD in err_msg:
            err_msg = err_msg.replace(settings.DB_PASSWORD, "********")
        if settings.DATABASE_URL:
            parsed = urllib.parse.urlsplit(settings.DATABASE_URL)
            if parsed.password and parsed.password in err_msg:
                err_msg = err_msg.replace(parsed.password, "********")
        return False, err_msg
