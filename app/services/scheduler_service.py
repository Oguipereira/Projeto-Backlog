"""
Agendador de envio automático de relatório por e-mail.

Usa APScheduler com BackgroundScheduler — singleton de módulo que
persiste entre reruns do Streamlit dentro do mesmo processo.

Limitação conhecida: o agendador para se o Streamlit Cloud colocar
o app em modo sleep por inatividade. Mantenha o app ativo ou use
o botão "Enviar agora" para envios pontuais.
"""
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

_scheduler: Optional[BackgroundScheduler] = None
_last_sent: Optional[datetime] = None
_last_status: str = ""

_DAY_LABELS = {
    "mon": "Segunda-feira",
    "tue": "Terça-feira",
    "wed": "Quarta-feira",
    "thu": "Quinta-feira",
    "fri": "Sexta-feira",
    "sat": "Sábado",
    "sun": "Domingo",
}


def _get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None or not _scheduler.running:
        _scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
        _scheduler.start()
    return _scheduler


def _make_job_fn():
    """
    Cria a função do job isolada do contexto Streamlit.
    Lê configurações do settings.json em tempo de execução.
    """
    def _job():
        global _last_sent, _last_status
        try:
            import json
            from pathlib import Path
            from app.database import get_db_session
            from app.services.incident_service import IncidentService
            from app.services.config_service import ConfigService
            from app.services.report_service import build_report
            from app.services.email_service import send_email

            db = get_db_session()
            try:
                svc       = IncidentService(db)
                cfg_svc   = ConfigService(db)
                all_incs  = svc.get_all()
                open_incs = svc.get_all({"status": ["Aberto", "Em Andamento"]})
                rates     = cfg_svc.get_production_rates()
                email_cfg = cfg_svc.get_email_config()
            finally:
                db.close()

            report = build_report(all_incs, open_incs, rates)
            result = send_email(
                smtp_host = email_cfg.get("smtp_host", "smtp.gmail.com"),
                smtp_port = int(email_cfg.get("smtp_port", 587)),
                username  = email_cfg.get("username", ""),
                password  = email_cfg.get("password", ""),
                from_addr = email_cfg.get("from_addr", ""),
                to_addrs  = email_cfg.get("to_addrs", []),
                report    = report,
            )

            _last_sent   = datetime.now()
            _last_status = "ok" if result["status"] == "ok" else result.get("message", "erro")

            # Persiste last_sent no settings.json
            db2 = get_db_session()
            try:
                ConfigService(db2).save_schedule({
                    "last_sent":   _last_sent.strftime("%d/%m/%Y %H:%M"),
                    "last_status": _last_status,
                })
            finally:
                db2.close()

        except Exception as e:
            _last_sent   = datetime.now()
            _last_status = f"erro: {e}"

    return _job


def activate(frequency: str, day_of_week: str, hour: int, minute: int):
    """
    Ativa o job de envio automático com o cronograma especificado.

    frequency: "daily" | "weekly"
    day_of_week: "mon" | "tue" | ... (usado apenas se frequency == "weekly")
    """
    sched = _get_scheduler()

    if frequency == "daily":
        trigger = CronTrigger(hour=hour, minute=minute, timezone="America/Sao_Paulo")
    else:
        trigger = CronTrigger(
            day_of_week=day_of_week,
            hour=hour,
            minute=minute,
            timezone="America/Sao_Paulo",
        )

    sched.add_job(
        _make_job_fn(),
        trigger=trigger,
        id="email_report",
        name="Relatório Executivo",
        replace_existing=True,
    )


def deactivate():
    sched = _get_scheduler()
    if sched.get_job("email_report"):
        sched.remove_job("email_report")


def is_active() -> bool:
    try:
        return _get_scheduler().get_job("email_report") is not None
    except Exception:
        return False


def next_run() -> Optional[datetime]:
    try:
        job = _get_scheduler().get_job("email_report")
        return job.next_run_time if job else None
    except Exception:
        return None


def last_run() -> tuple:
    """Retorna (datetime | None, status_str)."""
    return _last_sent, _last_status


def day_label(day_key: str) -> str:
    return _DAY_LABELS.get(day_key, day_key)
