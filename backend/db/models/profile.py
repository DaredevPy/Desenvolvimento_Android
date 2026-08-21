# backend/db/models/profile.py
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, generate_uuid, utc_now

class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    nome_razao_social: Mapped[str] = mapped_column(String(255), nullable=False)
    cpf_cnpj: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    telefone: Mapped[str] = mapped_column(String(20), nullable=False)
    chave_pix: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="profile")
    client: Mapped[Optional["Client"]] = relationship("Client", back_populates="profile", uselist=False, cascade="all, delete-orphan")
    provider: Mapped[Optional["Provider"]] = relationship("Provider", back_populates="profile", uselist=False, cascade="all, delete-orphan")
