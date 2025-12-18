from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from typing import Generator
from sqlalchemy.orm import Session
from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,   # checks stale connections
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def test_db_connection() -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()