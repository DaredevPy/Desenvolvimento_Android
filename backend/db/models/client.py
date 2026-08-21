# backend/db/models/client.py
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, generate_uuid, utc_now

class Client(Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), unique=True, nullable=False)
    endereco_padrao_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    contrato_codigo: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    profile: Mapped["Profile"] = relationship("Profile", back_populates="client")
    collections: Mapped[List["Collection"]] = relationship("Collection", back_populates="client")
