# backend/app/collections.py
import hashlib
import re
import uuid as uuid_lib
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.db import session as db_session
from backend.db.models import (
    AuditLog,
    Client,
    Collection,
    CollectionItemChecked,
    CollectionItemDeclared,
    IdempotencyRecord,
    Profile,
    Provider,
    Tire,
    User,
)

from .rbac import require_roles
from .validacao import exigir_json_compacto

router = APIRouter(prefix="/api/v1/collections", tags=["collections"])

NAO_ENCONTRADO = "Recurso não encontrado."

# Padrão documentado (docs 03/06). Configuração pelo Administrador = missão futura.
LIMITE_ALERTA_IDADE_ANOS = 7.0

# Limites de volume por requisição (doc 08 §4.1). Coletas reais citadas nos
# docs ficam na casa de centenas de pneus; os tetos dão folga e rejeitam
# payloads capazes de exaurir memória/CPU.
MAX_ITENS_DECLARADOS = 200
MAX_PNEUS_POR_LOTE = 2000
MAX_QUANTIDADE = 1_000_000

_DOT_FORMATO = re.compile(r"^\d{4}$")

TRANSICOES_VALIDAS = {
    "RASCUNHO": {"SOLICITADA"},
    "SOLICITADA": {"ACEITA", "CANCELADA"},
    "ACEITA": {"EM_DESLOCAMENTO", "CANCELADA"},
    "EM_DESLOCAMENTO": {"EM_CONFERENCIA"},
    "EM_CONFERENCIA": {"CARREGADA"},
    "CARREGADA": {"FINALIZADA"},
    "FINALIZADA": {"CONTESTADA"},
    "CONTESTADA": set(),
}


class ItemDeclaradoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marca: str = Field(min_length=1, max_length=100)
    dimensao: str = Field(min_length=1, max_length=50)
    quantidade_declarada: int = Field(gt=0, le=MAX_QUANTIDADE)
    observacao: Optional[str] = Field(default=None, max_length=1000)


class ColetaCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endereco_origem_json: dict = Field(min_length=1)
    data_agendada: datetime
    itens: list[ItemDeclaradoRequest] = Field(min_length=1, max_length=MAX_ITENS_DECLARADOS)

    @field_validator("endereco_origem_json")
    @classmethod
    def limitar_endereco(cls, value: dict) -> dict:
        return exigir_json_compacto("endereco_origem_json", value)

    @field_validator("data_agendada")
    @classmethod
    def exigir_fuso_horario(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("data_agendada deve informar fuso horário (ISO 8601 com offset).")
        return value


class AvancoStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    novo_status: Literal["EM_DESLOCAMENTO", "EM_CONFERENCIA", "CARREGADA"]


class PneuConferidoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marca: str = Field(min_length=1, max_length=100)
    medida: str = Field(min_length=1, max_length=50)
    dot: str
    numero_fogo: Optional[str] = Field(default=None, max_length=50)
    numero_fogo_ilegivel: bool = False
    numero_serie: Optional[str] = Field(default=None, max_length=50)
    modelo: Optional[str] = Field(default=None, max_length=100)
    estado_conservacao: Optional[str] = Field(default=None, max_length=50)
    observacoes: Optional[str] = Field(default=None, max_length=2000)
    foto_pneu_url: Optional[str] = Field(default=None, max_length=500)

    @field_validator("dot")
    @classmethod
    def validar_dot(cls, value: str) -> str:
        if not _DOT_FORMATO.fullmatch(value):
            raise ValueError("DOT deve ter 4 dígitos no formato WWYY.")
        if not 1 <= int(value[:2]) <= 53:
            raise ValueError("Semana de fabricação deve estar entre 01 e 53.")
        return value


class RegistroPneusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pneus: list[PneuConferidoRequest] = Field(min_length=1, max_length=MAX_PNEUS_POR_LOTE)


class ConclusaoConferenciaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantidade_conferida: int = Field(ge=0, le=MAX_QUANTIDADE)
    quantidade_coletada: int = Field(ge=0, le=MAX_QUANTIDADE)
    justificativa_divergencia: Optional[str] = Field(default=None, max_length=2000)
    fotos_divergencia_json: Optional[dict] = None

    @field_validator("fotos_divergencia_json")
    @classmethod
    def limitar_fotos(cls, value: Optional[dict]) -> Optional[dict]:
        return exigir_json_compacto("fotos_divergencia_json", value) if value is not None else None


class ContestacaoRequest(BaseModel):
    # Docs 03 §2.1 / 05 §1 não definem payload para a contestação do cliente;
    # prazo, motivo e evidências permanecem decisão pendente (STATUS §8).
    model_config = ConfigDict(extra="forbid")


def _stmt_aceite(coleta_id: str, provider_id: str):
    # UPDATE condicional: atômico no banco; garante um único vencedor na corrida.
    return (
        update(Collection)
        .where(
            Collection.id == coleta_id,
            Collection.status == "SOLICITADA",
            Collection.provider_id.is_(None),
        )
        .values(provider_id=provider_id, status="ACEITA")
    )


def _stmt_avanco(coleta_id: str, status_atual: str, novo_status: str):
    return (
        update(Collection)
        .where(Collection.id == coleta_id, Collection.status == status_atual)
        .values(status=novo_status)
    )


def _calcular_idade_anos(dot: str) -> float:
    # Implementação provisória em anos completos (doc 06 §8 mantém a fórmula
    # decimal exata como decisão pendente); centralizada aqui para troca futura.
    semana = int(dot[:2])
    yy = int(dot[2:])
    hoje = datetime.now(timezone.utc)
    ano_fabricacao = 2000 + yy
    if ano_fabricacao > hoje.year:
        ano_fabricacao = 1900 + yy
    idade = float(hoje.year - ano_fabricacao)
    if hoje.isocalendar().week < semana:
        idade -= 1.0
    if idade < 0:
        raise ValueError("DOT com data de fabricação no futuro.")
    return idade


def _coleta_do_provider(db, coleta_id: str, provider_id: str, bloquear: bool = False) -> Collection:
    consulta = select(Collection).where(Collection.id == coleta_id)
    if bloquear:
        # Serializa operações de escrita concorrentes na mesma coleta (PostgreSQL).
        consulta = consulta.with_for_update()
    coleta = db.scalars(consulta).first()
    # 404 uniforme: inexistente e atribuído a outro prestador são indistinguíveis.
    if coleta is None or coleta.provider_id != provider_id:
        raise HTTPException(status_code=404, detail=NAO_ENCONTRADO)
    return coleta


def _client_do_usuario(db, user_id: str) -> Optional[Client]:
    return db.scalars(
        select(Client).join(Profile, Client.profile_id == Profile.id).where(Profile.user_id == user_id)
    ).first()


def _provider_do_usuario(db, user_id: str) -> Optional[Provider]:
    return db.scalars(
        select(Provider).join(Profile, Provider.profile_id == Profile.id).where(Profile.user_id == user_id)
    ).first()


def _chave_idempotencia(valor: Optional[str]) -> Optional[str]:
    # Docs 09 §4.1 / AGENTS §5.4: chave UUIDv4 gerada pelo app no cabeçalho
    # X-Idempotency-Key. Opcional até o outbox do Flutter existir.
    if valor is None:
        return None
    try:
        chave = uuid_lib.UUID(valor)
    except ValueError:
        raise HTTPException(status_code=422, detail="X-Idempotency-Key deve ser um UUID válido.") from None
    if chave.version != 4:
        raise HTTPException(status_code=422, detail="X-Idempotency-Key deve ser um UUIDv4.")
    return str(chave)


def _hash_operacao(dados) -> str:
    # Aceita qualquer schema Pydantic v2 (criação, pneus, conclusão, finalização).
    return hashlib.sha256(dados.model_dump_json().encode()).hexdigest()


def _replay_idempotente(db, chave: str, client_id: str, hash_operacao: str) -> Optional[dict]:
    """Retorna a resposta armazenada quando a chave é reuso legítimo da
    MESMA operação; rejeita reuso por outro usuário (404 uniforme) ou com
    conteúdo diferente (409)."""
    existente = db.scalars(
        select(Collection).where(Collection.idempotency_key == chave)
    ).first()
    if existente is None:
        return None
    if existente.client_id != client_id:
        # Chave alheia é indistinguível de chave inexistente (anti-enumeração).
        raise HTTPException(status_code=404, detail=NAO_ENCONTRADO)
    if existente.idempotency_request_hash != hash_operacao:
        raise HTTPException(
            status_code=409,
            detail="Chave de idempotência já utilizada para uma operação diferente.",
        )
    return existente.idempotency_response_json


def _verificar_chave_registro(
    db, chave: str, usuario_id: str, escopo: str, coleta_id: str, hash_operacao: str
):
    """Replay para operações registradas em idempotency_records (doc 09 §2:
    pneus, conclusão e finalização). Mesmo contrato de _replay_idempotente."""
    registro = db.scalars(
        select(IdempotencyRecord).where(IdempotencyRecord.chave == chave)
    ).first()
    if registro is None:
        return None
    if registro.user_id != usuario_id:
        # Chave alheia é indistinguível de chave inexistente (anti-enumeração).
        raise HTTPException(status_code=404, detail=NAO_ENCONTRADO)
    if (
        registro.escopo != escopo
        or registro.recurso_id != coleta_id
        or registro.request_hash != hash_operacao
    ):
        raise HTTPException(
            status_code=409,
            detail="Chave de idempotência já utilizada para uma operação diferente.",
        )
    return registro.response_json


def _resposta(coleta: Collection) -> dict:
    return {
        "id": coleta.id,
        "codigo_identificador": coleta.codigo_identificador,
        "status": coleta.status,
        "endereco_origem_json": coleta.endereco_origem_json,
        "data_agendada": coleta.data_agendada.isoformat(),
        "provider_id": coleta.provider_id,
        "criado_em": coleta.created_at.isoformat(),
        "itens": [
            {
                "marca": item.marca,
                "dimensao": item.dimensao,
                "quantidade_declarada": item.quantidade_declarada,
                "observacao": item.observacao,
            }
            for item in coleta.items_declared
        ],
    }


@router.post("", status_code=201)
def criar_coleta(
    dados: ColetaCreateRequest,
    usuario: User = Depends(require_roles("CLIENTE")),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    with db_session.SessionLocal() as db:
        client = _client_do_usuario(db, usuario.id)
        if client is None:
            raise HTTPException(status_code=404, detail="Perfil não encontrado.")
        chave = _chave_idempotencia(x_idempotency_key)
        hash_operacao = _hash_operacao(dados) if chave is not None else None
        if chave is not None:
            # Doc 09 §4.1: chave já processada NÃO re-executa a operação;
            # devolve exatamente a resposta armazenada com HTTP 200.
            armazenada = _replay_idempotente(db, chave, client.id, hash_operacao)
            if armazenada is not None:
                return JSONResponse(status_code=200, content=armazenada)
        coleta = Collection(
            codigo_identificador=f"COL-{uuid_lib.uuid4().hex[:16].upper()}",
            client_id=client.id,
            status="SOLICITADA",
            endereco_origem_json=dados.endereco_origem_json,
            data_agendada=dados.data_agendada,
            idempotency_key=chave,
            idempotency_request_hash=hash_operacao,
        )
        coleta.items_declared = [
            CollectionItemDeclared(**item.model_dump()) for item in dados.itens
        ]
        db.add(coleta)
        try:
            # Flush e commit dentro do try: o UNIQUE pode estourar no INSERT
            # (flush), não apenas no commit — o fallback de replay cobre ambos.
            db.flush()
            corpo = _resposta(coleta)
            coleta.idempotency_response_json = corpo if chave is not None else None
            db.commit()
        except IntegrityError:
            # Corrida de dois requests simultâneos com a mesma chave: o UNIQUE
            # (uq_collections_idempotency) decide no banco quem venceu.
            db.rollback()
            if chave is None:
                raise
            armazenada = _replay_idempotente(db, chave, client.id, hash_operacao)
            if armazenada is None:
                raise
            return JSONResponse(status_code=200, content=armazenada)
        if chave is not None:
            return JSONResponse(status_code=201, content=corpo)
        return corpo


@router.get("")
def listar_minhas_coletas(usuario: User = Depends(require_roles("CLIENTE", "PRESTADOR"))) -> list[dict]:
    with db_session.SessionLocal() as db:
        consulta = select(Collection).options(selectinload(Collection.items_declared))
        if usuario.role == "CLIENTE":
            client = _client_do_usuario(db, usuario.id)
            if client is None:
                raise HTTPException(status_code=404, detail="Perfil não encontrado.")
            consulta = consulta.where(Collection.client_id == client.id)
        else:
            provider = _provider_do_usuario(db, usuario.id)
            if provider is None:
                raise HTTPException(status_code=404, detail="Perfil não encontrado.")
            consulta = consulta.where(Collection.provider_id == provider.id)
        coletas = db.scalars(consulta.order_by(Collection.created_at.desc())).all()
        return [_resposta(coleta) for coleta in coletas]


@router.get("/disponiveis")
def listar_disponiveis(usuario: User = Depends(require_roles("PRESTADOR"))) -> list[dict]:
    with db_session.SessionLocal() as db:
        coletas = db.scalars(
            select(Collection)
            .options(selectinload(Collection.items_declared))
            .where(Collection.status == "SOLICITADA", Collection.provider_id.is_(None))
            .order_by(Collection.created_at.asc())
        ).all()
        return [_resposta(coleta) for coleta in coletas]


@router.get("/{coleta_id}")
def obter_coleta(
    coleta_id: str,
    usuario: User = Depends(require_roles("CLIENTE")),
) -> dict:
    with db_session.SessionLocal() as db:
        client = _client_do_usuario(db, usuario.id)
        if client is None:
            raise HTTPException(status_code=404, detail="Perfil não encontrado.")
        coleta = db.get(Collection, coleta_id)
        # 404 uniforme: inexistente e alheio são indistinguíveis (anti-enumeração).
        if coleta is None or coleta.client_id != client.id:
            raise HTTPException(status_code=404, detail=NAO_ENCONTRADO)
        return _resposta(coleta)


@router.post("/{coleta_id}/aceitar")
def aceitar_coleta(
    coleta_id: str,
    usuario: User = Depends(require_roles("PRESTADOR")),
) -> dict:
    with db_session.SessionLocal() as db:
        provider = _provider_do_usuario(db, usuario.id)
        if provider is None:
            raise HTTPException(status_code=404, detail="Perfil não encontrado.")
        if db.scalars(select(Collection.id).where(Collection.id == coleta_id)).first() is None:
            raise HTTPException(status_code=404, detail=NAO_ENCONTRADO)
        resultado = db.execute(_stmt_aceite(coleta_id, provider.id))
        if resultado.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="Coleta não está mais disponível para aceite.")
        db.commit()
        coleta = db.get(Collection, coleta_id)
        return {"id": coleta.id, "status": coleta.status, "provider_id": coleta.provider_id}


@router.post("/{coleta_id}/cancelar")
def cancelar_coleta(
    coleta_id: str,
    request: Request,
    usuario: User = Depends(require_roles("CLIENTE", "PRESTADOR", "ADMINISTRADOR")),
    justificativa: Optional[str] = Header(default=None, alias="X-Justificativa"),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
) -> dict:
    """Cancela uma coleta conforme a matriz de perfis (doc 04 §2) e a máquina
    de estados (doc 05 §1):

    - CLIENTE: SOLICITADA -> CANCELADA na própria coleta (sem chave).
    - PRESTADOR responsável / ADMINISTRADOR: ACEITA -> CANCELADA com
      justificativa (X-Justificativa) e idempotência obrigatória
      (X-Idempotency-Key UUIDv4).

    O replay da MESMA chave devolve a resposta armazenada sem re-executar a
    operação nem duplicar a auditoria (docs 09 §§4.1 e 08 §3.1). Chave alheia
    é indistinguível de chave inexistente (404 uniforme)."""
    with db_session.SessionLocal() as db:
        # FOR UPDATE serializa cancelamentos concorrentes da mesma coleta.
        coleta = db.get(Collection, coleta_id, with_for_update=True)
        if coleta is None:
            raise HTTPException(status_code=404, detail=NAO_ENCONTRADO)

        chave = None
        hash_operacao = None

        if usuario.role == "CLIENTE":
            client = _client_do_usuario(db, usuario.id)
            if client is None:
                raise HTTPException(status_code=404, detail="Perfil não encontrado.")
            # Anti-enumeração (padrão da API): alheia e inexistente são iguais.
            if coleta.client_id != client.id:
                raise HTTPException(status_code=404, detail=NAO_ENCONTRADO)
            if coleta.status != "SOLICITADA":
                raise HTTPException(
                    status_code=409,
                    detail=f"Transição inválida a partir de {coleta.status}.",
                )
        else:
            # PRESTADOR responsável ou ADMINISTRADOR: apenas ACEITA -> CANCELADA.
            if usuario.role == "PRESTADOR":
                provider = _provider_do_usuario(db, usuario.id)
                if provider is None:
                    raise HTTPException(status_code=404, detail="Perfil não encontrado.")
                # Anti-enumeração: coleta alheia e inexistente são iguais.
                if coleta.provider_id != provider.id:
                    raise HTTPException(status_code=404, detail=NAO_ENCONTRADO)
            if justificativa is None or justificativa.strip() == "":
                raise HTTPException(
                    status_code=422,
                    detail="Justificativa é obrigatória para cancelamento após ACEITA.",
                )
            if x_idempotency_key is None:
                raise HTTPException(
                    status_code=422,
                    detail="X-Idempotency-Key é obrigatória para cancelamento após ACEITA.",
                )
            chave = _chave_idempotencia(x_idempotency_key)
            # Hash da operação idempotente: mesma chave + mesma justificativa.
            hash_operacao = hashlib.sha256(
                f"{coleta_id}:CANCELADA:{justificativa}".encode()
            ).hexdigest()
            # Replay: mesma chave + mesma operação devolvem a resposta
            # armazenada (mesmo com a coleta já CANCELADA); chave alheia e
            # operação divergente seguem o contrato das demais operações
            # (404 uniforme / 409).
            armazenada = _verificar_chave_registro(
                db, chave, usuario.id, "CANCELACAO", coleta_id, hash_operacao
            )
            if armazenada is not None:
                return JSONResponse(status_code=200, content=armazenada)
            if coleta.status != "ACEITA":
                raise HTTPException(
                    status_code=409,
                    detail=f"Cancelamento permitido apenas para coleta em estado ACEITA. Estado atual: {coleta.status}.",
                )

        corpo_resposta = {
            "id": coleta_id,
            "status": "CANCELADA",
            "justificativa": justificativa or "",
        }
        ip_origem = request.client.host if request.client else "desconhecida"
        db.add(
            AuditLog(
                user_id=usuario.id,
                acao="CANCELACAO_COLETA",
                entidade_afetada="collections",
                entidade_id=coleta_id,
                valor_anterior_json={"status": coleta.status},
                valor_novo_json={"status": "CANCELADA", "justificativa": justificativa or ""},
                ip_origem=ip_origem,
            )
        )
        if chave is not None:
            db.add(
                IdempotencyRecord(
                    chave=chave,
                    user_id=usuario.id,
                    escopo="CANCELACAO",
                    recurso_id=coleta_id,
                    request_hash=hash_operacao,
                    response_json=corpo_resposta,
                )
            )

        # Alterar estado da coleta (apenas o status; dados permanecem intactos:
        # pneus, itens, prestador, históricos e financeiros). Não gera snapshot
        # financeiro nem transação (coleta não finalizada por conclusão).
        coleta.status = "CANCELADA"

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if chave is None:
                raise
            # Corrida de duas requisições com a mesma chave: o UNIQUE(chave)
            # decide no banco quem venceu; o perdedor reexecuta o replay.
            armazenada = _verificar_chave_registro(
                db, chave, usuario.id, "CANCELACAO", coleta_id, hash_operacao
            )
            if armazenada is None:
                raise
            return JSONResponse(status_code=200, content=armazenada)
        return corpo_resposta
@router.post("/{coleta_id}/status")
def avancar_status(
    coleta_id: str,
    dados: AvancoStatusRequest,
    usuario: User = Depends(require_roles("PRESTADOR")),
) -> dict:
    with db_session.SessionLocal() as db:
        provider = _provider_do_usuario(db, usuario.id)
        if provider is None:
            raise HTTPException(status_code=404, detail="Perfil não encontrado.")
        coleta = db.get(Collection, coleta_id)
        if coleta is None or coleta.provider_id != provider.id:
            raise HTTPException(status_code=404, detail=NAO_ENCONTRADO)
        if dados.novo_status not in TRANSICOES_VALIDAS[coleta.status]:
            raise HTTPException(
                status_code=409,
                detail=f"Transição inválida a partir de {coleta.status}.",
            )
        resultado = db.execute(_stmt_avanco(coleta_id, coleta.status, dados.novo_status))
        if resultado.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail=f"Transição inválida a partir de {coleta.status}.")
        db.commit()
        return {"id": coleta_id, "status": dados.novo_status}


# --- Conferência e registro individual dos pneus (doc 05 Etapa 4) ---


@router.post("/{coleta_id}/conferencia/iniciar")
def iniciar_conferencia(
    coleta_id: str,
    usuario: User = Depends(require_roles("PRESTADOR")),
) -> dict:
    with db_session.SessionLocal() as db:
        provider = _provider_do_usuario(db, usuario.id)
        if provider is None:
            raise HTTPException(status_code=404, detail="Perfil não encontrado.")
        _coleta_do_provider(db, coleta_id, provider.id)
        # Doc 05: a conferência inicia com a chegada ao local (EM_DESLOCAMENTO -> EM_CONFERENCIA).
        resultado = db.execute(_stmt_avanco(coleta_id, "EM_DESLOCAMENTO", "EM_CONFERENCIA"))
        if resultado.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="Transição inválida a partir do estado atual.")
        db.commit()
        coleta = db.get(Collection, coleta_id)
        itens = db.scalars(
            select(CollectionItemDeclared)
            .where(CollectionItemDeclared.collection_id == coleta_id)
            .order_by(CollectionItemDeclared.created_at.asc())
        ).all()
        return {
            "id": coleta.id,
            "status": coleta.status,
            "itens_declarados": [
                {
                    "marca": item.marca,
                    "dimensao": item.dimensao,
                    "quantidade_declarada": item.quantidade_declarada,
                    "observacao": item.observacao,
                }
                for item in itens
            ],
        }


def _registrar_pneus(db, coleta_id: str, pneus: list[PneuConferidoRequest]) -> list[Tire]:
    idades = []
    for pneu in pneus:
        try:
            idades.append(_calcular_idade_anos(pneu.dot))
        except ValueError as erro:
            raise HTTPException(status_code=422, detail=str(erro)) from None
        if pneu.numero_fogo_ilegivel:
            # Doc 06 §4.1: ilegível exige foto comprovatória e observação descritiva.
            if not pneu.foto_pneu_url or not pneu.observacoes:
                raise HTTPException(
                    status_code=422,
                    detail="Número de fogo ilegível exige foto e observação descritiva.",
                )
            if pneu.numero_fogo:
                raise HTTPException(
                    status_code=422,
                    detail="Não informar numero_fogo quando marcado como ilegível.",
                )
    numeros_fogo = [p.numero_fogo for p in pneus if p.numero_fogo]
    if len(numeros_fogo) != len(set(numeros_fogo)):
        raise HTTPException(status_code=409, detail="Número de fogo duplicado na mesma coleta.")
    if numeros_fogo:
        existentes = db.scalars(
            select(Tire.numero_fogo).where(
                Tire.collection_id == coleta_id, Tire.numero_fogo.in_(numeros_fogo)
            )
        ).all()
        if existentes:
            raise HTTPException(status_code=409, detail="Número de fogo duplicado na mesma coleta.")

    registrados = []
    for pneu, idade in zip(pneus, idades):
        registrados.append(
            Tire(
                collection_id=coleta_id,
                dot=pneu.dot,
                semana_fabricacao=int(pneu.dot[:2]),
                ano_fabricacao=int(pneu.dot[2:]),
                idade_calculada_anos=idade,
                alerta_idade_obsoleto=idade >= LIMITE_ALERTA_IDADE_ANOS,
                numero_fogo=pneu.numero_fogo,
                numero_fogo_ilegivel=pneu.numero_fogo_ilegivel,
                numero_serie=pneu.numero_serie,
                marca=pneu.marca,
                medida=pneu.medida,
                modelo=pneu.modelo,
                estado_conservacao=pneu.estado_conservacao,
                observacoes=pneu.observacoes,
                foto_pneu_url=pneu.foto_pneu_url,
            )
        )
    db.add_all(registrados)
    # IDs são gerados no INSERT: flush garante ids reais no corpo da resposta
    # e na resposta armazenada para replay.
    db.flush()
    return registrados


@router.post("/{coleta_id}/conferencia/pneus", status_code=201)
def registrar_pneus(
    coleta_id: str,
    dados: RegistroPneusRequest,
    usuario: User = Depends(require_roles("PRESTADOR")),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    with db_session.SessionLocal() as db:
        provider = _provider_do_usuario(db, usuario.id)
        if provider is None:
            raise HTTPException(status_code=404, detail="Perfil não encontrado.")
        # FOR UPDATE serializa requests concorrentes na MESMA coleta;
        # corrida entre chaves iguais é decidida por uq_idem_chave.
        coleta = _coleta_do_provider(db, coleta_id, provider.id, bloquear=True)
        chave = _chave_idempotencia(x_idempotency_key)
        hash_operacao = _hash_operacao(dados) if chave is not None else None
        if chave is not None:
            # Doc 09 §4.1: replay devolve exatamente a resposta armazenada.
            armazenada = _verificar_chave_registro(
                db, chave, usuario.id, "PNEUS", coleta_id, hash_operacao
            )
            if armazenada is not None:
                return JSONResponse(status_code=200, content=armazenada)
        if coleta.status != "EM_CONFERENCIA":
            raise HTTPException(status_code=409, detail="Conferência não está aberta para esta coleta.")
        try:
            # O guard cobre o flush dos pneus além do commit: em corrida pela
            # MESMA chave, o perdedor pode violar uq_tires_collection_numero_fogo
            # no flush antes de o vencedor registrar a chave (SQLite ignora
            # FOR UPDATE); o contrato documentado é resolver a corrida por
            # uq_idem_chave (replay). Em PostgreSQL o FOR UPDATE serializa e
            # este caminho é inacessível.
            registrados = _registrar_pneus(db, coleta_id, dados.pneus)
            corpo = [
                {
                    "id": pneu.id,
                    "dot": pneu.dot,
                    "numero_fogo": pneu.numero_fogo,
                    "numero_fogo_ilegivel": pneu.numero_fogo_ilegivel,
                    "idade_calculada_anos": float(pneu.idade_calculada_anos),
                    "alerta_idade_obsoleto": pneu.alerta_idade_obsoleto,
                }
                for pneu in registrados
            ]
            if chave is not None:
                db.add(
                    IdempotencyRecord(
                        chave=chave,
                        user_id=usuario.id,
                        escopo="PNEUS",
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
                db, chave, usuario.id, "PNEUS", coleta_id, hash_operacao
            )
            if armazenada is None:
                raise
            return JSONResponse(status_code=200, content=armazenada)
        if chave is not None:
            return JSONResponse(status_code=201, content=corpo)
        return corpo


@router.get("/{coleta_id}/conferencia/pneus")
def listar_pneus_conferencia(
    coleta_id: str,
    usuario: User = Depends(require_roles("PRESTADOR")),
) -> list[dict]:
    with db_session.SessionLocal() as db:
        provider = _provider_do_usuario(db, usuario.id)
        if provider is None:
            raise HTTPException(status_code=404, detail="Perfil não encontrado.")
        _coleta_do_provider(db, coleta_id, provider.id)
        pneus = db.scalars(select(Tire).where(Tire.collection_id == coleta_id)).all()
        return [
            {
                "id": pneu.id,
                "dot": pneu.dot,
                "numero_fogo": pneu.numero_fogo,
                "numero_fogo_ilegivel": pneu.numero_fogo_ilegivel,
                "idade_calculada_anos": float(pneu.idade_calculada_anos),
                "alerta_idade_obsoleto": pneu.alerta_idade_obsoleto,
                "marca": pneu.marca,
                "medida": pneu.medida,
            }
            for pneu in pneus
        ]


@router.post("/{coleta_id}/conferencia/concluir")
def concluir_conferencia(
    coleta_id: str,
    dados: ConclusaoConferenciaRequest,
    usuario: User = Depends(require_roles("PRESTADOR")),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    with db_session.SessionLocal() as db:
        provider = _provider_do_usuario(db, usuario.id)
        if provider is None:
            raise HTTPException(status_code=404, detail="Perfil não encontrado.")
        # FOR UPDATE impede conclusão dupla concorrente da mesma coleta.
        coleta = _coleta_do_provider(db, coleta_id, provider.id, bloquear=True)
        chave = _chave_idempotencia(x_idempotency_key)
        hash_operacao = _hash_operacao(dados) if chave is not None else None
        if chave is not None:
            armazenada = _verificar_chave_registro(
                db, chave, usuario.id, "CONCLUSAO", coleta_id, hash_operacao
            )
            if armazenada is not None:
                return JSONResponse(status_code=200, content=armazenada)
        if coleta.status != "EM_CONFERENCIA":
            raise HTTPException(status_code=409, detail="Conferência não está aberta para esta coleta.")
        if db.scalars(
            select(CollectionItemChecked.id).where(CollectionItemChecked.collection_id == coleta_id)
        ).first() is not None:
            raise HTTPException(status_code=409, detail="Conferência já concluída para esta coleta.")

        quantidade_declarada = sum(
            item.quantidade_declarada
            for item in db.scalars(
                select(CollectionItemDeclared).where(
                    CollectionItemDeclared.collection_id == coleta_id
                )
            ).all()
        )
        divergencia = (
            dados.quantidade_conferida != quantidade_declarada
            or dados.quantidade_coletada != quantidade_declarada
        )
        if divergencia:
            # Doc 03 §3: divergência exige justificativa fundamentada + pelo menos 1 foto.
            if not dados.justificativa_divergencia or not dados.fotos_divergencia_json:
                raise HTTPException(
                    status_code=422,
                    detail="Divergência de quantidade exige justificativa e foto.",
                )

        pneus_registrados = len(db.scalars(select(Tire.id).where(Tire.collection_id == coleta_id)).all())
        if pneus_registrados != dados.quantidade_coletada:
            # Doc 03 §3: Quantidade Coletada = soma exata dos registros individuais.
            raise HTTPException(
                status_code=409,
                detail="Quantidade coletada deve corresponder aos pneus registrados.",
            )

        db.add(
            CollectionItemChecked(
                collection_id=coleta_id,
                quantidade_conferida=dados.quantidade_conferida,
                quantidade_coletada=dados.quantidade_coletada,
                justificativa_divergencia=dados.justificativa_divergencia,
                fotos_divergencia_json=dados.fotos_divergencia_json,
            )
        )
        resultado = db.execute(_stmt_avanco(coleta_id, "EM_CONFERENCIA", "CARREGADA"))
        if resultado.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="Transição inválida a partir do estado atual.")
        corpo = {"id": coleta_id, "status": "CARREGADA"}
        try:
            if chave is not None:
                db.add(
                    IdempotencyRecord(
                        chave=chave,
                        user_id=usuario.id,
                        escopo="CONCLUSAO",
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
                db, chave, usuario.id, "CONCLUSAO", coleta_id, hash_operacao
            )
            if armazenada is None:
                raise
            return JSONResponse(status_code=200, content=armazenada)
        return corpo


@router.post("/{coleta_id}/contestar")
def contestar_coleta(
    coleta_id: str,
    _dados: ContestacaoRequest,
    request: Request,
    usuario: User = Depends(require_roles("CLIENTE", "ADMINISTRADOR")),
) -> dict:
    with db_session.SessionLocal() as db:
        if usuario.role != "ADMINISTRADOR":
            client = _client_do_usuario(db, usuario.id)
            if client is None:
                raise HTTPException(status_code=404, detail="Perfil não encontrado.")
        # FOR UPDATE serializa contestações simultâneas; a transição FINALIZADA
        # -> CONTESTADA é decidida pelo UPDATE condicional no banco.
        coleta = db.get(Collection, coleta_id, with_for_update=True)
        if usuario.role == "ADMINISTRADOR":
            # Matriz doc 04: admin atua na contestação (mediação, doc 10 §2).
            if coleta is None:
                raise HTTPException(status_code=404, detail=NAO_ENCONTRADO)
        else:
            # Anti-enumeração: inexistente e alheia são indistinguíveis.
            if coleta is None or coleta.client_id != client.id:
                raise HTTPException(status_code=404, detail=NAO_ENCONTRADO)
        resultado = db.execute(_stmt_avanco(coleta_id, "FINALIZADA", "CONTESTADA"))
        if resultado.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="Transição inválida a partir do estado atual.")
        db.add(
            AuditLog(
                user_id=usuario.id,
                acao="CONTESTACAO_COLETA",
                entidade_afetada="collections",
                entidade_id=coleta_id,
                valor_anterior_json={"status": "FINALIZADA"},
                valor_novo_json={"status": "CONTESTADA"},
                ip_origem=request.client.host if request.client else "desconhecida",
            )
        )
        db.commit()
        return {"id": coleta_id, "status": "CONTESTADA"}
