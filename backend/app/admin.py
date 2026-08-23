# backend/app/admin.py
# Fundação da Dashboard Administrativa (doc 10): consultas operacionais
# somente leitura + listagens de price_rules e audit_logs. Nenhum endpoint
# aqui altera coletas, snapshots ou lançamentos financeiros.
from datetime import date, datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from backend.db import session as db_session
from backend.db.models import AuditLog, Client, Collection, PriceRule, Profile, Provider

from .collections import NAO_ENCONTRADO
from .rbac import require_roles

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _paginar(db, consulta, page: int, por_pagina: int):
    total = db.scalar(select(func.count()).select_from(consulta.subquery()))
    itens = (
        db.scalars(consulta.offset((page - 1) * por_pagina).limit(por_pagina)).all()
    )
    return total, itens


@router.get("/pricing-rules")
def listar_regras_preco(
    perfil_alvo: Optional[Literal["CLIENTE", "PRESTADOR"]] = None,
    ativo: Optional[bool] = None,
    page: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=20, ge=1, le=100),
    usuario=Depends(require_roles("ADMINISTRADOR")),
) -> dict:
    with db_session.SessionLocal() as db:
        consulta = select(PriceRule)
        if perfil_alvo is not None:
            consulta = consulta.where(PriceRule.perfil_alvo == perfil_alvo)
        if ativo is not None:
            consulta = consulta.where(PriceRule.ativo.is_(ativo))
        total, regras = _paginar(
            db, consulta.order_by(PriceRule.created_at.desc()), page, por_pagina
        )
        return {
            "pagina": page,
            "por_pagina": por_pagina,
            "total": total,
            "itens": [
                {
                    "id": r.id,
                    "perfil_alvo": r.perfil_alvo,
                    "faixa_inicio_quantidade": r.faixa_inicio_quantidade,
                    "faixa_fim_quantidade": r.faixa_fim_quantidade,
                    "valor_unitario": float(r.valor_unitario),
                    "vigencia_inicio": r.vigencia_inicio.isoformat(),
                    "vigencia_fim": r.vigencia_fim.isoformat() if r.vigencia_fim else None,
                    "ativo": r.ativo,
                    "criado_por_admin_id": r.criado_por_admin_id,
                    "criado_em": r.created_at.isoformat(),
                }
                for r in regras
            ],
        }


@router.get("/audit-logs")
def listar_auditoria(
    entidade_afetada: Optional[str] = None,
    acao: Optional[str] = None,
    user_id: Optional[str] = None,
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None,
    page: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=20, ge=1, le=100),
    usuario=Depends(require_roles("ADMINISTRADOR")),
) -> dict:
    # Trilha é somente leitura: nenhuma rota de escrita existe para audit_logs.
    with db_session.SessionLocal() as db:
        consulta = select(AuditLog)
        if entidade_afetada is not None:
            consulta = consulta.where(AuditLog.entidade_afetada == entidade_afetada)
        if acao is not None:
            consulta = consulta.where(AuditLog.acao == acao)
        if user_id is not None:
            consulta = consulta.where(AuditLog.user_id == user_id)
        if data_inicio is not None:
            consulta = consulta.where(
                AuditLog.created_at
                >= datetime.combine(data_inicio, datetime.min.time(), tzinfo=timezone.utc)
            )
        if data_fim is not None:
            limite = datetime.combine(
                data_fim + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc
            )
            consulta = consulta.where(AuditLog.created_at < limite)
        total, logs = _paginar(
            db, consulta.order_by(AuditLog.created_at.desc()), page, por_pagina
        )
        return {
            "pagina": page,
            "por_pagina": por_pagina,
            "total": total,
            "itens": [
                {
                    "id": log.id,
                    "user_id": log.user_id,
                    "acao": log.acao,
                    "entidade_afetada": log.entidade_afetada,
                    "entidade_id": log.entidade_id,
                    "valor_anterior_json": log.valor_anterior_json,
                    "valor_novo_json": log.valor_novo_json,
                    "ip_origem": log.ip_origem,
                    "criado_em": log.created_at.isoformat(),
                }
                for log in logs
            ],
        }


def _carregar_coleta(db, coleta_id: str) -> Collection:
    consulta = (
        select(Collection)
        .options(
            selectinload(Collection.client).selectinload(Client.profile).selectinload(Profile.user),
            selectinload(Collection.provider).selectinload(Provider.profile).selectinload(Profile.user),
            selectinload(Collection.items_declared),
            selectinload(Collection.items_checked),
            selectinload(Collection.tires),
            selectinload(Collection.financial_transactions),
        )
        .where(Collection.id == coleta_id)
    )
    coleta = db.scalars(consulta).first()
    if coleta is None:
        raise HTTPException(status_code=404, detail=NAO_ENCONTRADO)
    return coleta


def _email(coleta: Collection, lado: str) -> Optional[str]:
    parte = coleta.client if lado == "cliente" else coleta.provider
    if parte is None or parte.profile is None or parte.profile.user is None:
        return None
    return parte.profile.user.email


def _resumo(coleta: Collection) -> dict:
    declarada = sum(item.quantidade_declarada for item in coleta.items_declared)
    conferencia = coleta.items_checked[-1] if coleta.items_checked else None
    return {
        "id": coleta.id,
        "codigo_identificador": coleta.codigo_identificador,
        "status": coleta.status,
        "cliente_id": coleta.client_id,
        "cliente_email": _email(coleta, "cliente"),
        "prestador_id": coleta.provider_id,
        "prestador_email": _email(coleta, "prestador"),
        "data_agendada": coleta.data_agendada.isoformat(),
        "data_finalizacao": (
            coleta.data_finalizacao.isoformat() if coleta.data_finalizacao else None
        ),
        "criado_em": coleta.created_at.isoformat(),
        "quantidade_declarada": declarada,
        "quantidade_conferida": conferencia.quantidade_conferida if conferencia else None,
        "quantidade_coletada": conferencia.quantidade_coletada if conferencia else None,
        "snapshot_valor_cliente": (
            float(coleta.snapshot_valor_cliente) if coleta.snapshot_valor_cliente is not None else None
        ),
        "snapshot_valor_prestador": (
            float(coleta.snapshot_valor_prestador) if coleta.snapshot_valor_prestador is not None else None
        ),
    }


@router.get("/collections")
def listar_coletas(
    status: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=20, ge=1, le=100),
    usuario=Depends(require_roles("ADMINISTRADOR")),
) -> dict:
    # Visão administrativa atravessa ownership de terceiros (permissão explícita
    # do doc 10); o helper de ownership dos usuários comuns permanece intacto.
    with db_session.SessionLocal() as db:
        consulta = (
            select(Collection)
            .options(
                selectinload(Collection.items_declared),
                selectinload(Collection.items_checked),
                selectinload(Collection.client).selectinload(Client.profile),
                selectinload(Collection.provider).selectinload(Provider.profile),
            )
        )
        if status is not None:
            consulta = consulta.where(Collection.status == status)
        total, coletas = _paginar(
            db, consulta.order_by(Collection.created_at.desc()), page, por_pagina
        )
        return {
            "pagina": page,
            "por_pagina": por_pagina,
            "total": total,
            "itens": [_resumo(c) for c in coletas],
        }


@router.get("/collections/{coleta_id}")
def detalhar_coleta(
    coleta_id: str,
    usuario=Depends(require_roles("ADMINISTRADOR")),
) -> dict:
    with db_session.SessionLocal() as db:
        coleta = _carregar_coleta(db, coleta_id)
        resposta = _resumo(coleta)
        resposta.update(
            {
                "endereco_origem_json": coleta.endereco_origem_json,
                "itens_declarados": [
                    {
                        "marca": item.marca,
                        "dimensao": item.dimensao,
                        "quantidade_declarada": item.quantidade_declarada,
                        "observacao": item.observacao,
                    }
                    for item in coleta.items_declared
                ],
                "conferencia": [
                    {
                        "quantidade_conferida": item.quantidade_conferida,
                        "quantidade_coletada": item.quantidade_coletada,
                        "justificativa_divergencia": item.justificativa_divergencia,
                        "fotos_divergencia_json": item.fotos_divergencia_json,
                    }
                    for item in coleta.items_checked
                ],
                "pneus": [
                    {
                        "id": pneu.id,
                        "dot": pneu.dot,
                        "semana_fabricacao": pneu.semana_fabricacao,
                        "ano_fabricacao": pneu.ano_fabricacao,
                        "idade_calculada_anos": float(pneu.idade_calculada_anos),
                        "alerta_idade_obsoleto": pneu.alerta_idade_obsoleto,
                        "numero_fogo": pneu.numero_fogo,
                        "numero_fogo_ilegivel": pneu.numero_fogo_ilegivel,
                        "marca": pneu.marca,
                        "medida": pneu.medida,
                    }
                    for pneu in coleta.tires
                ],
                "lancamentos_financeiros": [
                    {
                        "id": lancamento.id,
                        "tipo_entidade": lancamento.tipo_entidade,
                        "perfil_id": lancamento.perfil_id,
                        "valor_total": float(lancamento.valor_total),
                        "status_pagamento": lancamento.status_pagamento,
                        "data_vencimento": lancamento.data_vencimento.isoformat(),
                        "data_pagamento": (
                            lancamento.data_pagamento.isoformat()
                            if lancamento.data_pagamento
                            else None
                        ),
                    }
                    for lancamento in coleta.financial_transactions
                ],
            }
        )
        return resposta
