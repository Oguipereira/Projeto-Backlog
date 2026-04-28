import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import engine, DATABASE_URL
from app.models import Base


def init_db():
    Base.metadata.create_all(bind=engine)
    print(f"Banco inicializado: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")


if __name__ == "__main__":
    init_db()
