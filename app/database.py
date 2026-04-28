import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Ordem de prioridade para DATABASE_URL:
# 1. Streamlit secrets (produção no Streamlit Cloud)
# 2. Variável de ambiente (Railway, Docker, etc.)
# 3. SQLite local (desenvolvimento)
_sqlite_url = f"sqlite:///{DATA_DIR / 'incidents.db'}"

def _get_database_url() -> str:
    try:
        import streamlit as st
        url = st.secrets.get("DATABASE_URL", "")
        if url:
            return url
    except Exception:
        pass
    return os.environ.get("DATABASE_URL", _sqlite_url)

DATABASE_URL = _get_database_url()

# Supabase retorna URLs com "postgres://", SQLAlchemy exige "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_is_sqlite = DATABASE_URL.startswith("sqlite")
if _is_sqlite:
    DATA_DIR.mkdir(exist_ok=True)

connect_args = {"check_same_thread": False} if _is_sqlite else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db_session():
    return SessionLocal()


def init_db():
    from app.models import Base as _Base
    _Base.metadata.create_all(bind=engine)
