# backend/app/main.py
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from backend.app.auth import router as auth_router
from backend.app.admin import router as admin_router
from backend.app.collections import router as collections_router
from backend.app.ownership import router as ownership_router
from backend.app.profiles import router as profiles_router
from backend.app.pricing import router as pricing_router
from backend.app.rbac import router as rbac_router
from backend.db import session as db_session

app = FastAPI(title="Plataforma de Coleta e Transporte de Pneus")
app.include_router(auth_router)
app.include_router(rbac_router)
app.include_router(profiles_router)
app.include_router(ownership_router)
app.include_router(collections_router)
app.include_router(pricing_router)
app.include_router(admin_router)

# Rejeita corpos excessivos antes de chegarem às rotas (413). Clientes reais
# enviam Content-Length; transfer-encoding chunked fica como pendência.
LIMITE_CORPO_BYTES = 1_048_576

# HSTS somente quando HTTPS é garantido no ambiente (implantação ativa via
# variável); desenvolvimento local HTTP e testes permanecem sem o cabeçalho.
HSTS_HABILITADO = os.getenv("HSTS_ENABLED", "").lower() in ("1", "true", "yes")

_CABECALHOS_API = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    # API REST JSON sem HTML próprio; /docs recebe política própria abaixo.
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}
_ROTAS_DOCS = ("/docs", "/redoc", "/openapi.json")


@app.middleware("http")
async def hardening_http(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length is not None and content_length.isdigit() and int(content_length) > LIMITE_CORPO_BYTES:
        resposta = JSONResponse(
            status_code=413,
            content={"detail": "Corpo da requisição excede o tamanho máximo permitido."},
        )
    else:
        resposta = await call_next(request)
    cabecalhos = _CABECALHOS_API
    if request.url.path.startswith(_ROTAS_DOCS):
        # Swagger UI precisa carregar scripts/estilos próprios.
        cabecalhos = {k: v for k, v in _CABECALHOS_API.items() if k != "Content-Security-Policy"}
    for cabecalho, valor in cabecalhos.items():
        resposta.headers[cabecalho] = valor
    if HSTS_HABILITADO:
        resposta.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return resposta


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/health/db")
def health_db() -> JSONResponse:
    try:
        with db_session.SessionLocal() as db:
            db.execute(select(1))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "unavailable"},
        )
    return JSONResponse(content={"status": "ok", "database": "ok"})
