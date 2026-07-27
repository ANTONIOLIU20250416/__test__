from datetime import date, timedelta
from typing import Optional

from sqlmodel import Session

from .models import AuditLog, EnvCertStatus

EXPIRING_SOON_WINDOW_DAYS = 60


def log_action(session: Session, entity_type: str, entity_id: int, action: str,
                details: Optional[dict] = None, actor: str = "system") -> None:
    session.add(AuditLog(entity_type=entity_type, entity_id=entity_id, action=action,
                          details=details or {}, actor=actor))
    session.commit()


def env_cert_status(expiry_date) -> str:
    if expiry_date is None:
        return EnvCertStatus.VALID
    today = date.today()
    if expiry_date < today:
        return EnvCertStatus.EXPIRED
    if expiry_date <= today + timedelta(days=EXPIRING_SOON_WINDOW_DAYS):
        return EnvCertStatus.EXPIRING_SOON
    return EnvCertStatus.VALID
