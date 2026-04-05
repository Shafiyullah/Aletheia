import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Use absolute path to ensure DB is stored in the project root reliably
# Default to SQLite for local development, overwritten by Docker ENV
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./aletheia_production.db")

# For SQLite, we require check_same_thread=False for FastAPI concurrency
# But for PostgreSQL, we don't.
engine_args = {}
if "sqlite" in DATABASE_URL:
    engine_args["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_args)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """FastAPI Dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
