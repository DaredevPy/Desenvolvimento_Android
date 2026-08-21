# backend/db/models/restriction.py
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, Text, CheckConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, generate_uuid, utc_now

class ProviderRestriction(Base):
    __tablename__ = "provider_restrictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("providers.id", ondelete="CASCADE"), nullable=False)
    admin_responsavel_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    motivo: Mapped[str] = mapped_column(Text, nullable=False)
    evidencias_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    data_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    prazo_fim: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="ATIVA", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    provider: Mapped["Provider"] = relationship("Provider", back_populates="restrictions")
    admin_responsavel: Mapped["User"] = relationship("User")

    __table_args__ = (
        CheckConstraint("status IN ('ATIVA', 'REVOGADA', 'EXPIRADA')", name="check_restriction_status"),
    )
