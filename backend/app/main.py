# backend/app/main.py
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import select

from backend.app.auth import router as auth_router
from backend.app.profiles import router as profiles_router
from backend.app.rbac import router as rbac_router
from backend.db import session as db_session

app = FastAPI(title="Plataforma de Coleta e Transporte de Pneus")
app.include_router(auth_router)
app.include_router(rbac_router)
app.include_router(profiles_router)


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
