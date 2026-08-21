# backend/db/models/audit.py
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, generate_uuid, utc_now

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    acao: Mapped[str] = mapped_column(String(100), nullable=False)
    entidade_afetada: Mapped[str] = mapped_column(String(100), nullable=False)
    entidade_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    valor_anterior_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    valor_novo_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_origem: Mapped[str] = mapped_column(String(45), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    user: Mapped["User"] = relationship("User")
