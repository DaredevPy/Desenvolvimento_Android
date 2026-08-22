# backend/app/rbac.py
# Endpoints /test são temporários, exclusivos para comprovar o RBAC.
from fastapi import APIRouter, Depends, HTTPException

from backend.db.models import User

from .auth import get_current_user

router = APIRouter(prefix="/api/v1/rbac", tags=["rbac"])


def require_roles(*roles_permitidas: str):
    def dependencia(usuario: User = Depends(get_current_user)) -> User:
        if usuario.role not in roles_permitidas:
            raise HTTPException(status_code=403, detail="Acesso negado para este perfil.")
        return usuario
    return dependencia


@router.get("/test/client")
def teste_cliente(usuario: User = Depends(require_roles("CLIENTE"))) -> dict:
    return {"status": "ok", "role": usuario.role}


@router.get("/test/provider")
def teste_prestador(usuario: User = Depends(require_roles("PRESTADOR"))) -> dict:
    return {"status": "ok", "role": usuario.role}


@router.get("/test/admin")
def teste_admin(usuario: User = Depends(require_roles("ADMINISTRADOR"))) -> dict:
    return {"status": "ok", "role": usuario.role}
