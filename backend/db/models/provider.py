# backend/db/models/provider.py
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, DateTime, ForeignKey, Numeric, CheckConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, generate_uuid, utc_now

class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), unique=True, nullable=False)
    reputacao_score: Mapped[float] = mapped_column(Numeric(5, 2), default=5.00, nullable=False)
    taxa_resposta: Mapped[float] = mapped_column(Numeric(5, 2), default=100.00, nullable=False)
    status_operacional: Mapped[str] = mapped_column(String(50), default="DISPONIVEL", nullable=False)
    dados_veiculo_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    profile: Mapped["Profile"] = relationship("Profile", back_populates="provider")
    collections: Mapped[List["Collection"]] = relationship("Collection", back_populates="provider")
    reputation_events: Mapped[List["ProviderReputationEvent"]] = relationship("ProviderReputationEvent", back_populates="provider", cascade="all, delete-orphan")
    restrictions: Mapped[List["ProviderRestriction"]] = relationship("ProviderRestriction", back_populates="provider", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("reputacao_score >= 0.00 AND reputacao_score <= 5.00", name="check_provider_score"),
        CheckConstraint("taxa_resposta >= 0.00 AND taxa_resposta <= 100.00", name="check_provider_taxa"),
        CheckConstraint("status_operacional IN ('DISPONIVEL', 'EM_COLETA', 'RESTITO', 'INDISPONIVEL')", name="check_provider_status"),
    )
