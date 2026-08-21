# backend/db/models/tire.py
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, Integer, Numeric, Boolean, Text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, generate_uuid, utc_now

class Tire(Base):
    __tablename__ = "tires"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    collection_id: Mapped[str] = mapped_column(String(36), ForeignKey("collections.id", ondelete="CASCADE"), nullable=False, index=True)
    numero_fogo: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    numero_fogo_ilegivel: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    numero_serie: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    dot: Mapped[str] = mapped_column(String(10), nullable=False, index=True) # ATENÇÃO: NENHUMA CONSTRAINT UNIQUE!
    semana_fabricacao: Mapped[int] = mapped_column(Integer, nullable=False)
    ano_fabricacao: Mapped[int] = mapped_column(Integer, nullable=False)
    idade_calculada_anos: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    alerta_idade_obsoleto: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    marca: Mapped[str] = mapped_column(String(100), nullable=False)
    medida: Mapped[str] = mapped_column(String(50), nullable=False)
    modelo: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    estado_conservacao: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    observacoes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    foto_pneu_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    collection: Mapped["Collection"] = relationship("Collection", back_populates="tires")

    __table_args__ = (
        CheckConstraint("length(dot) >= 3 AND length(dot) <= 10", name="check_tire_dot_length"),
        CheckConstraint("semana_fabricacao >= 1 AND semana_fabricacao <= 53", name="check_tire_semana"),
        CheckConstraint("ano_fabricacao >= 0 AND ano_fabricacao <= 99", name="check_tire_ano"),
        CheckConstraint("idade_calculada_anos >= 0", name="check_tire_idade"),
    )
