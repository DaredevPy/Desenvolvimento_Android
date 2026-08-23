# backend/db/models/collection.py
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, DateTime, ForeignKey, Numeric, CheckConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, generate_uuid, utc_now

class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    codigo_identificador: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False, index=True)
    provider_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("providers.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="RASCUNHO", nullable=False, index=True)
    endereco_origem_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    data_agendada: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_finalizacao: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    snapshot_valor_prestador: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    snapshot_valor_cliente: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(36), unique=True, nullable=True, index=True)
    idempotency_request_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    idempotency_response_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    client: Mapped["Client"] = relationship("Client", back_populates="collections")
    provider: Mapped[Optional["Provider"]] = relationship("Provider", back_populates="collections")
    items_declared: Mapped[List["CollectionItemDeclared"]] = relationship("CollectionItemDeclared", back_populates="collection", cascade="all, delete-orphan")
    items_checked: Mapped[List["CollectionItemChecked"]] = relationship("CollectionItemChecked", back_populates="collection", cascade="all, delete-orphan")
    tires: Mapped[List["Tire"]] = relationship("Tire", back_populates="collection", cascade="all, delete-orphan")
    financial_transactions: Mapped[List["FinancialTransaction"]] = relationship("FinancialTransaction", back_populates="collection")

    __table_args__ = (
        CheckConstraint("status IN ('RASCUNHO', 'SOLICITADA', 'ACEITA', 'EM_DESLOCAMENTO', 'EM_CONFERENCIA', 'CARREGADA', 'FINALIZADA', 'CONTESTADA', 'CANCELADA')", name="check_collection_status"),
        CheckConstraint("snapshot_valor_prestador IS NULL OR snapshot_valor_prestador >= 0", name="check_snapshot_prestador"),
        CheckConstraint("snapshot_valor_cliente IS NULL OR snapshot_valor_cliente >= 0", name="check_snapshot_cliente"),
    )
