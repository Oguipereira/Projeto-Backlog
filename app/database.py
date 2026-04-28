import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

def _sqlite_data_dir() -> Path:
    """Use /tmp on read-only filesystems (e.g. Streamlit Cloud)."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        test = DATA_DIR / ".write_test"
        test.touch()
        test.unlink()
        return DATA_DIR
    except Exception:
        tmp = Path("/tmp/incident_data")
        tmp.mkdir(parents=True, exist_ok=True)
        return tmp

_sqlite_url = f"sqlite:///{_sqlite_data_dir() / 'incidents.db'}"

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

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_is_sqlite = DATABASE_URL.startswith("sqlite")

connect_args = {"check_same_thread": False} if _is_sqlite else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db_session():
    return SessionLocal()


def init_db():
    from app.models import Base as _Base
    _Base.metadata.create_all(bind=engine)


# Cria tabelas automaticamente ao importar — garante que todas as páginas
# encontrem o schema pronto independente da ordem de carregamento.
init_db()
