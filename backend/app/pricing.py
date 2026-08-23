# backend/app/pricing.py
# Fundação financeira: price_rules (ADMIN) + fechamento financeiro com snapshot
# imutável (docs 03 §4, 06 §5, 07 §§1-3, 10 §§2-3).
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from backend.db import session as db_session
from backend.db.models import (
    AuditLog,
    Collection,
    FinancialTransaction,
    IdempotencyRecord,
    PriceRule,
    Tire,
    User,
)

from .collections import (
    NAO_ENCONTRADO,
    _chave_idempotencia,
    _coleta_do_provider,
    _hash_operacao,
    _provider_do_usuario,
    _verificar_chave_registro,
)
from .rbac import require_roles

router = APIRouter(prefix="/api/v1", tags=["pricing"])

CENTAVO = Decimal("0.01")


class RegraPrecoCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    perfil_alvo: Literal["CLIENTE", "PRESTADOR"]
    faixa_inicio_quantidade: int = Field(ge=0)
    faixa_fim_quantidade: int = Field(ge=0)
    valor_unitario: Decimal = Field(ge=0, decimal_places=2, max_digits=10)
    vigencia_inicio: date
    vigencia_fim: Optional[date] = None
    justificativa: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validar_faixas(self):
        if self.faixa_fim_quantidade < self.faixa_inicio_quantidade:
            raise ValueError("faixa_fim_quantidade deve ser >= faixa_inicio_quantidade.")
        if self.vigencia_fim is not None and self.vigencia_fim < self.vigencia_inicio:
            raise ValueError("vigencia_fim deve ser >= vigencia_inicio.")
        return self


class RegraPrecoUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valor_unitario: Optional[Decimal] = Field(
        default=None, ge=0, decimal_places=2, max_digits=10
    )
    faixa_inicio_quantidade: Optional[int] = Field(default=None, ge=0)
    faixa_fim_quantidade: Optional[int] = Field(default=None, ge=0)
    vigencia_fim: Optional[date] = None
    ativo: Optional[bool] = None
    justificativa: str = Field(min_length=1, max_length=2000)


class FinalizacaoRequest(BaseModel):
    # Corpo vazio por exigência de segurança: nenhum valor financeiro é aceito
    # do cliente (docs 07 §1 e AGENTS.md §3).
    model_config = ConfigDict(extra="forbid")


def _validar_sobreposicao(
    db,
    perfil_alvo: str,
    inicio_qtd: int,
    fim_qtd: int,
    vigencia_inicio: date,
    vigencia_fim: Optional[date],
    excluir_id: Optional[str] = None,
) -> None:
    # Ambiguidade de cálculo existe apenas entre regras selecionáveis (ativas);
    # histórico desativado nunca bloqueia novas faixas.
    consulta = select(PriceRule).where(
        PriceRule.perfil_alvo == perfil_alvo,
        PriceRule.ativo.is_(True),
        PriceRule.faixa_inicio_quantidade <= fim_qtd,
        PriceRule.faixa_fim_quantidade >= inicio_qtd,
    )
    if excluir_id is not None:
        consulta = consulta.where(PriceRule.id != excluir_id)
    limite_nova = vigencia_fim or date.max
    for regra in db.scalars(consulta).all():
        if regra.vigencia_inicio <= limite_nova and (regra.vigencia_fim or date.max) >= vigencia_inicio:
            raise HTTPException(
                status_code=409,
                detail=f"Faixa conflita com regra ativa existente para {perfil_alvo}.",
            )


def _snapshot_regra(regra: PriceRule, justificativa: Optional[str]) -> dict:
    return {
        "perfil_alvo": regra.perfil_alvo,
        "faixa_inicio_quantidade": regra.faixa_inicio_quantidade,
        "faixa_fim_quantidade": regra.faixa_fim_quantidade,
        "valor_unitario": str(regra.valor_unitario),
        "vigencia_inicio": regra.vigencia_inicio.isoformat(),
        "vigencia_fim": regra.vigencia_fim.isoformat() if regra.vigencia_fim else None,
        "ativo": regra.ativo,
        "justificativa": justificativa,
    }


def _log_auditoria(
    usuario: User, request: Request, acao: str, regra_id: str, anterior: Optional[dict], novo: dict
) -> AuditLog:
    return AuditLog(
        user_id=usuario.id,
        acao=acao,
        entidade_afetada="price_rules",
        entidade_id=regra_id,
        valor_anterior_json=anterior,
        valor_novo_json=novo,
        ip_origem=request.client.host if request.client else "desconhecida",
    )


@router.post("/admin/pricing-rules", status_code=201)
def criar_regra_preco(
    dados: RegraPrecoCreateRequest,
    request: Request,
    usuario: User = Depends(require_roles("ADMINISTRADOR")),
) -> dict:
    with db_session.SessionLocal() as db:
        _validar_sobreposicao(
            db,
            dados.perfil_alvo,
            dados.faixa_inicio_quantidade,
            dados.faixa_fim_quantidade,
            dados.vigencia_inicio,
            dados.vigencia_fim,
        )
        regra = PriceRule(
            perfil_alvo=dados.perfil_alvo,
            faixa_inicio_quantidade=dados.faixa_inicio_quantidade,
            faixa_fim_quantidade=dados.faixa_fim_quantidade,
            valor_unitario=dados.valor_unitario,
            vigencia_inicio=dados.vigencia_inicio,
            vigencia_fim=dados.vigencia_fim,
            criado_por_admin_id=usuario.id,
        )
        db.add(regra)
        db.flush()
        db.add(
            _log_auditoria(
                usuario, request, "CRIACAO_REGRA_PRECO", regra.id, None,
                _snapshot_regra(regra, dados.justificativa),
            )
        )
        db.commit()
        return _snapshot_regra(regra, dados.justificativa) | {"id": regra.id}


@router.patch("/admin/pricing-rules/{regra_id}")
def alterar_regra_preco(
    regra_id: str,
    dados: RegraPrecoUpdateRequest,
    request: Request,
    usuario: User = Depends(require_roles("ADMINISTRADOR")),
) -> dict:
    with db_session.SessionLocal() as db:
        regra = db.get(PriceRule, regra_id)
        if regra is None:
            raise HTTPException(status_code=404, detail=NAO_ENCONTRADO)

        anterior = _snapshot_regra(regra, None)
        informados = dados.model_fields_set

        if "valor_unitario" in informados:
            regra.valor_unitario = dados.valor_unitario
        if "faixa_inicio_quantidade" in informados:
            regra.faixa_inicio_quantidade = dados.faixa_inicio_quantidade
        if "faixa_fim_quantidade" in informados:
            regra.faixa_fim_quantidade = dados.faixa_fim_quantidade
        if "vigencia_fim" in informados:
            regra.vigencia_fim = dados.vigencia_fim
        if "ativo" in informados:
            regra.ativo = dados.ativo

        if regra.faixa_fim_quantidade < regra.faixa_inicio_quantidade:
            raise HTTPException(status_code=422, detail="Faixa de quantidade inválida.")
        if regra.vigencia_fim is not None and regra.vigencia_fim < regra.vigencia_inicio:
            raise HTTPException(status_code=422, detail="Vigência inválida.")

        alterou_escopo = bool(informados & {"faixa_inicio_quantidade", "faixa_fim_quantidade", "vigencia_fim"})
        if alterou_escopo and regra.ativo:
            _validar_sobreposicao(
                db,
                regra.perfil_alvo,
                regra.faixa_inicio_quantidade,
                regra.faixa_fim_quantidade,
                regra.vigencia_inicio,
                regra.vigencia_fim,
                excluir_id=regra.id,
            )

        db.flush()
        db.add(_log_auditoria(usuario, request, "ALTERACAO_REGRA_PRECO", regra.id, anterior,
                              _snapshot_regra(regra, dados.justificativa)))
        db.commit()
        return _snapshot_regra(regra, dados.justificativa) | {"id": regra.id}


def _regra_aplicavel(db, perfil_alvo: str, quantidade: int, referencia: date) -> Optional[PriceRule]:
    return db.scalars(
        select(PriceRule)
        .where(
            PriceRule.perfil_alvo == perfil_alvo,
            PriceRule.ativo.is_(True),
            PriceRule.faixa_inicio_quantidade <= quantidade,
            PriceRule.faixa_fim_quantidade >= quantidade,
            PriceRule.vigencia_inicio <= referencia,
            or_(PriceRule.vigencia_fim.is_(None), PriceRule.vigencia_fim >= referencia),
        )
        .order_by(PriceRule.created_at.desc())
    ).first()


def _calcular_valor(quantidade: int, valor_unitario) -> Decimal:
    return (Decimal(quantidade) * Decimal(str(valor_unitario))).quantize(CENTAVO, rounding=ROUND_HALF_UP)


@router.post("/collections/{coleta_id}/finalizar")
def finalizar_coleta(
    coleta_id: str,
    _dados: FinalizacaoRequest,
    usuario: User = Depends(require_roles("PRESTADOR")),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    with db_session.SessionLocal() as db:
        provider = _provider_do_usuario(db, usuario.id)
        if provider is None:
            raise HTTPException(status_code=404, detail="Perfil não encontrado.")
        # FOR UPDATE: fechamento concorrente é serializado na própria coleta.
        coleta = _coleta_do_provider(db, coleta_id, provider.id, bloquear=True)
        chave = _chave_idempotencia(x_idempotency_key)
        hash_operacao = _hash_operacao(_dados) if chave is not None else None
        if chave is not None:
            # Repetição da MESMA finalização é replay, não novo fechamento.
            armazenada = _verificar_chave_registro(
                db, chave, usuario.id, "FINALIZACAO", coleta_id, hash_operacao
            )
            if armazenada is not None:
                return JSONResponse(status_code=200, content=armazenada)
        if coleta.status != "CARREGADA":
            raise HTTPException(status_code=409, detail="Finalização exige coleta no estado CARREGADA.")

        quantidade = db.scalar(
            select(func.count()).select_from(Tire).where(Tire.collection_id == coleta_id)
        )
        hoje = date.today()
        regra_cliente = _regra_aplicavel(db, "CLIENTE", quantidade, hoje)
        regra_prestador = _regra_aplicavel(db, "PRESTADOR", quantidade, hoje)
        if regra_cliente is None or regra_prestador is None:
            faltante = "CLIENTE" if regra_cliente is None else "PRESTADOR"
            raise HTTPException(
                status_code=409,
                detail=f"Regra de preço aplicável não encontrada para {faltante}.",
            )

        valor_cliente = _calcular_valor(quantidade, regra_cliente.valor_unitario)
        valor_prestador = _calcular_valor(quantidade, regra_prestador.valor_unitario)

        # Snapshot imutável + lançamentos + transição de estado: uma única
        # transação (doc 07 §3); trava FOR UPDATE impede fechamento duplicado.
        coleta.snapshot_valor_cliente = valor_cliente
        coleta.snapshot_valor_prestador = valor_prestador
        coleta.status = "FINALIZADA"
        coleta.data_finalizacao = datetime.now(timezone.utc)
        lancamentos = [
            FinancialTransaction(
                collection_id=coleta_id,
                tipo_entidade="CLIENTE",
                perfil_id=coleta.client.profile_id,
                valor_total=valor_cliente,
                data_vencimento=hoje,
            ),
            FinancialTransaction(
                collection_id=coleta_id,
                tipo_entidade="PRESTADOR",
                perfil_id=provider.profile_id,
                valor_total=valor_prestador,
                data_vencimento=hoje,
            ),
        ]
        db.add_all(lancamentos)
        db.flush()
        corpo = {
            "id": coleta.id,
            "status": coleta.status,
            "quantidade_coletada": quantidade,
            "snapshot_valor_cliente": float(valor_cliente),
            "snapshot_valor_prestador": float(valor_prestador),
            "transacoes": [
                {"id": l.id, "tipo_entidade": l.tipo_entidade, "valor_total": float(l.valor_total)}
                for l in lancamentos
            ],
        }
        try:
            if chave is not None:
                # Registro da chave na MESMA transação do fechamento: falha
                # no meio => nada persistido e chave disponível para retry.
                db.add(
                    IdempotencyRecord(
                        chave=chave,
                        user_id=usuario.id,
                        escopo="FINALIZACAO",
                        recurso_id=coleta_id,
                        request_hash=hash_operacao,
                        response_json=corpo,
                    )
                )
            db.commit()
        except IntegrityError:
            db.rollback()
            if chave is None:
                raise
            armazenada = _verificar_chave_registro(
                db, chave, usuario.id, "FINALIZACAO", coleta_id, hash_operacao
            )
            if armazenada is None:
                raise
            return JSONResponse(status_code=200, content=armazenada)
        return corpo
