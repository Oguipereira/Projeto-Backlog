from typing import List
from sqlalchemy.orm import Session

from app.models import ActivityLog


class ActivityService:
    def __init__(self, db: Session):
        self.db = db

    def log(self, email: str, name: str, action: str, details: str = ""):
        entry = ActivityLog(
            user_email=email,
            user_name=name,
            action=action,
            details=details,
        )
        self.db.add(entry)
        self.db.commit()

    def get_recent(self, limit: int = 500) -> List[ActivityLog]:
        return (
            self.db.query(ActivityLog)
            .order_by(ActivityLog.created_at.desc())
            .limit(limit)
            .all()
        )
