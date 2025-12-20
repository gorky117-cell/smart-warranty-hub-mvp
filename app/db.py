import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DB_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{Path(__file__).resolve().parents[1] / 'data' / 'app.db'}",
)
connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}


class Base(DeclarativeBase):
    pass


engine = create_engine(DB_URL, echo=False, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
