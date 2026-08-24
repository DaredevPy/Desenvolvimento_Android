# backend/app/auth.py
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.db import session as db_session
from backend.db.models import User

from . import rate_limit, security

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

bearer_scheme = HTTPBearer(auto_error=False)

INVALID_CREDENTIALS = "Credenciais inválidas."


class Credenciais(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, value: str) -> str:
        return value.strip().lower()


class RegistroRequest(Credenciais):
    role: Literal["CLIENTE", "PRESTADOR"] = "CLIENTE"


def _autenticar_ou_401(detail: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _exigir_rate_limit(request: Request, escopo: str, limite: int) -> None:
    # Doc 08 §4.4: mitiga brute force em /login e abuso de criação de contas
    # em /register. Resposta uniforme por IP; não revela nada sobre a conta.
    ip = request.client.host if request.client else "desconhecida"
    retry_after = rate_limit.registrar_tentativa(escopo, limite, ip)
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Muitas requisições. Aguarde antes de tentar novamente.",
            headers={"Retry-After": str(retry_after)},
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    if credentials is None:
        raise _autenticar_ou_401("Não autenticado.")

    payload = security.decode_access_token(credentials.credentials)
    if payload is None:
        raise _autenticar_ou_401("Token inválido ou expirado.")

    with db_session.SessionLocal() as db:
        user = db.get(User, payload.get("sub"))

    if user is None or user.status != "ATIVO":
        raise _autenticar_ou_401("Token inválido ou expirado.")
    return user


@router.post("/register", status_code=201)
def register(data: RegistroRequest, request: Request) -> dict:
    _exigir_rate_limit(request, "registro", rate_limit.LIMITE_REGISTRO)
    with db_session.SessionLocal() as db:
        existente = db.scalars(select(User).where(User.email == data.email)).first()
        if existente is not None:
            raise HTTPException(status_code=409, detail="E-mail já cadastrado.")

        usuario = User(email=data.email, password_hash=security.hash_password(data.senha), role=data.role)
        db.add(usuario)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="E-mail já cadastrado.") from None
        return {"id": usuario.id, "email": usuario.email, "role": usuario.role}


@router.post("/login")
def login(data: Credenciais, request: Request) -> dict:
    _exigir_rate_limit(request, "login", rate_limit.LIMITE_LOGIN)
    with db_session.SessionLocal() as db:
        usuario = db.scalars(select(User).where(User.email == data.email)).first()

    if usuario is None:
        security.verify_password(data.senha, security.DUMMY_HASH)
        raise _autenticar_ou_401(INVALID_CREDENTIALS)

    if not security.verify_password(data.senha, usuario.password_hash):
        raise _autenticar_ou_401(INVALID_CREDENTIALS)

    token = security.create_access_token(usuario.id, usuario.role)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
def me(usuario: User = Depends(get_current_user)) -> dict:
    return {"id": usuario.id, "email": usuario.email, "role": usuario.role, "status": usuario.status}
