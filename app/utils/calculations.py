from datetime import datetime
from typing import Optional


def calculate_duration_minutes(started_at: datetime, ended_at: Optional[datetime] = None) -> float:
    if ended_at is None:
        ended_at = datetime.utcnow()
    delta = ended_at - started_at
    return max(0.0, delta.total_seconds() / 60.0)


def calculate_production_loss(duration_minutes: float, production_per_minute: float) -> float:
    return round(duration_minutes * production_per_minute, 2)


def get_production_rates(daily_target: float, effective_hours: float) -> dict:
    effective_minutes = effective_hours * 60
    return {
        "per_day": daily_target,
        "per_hour": round(daily_target / effective_hours, 4),
        "per_minute": round(daily_target / effective_minutes, 6),
        "per_second": round(daily_target / (effective_minutes * 60), 8),
    }


def format_duration(minutes: float) -> str:
    if minutes < 1:
        return f"{int(minutes * 60)}s"
    if minutes < 60:
        return f"{int(minutes)}min"
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    if mins == 0:
        return f"{hours}h"
    return f"{hours}h {mins}min"


def format_number(value: float, decimals: int = 0) -> str:
    if decimals == 0:
        return f"{int(value):,}".replace(",", ".")
    formatted = f"{value:,.{decimals}f}"
    # Convert to Brazilian format: 1,234.56 -> 1.234,56
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")
