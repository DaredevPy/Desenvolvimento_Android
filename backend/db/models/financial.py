# backend/db/models/financial.py
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, DateTime, Date, ForeignKey, Numeric, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, generate_uuid, utc_now

class FinancialTransaction(Base):
    __tablename__ = "financial_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    collection_id: Mapped[str] = mapped_column(String(36), ForeignKey("collections.id", ondelete="RESTRICT"), nullable=False, index=True)
    tipo_entidade: Mapped[str] = mapped_column(String(20), nullable=False) # 'CLIENTE' ou 'PRESTADOR'
    perfil_id: Mapped[str] = mapped_column(String(36), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False, index=True)
    valor_total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status_pagamento: Mapped[str] = mapped_column(String(50), default="PENDENTE", nullable=False)
    data_vencimento: Mapped[date] = mapped_column(Date, nullable=False)
    data_pagamento: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    collection: Mapped["Collection"] = relationship("Collection", back_populates="financial_transactions")
    profile: Mapped["Profile"] = relationship("Profile")

    __table_args__ = (
        CheckConstraint("tipo_entidade IN ('CLIENTE', 'PRESTADOR')", name="check_fin_tipo"),
        CheckConstraint("valor_total >= 0", name="check_fin_valor"),
        CheckConstraint("status_pagamento IN ('PENDENTE', 'PAGO', 'CANCELADO')", name="check_fin_status"),
    )
