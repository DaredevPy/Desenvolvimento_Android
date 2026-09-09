# backend/db/models/idempotency.py
# Registro de operações offline idempotentes (doc 09 §4.1; Missão 13).
# Um registro por chave: replay devolve response_json; corrida decidida
# pelo UNIQUE(chave) no banco.
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, generate_uuid, utc_now


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    chave: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    escopo: Mapped[str] = mapped_column(String(20), nullable=False)
    recurso_id: Mapped[str] = mapped_column(String(36), ForeignKey("collections.id", ondelete="RESTRICT"), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "escopo IN ('PNEUS', 'CONCLUSAO', 'FINALIZACAO', 'CANCELACAO')",
            name="check_idem_escopo",
        ),
    )
