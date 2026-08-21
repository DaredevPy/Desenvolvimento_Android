# backend/db/models/user.py
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, generate_uuid, utc_now

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ATIVO")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    profile: Mapped[Optional["Profile"]] = relationship("Profile", back_populates="user", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("role IN ('CLIENTE', 'PRESTADOR', 'ADMINISTRADOR')", name="check_user_role"),
        CheckConstraint("status IN ('ATIVO', 'SUSPENSO', 'INATIVO')", name="check_user_status"),
    )
