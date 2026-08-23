# backend/app/ownership.py
# Rotas /test são temporárias, exclusivas para demonstrar a regra de ownership.
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from backend.db import session as db_session
from backend.db.models import Profile, User

from .rbac import require_roles

router = APIRouter(prefix="/api/v1/ownership", tags=["ownership"])

NAO_ENCONTRADO = "Recurso não encontrado."


def exigir_dono(user_id_do_recurso: str, usuario: User) -> None:
    # 404 (e não 403) para não distinguir recurso inexistente de recurso alheio.
    if user_id_do_recurso != usuario.id:
        raise HTTPException(status_code=404, detail=NAO_ENCONTRADO)


class TelefoneUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    telefone: str = Field(min_length=8, max_length=20)


def _resposta(perfil: Profile) -> dict:
    return {
        "id": perfil.id,
        "nome_razao_social": perfil.nome_razao_social,
        "cpf_cnpj": perfil.cpf_cnpj,
        "telefone": perfil.telefone,
    }


@router.get("/test/perfil/{perfil_id}")
def ler_perfil(
    perfil_id: str,
    usuario: User = Depends(require_roles("CLIENTE", "PRESTADOR")),
) -> dict:
    with db_session.SessionLocal() as db:
        perfil = db.scalars(select(Profile).where(Profile.id == perfil_id)).first()
        if perfil is None:
            raise HTTPException(status_code=404, detail=NAO_ENCONTRADO)
        exigir_dono(perfil.user_id, usuario)
        return _resposta(perfil)


@router.put("/test/perfil/{perfil_id}")
def atualizar_perfil(
    perfil_id: str,
    dados: TelefoneUpdate,
    usuario: User = Depends(require_roles("CLIENTE", "PRESTADOR")),
) -> dict:
    with db_session.SessionLocal() as db:
        perfil = db.scalars(select(Profile).where(Profile.id == perfil_id)).first()
        if perfil is None:
            raise HTTPException(status_code=404, detail=NAO_ENCONTRADO)
        exigir_dono(perfil.user_id, usuario)
        perfil.telefone = dados.telefone
        db.commit()
        return _resposta(perfil)
