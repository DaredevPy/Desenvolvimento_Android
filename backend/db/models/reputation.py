# backend/db/models/reputation.py
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, Numeric, Text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, generate_uuid, utc_now

class ProviderReputationEvent(Base):
    __tablename__ = "provider_reputation_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True)
    collection_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("collections.id", ondelete="SET NULL"), nullable=True)
    tipo_evento: Mapped[str] = mapped_column(String(50), nullable=False)
    pontos_impacto: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    descricao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    provider: Mapped["Provider"] = relationship("Provider", back_populates="reputation_events")
    collection: Mapped[Optional["Collection"]] = relationship("Collection")

    __table_args__ = (
        CheckConstraint("tipo_evento IN ('ACEITE_RAPIDO', 'CANCELAMENTO', 'PONTUALIDADE', 'AVALIACAO_CLIENTE', 'DIVERGENCIA_INJUSTIFICADA')", name="check_rep_evento"),
    )
