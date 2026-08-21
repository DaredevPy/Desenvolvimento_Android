# backend/db/models/price_rule.py
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, DateTime, Date, ForeignKey, Numeric, Integer, Boolean, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, generate_uuid, utc_now

class PriceRule(Base):
    __tablename__ = "price_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    perfil_alvo: Mapped[str] = mapped_column(String(20), nullable=False) # 'CLIENTE' ou 'PRESTADOR'
    faixa_inicio_quantidade: Mapped[int] = mapped_column(Integer, nullable=False)
    faixa_fim_quantidade: Mapped[int] = mapped_column(Integer, nullable=False)
    valor_unitario: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    vigencia_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    vigencia_fim: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    criado_por_admin_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    criado_por: Mapped["User"] = relationship("User")

    __table_args__ = (
        CheckConstraint("perfil_alvo IN ('CLIENTE', 'PRESTADOR')", name="check_price_perfil"),
        CheckConstraint("faixa_inicio_quantidade >= 0", name="check_price_faixa_inicio"),
        CheckConstraint("faixa_fim_quantidade >= faixa_inicio_quantidade", name="check_price_faixa_fim"),
        CheckConstraint("valor_unitario >= 0", name="check_price_valor"),
    )
