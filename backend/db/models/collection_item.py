# backend/db/models/collection_item.py
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, Integer, Text, CheckConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, generate_uuid, utc_now

class CollectionItemDeclared(Base):
    __tablename__ = "collection_items_declared"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    collection_id: Mapped[str] = mapped_column(String(36), ForeignKey("collections.id", ondelete="CASCADE"), nullable=False)
    marca: Mapped[str] = mapped_column(String(100), nullable=False)
    dimensao: Mapped[str] = mapped_column(String(50), nullable=False)
    quantidade_declarada: Mapped[int] = mapped_column(Integer, nullable=False)
    observacao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    collection: Mapped["Collection"] = relationship("Collection", back_populates="items_declared")

    __table_args__ = (
        CheckConstraint("quantidade_declarada > 0", name="check_qtd_declarada_positive"),
    )

class CollectionItemChecked(Base):
    __tablename__ = "collection_items_checked"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    collection_id: Mapped[str] = mapped_column(String(36), ForeignKey("collections.id", ondelete="CASCADE"), nullable=False)
    quantidade_conferida: Mapped[int] = mapped_column(Integer, nullable=False)
    quantidade_coletada: Mapped[int] = mapped_column(Integer, nullable=False)
    justificativa_divergencia: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fotos_divergencia_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    collection: Mapped["Collection"] = relationship("Collection", back_populates="items_checked")

    __table_args__ = (
        CheckConstraint("quantidade_conferida >= 0", name="check_qtd_conferida_ge_zero"),
        CheckConstraint("quantidade_coletada >= 0", name="check_qtd_coletada_ge_zero"),
    )
