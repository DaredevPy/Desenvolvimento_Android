# backend/app/profiles.py
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.db import session as db_session
from backend.db.models import Client, Profile, Provider, User

from .rbac import require_roles

router = APIRouter(prefix="/api/v1/profile", tags=["profiles"])


def _normalizar_documento(value: str) -> str:
    digitos = "".join(caractere for caractere in value if caractere.isdigit())
    if len(digitos) not in (11, 14):
        raise ValueError("CPF/CNPJ deve conter 11 ou 14 dígitos.")
    return digitos


class PerfilBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome_razao_social: str = Field(min_length=1, max_length=255)
    cpf_cnpj: str
    telefone: str = Field(min_length=8, max_length=20)

    @field_validator("cpf_cnpj")
    @classmethod
    def validar_documento(cls, value: str) -> str:
        return _normalizar_documento(value)


class PerfilPrestadorRequest(PerfilBase):
    chave_pix: Optional[str] = Field(default=None, max_length=255)
    dados_veiculo_json: Optional[dict] = None


class ClienteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome_razao_social: Optional[str] = Field(default=None, min_length=1, max_length=255)
    cpf_cnpj: Optional[str] = None
    telefone: Optional[str] = Field(default=None, min_length=8, max_length=20)

    @field_validator("cpf_cnpj")
    @classmethod
    def validar_documento(cls, value: Optional[str]) -> Optional[str]:
        return _normalizar_documento(value) if value is not None else None


class PrestadorUpdate(ClienteUpdate):
    chave_pix: Optional[str] = Field(default=None, max_length=255)
    dados_veiculo_json: Optional[dict] = None


def _perfil_do_usuario(db, user_id: str) -> Optional[Profile]:
    return db.scalars(select(Profile).where(Profile.user_id == user_id)).first()


def _resposta_base(perfil: Profile) -> dict:
    return {
        "id": perfil.id,
        "nome_razao_social": perfil.nome_razao_social,
        "cpf_cnpj": perfil.cpf_cnpj,
        "telefone": perfil.telefone,
    }


def _aplicar_atualizacao(perfil: Profile, dados: BaseModel) -> None:
    for campo, valor in dados.model_dump(exclude_none=True).items():
        setattr(perfil, campo, valor)


@router.post("/client", status_code=201)
def criar_perfil_cliente(
    dados: PerfilBase,
    usuario: User = Depends(require_roles("CLIENTE")),
) -> dict:
    with db_session.SessionLocal() as db:
        if _perfil_do_usuario(db, usuario.id) is not None:
            raise HTTPException(status_code=409, detail="Perfil já cadastrado.")
        perfil = Profile(user_id=usuario.id, **dados.model_dump())
        db.add(perfil)
        try:
            db.flush()
            db.add(Client(profile_id=perfil.id))
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="Dados já cadastrados para outro usuário.") from None
        return _resposta_base(perfil)


@router.get("/client")
def obter_perfil_cliente(usuario: User = Depends(require_roles("CLIENTE"))) -> dict:
    with db_session.SessionLocal() as db:
        perfil = _perfil_do_usuario(db, usuario.id)
        if perfil is None:
            raise HTTPException(status_code=404, detail="Perfil não encontrado.")
        return _resposta_base(perfil)


@router.put("/client")
def atualizar_perfil_cliente(
    dados: ClienteUpdate,
    usuario: User = Depends(require_roles("CLIENTE")),
) -> dict:
    with db_session.SessionLocal() as db:
        perfil = _perfil_do_usuario(db, usuario.id)
        if perfil is None:
            raise HTTPException(status_code=404, detail="Perfil não encontrado.")
        _aplicar_atualizacao(perfil, dados)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="Dados já cadastrados para outro usuário.") from None
        return _resposta_base(perfil)


@router.post("/provider", status_code=201)
def criar_perfil_prestador(
    dados: PerfilPrestadorRequest,
    usuario: User = Depends(require_roles("PRESTADOR")),
) -> dict:
    payload = dados.model_dump()
    with db_session.SessionLocal() as db:
        if _perfil_do_usuario(db, usuario.id) is not None:
            raise HTTPException(status_code=409, detail="Perfil já cadastrado.")
        perfil = Profile(user_id=usuario.id, **{c: v for c, v in payload.items() if c != "dados_veiculo_json"})
        db.add(perfil)
        try:
            db.flush()
            db.add(Provider(profile_id=perfil.id, dados_veiculo_json=payload["dados_veiculo_json"]))
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="Dados já cadastrados para outro usuário.") from None
        return _resposta_prestador(db, perfil)


@router.get("/provider")
def obter_perfil_prestador(usuario: User = Depends(require_roles("PRESTADOR"))) -> dict:
    with db_session.SessionLocal() as db:
        perfil = _perfil_do_usuario(db, usuario.id)
        if perfil is None:
            raise HTTPException(status_code=404, detail="Perfil não encontrado.")
        return _resposta_prestador(db, perfil)


@router.put("/provider")
def atualizar_perfil_prestador(
    dados: PrestadorUpdate,
    usuario: User = Depends(require_roles("PRESTADOR")),
) -> dict:
    alteracoes = dados.model_dump(exclude_none=True)
    with db_session.SessionLocal() as db:
        perfil = _perfil_do_usuario(db, usuario.id)
        if perfil is None:
            raise HTTPException(status_code=404, detail="Perfil não encontrado.")
        veiculo = alteracoes.pop("dados_veiculo_json", None)
        for campo, valor in alteracoes.items():
            setattr(perfil, campo, valor)
        if veiculo is not None:
            prestador = db.scalars(select(Provider).where(Provider.profile_id == perfil.id)).first()
            prestador.dados_veiculo_json = veiculo
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="Dados já cadastrados para outro usuário.") from None
        return _resposta_prestador(db, perfil)


def _resposta_prestador(db, perfil: Profile) -> dict:
    prestador = db.scalars(select(Provider).where(Provider.profile_id == perfil.id)).first()
    resposta = _resposta_base(perfil)
    resposta.update({
        "chave_pix": perfil.chave_pix,
        "veiculo": prestador.dados_veiculo_json if prestador else None,
        "status_operacional": prestador.status_operacional if prestador else None,
    })
    return resposta
