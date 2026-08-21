# backend/db/session.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .models import Base

# URL do banco de dados (padrão SQLite em memória para suíte de testes se não especificado PostgreSQL)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///:memory:")

# No SQLite, habilita verificação de Foreign Keys e Same Thread
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db(bind_engine=engine):
    """Cria todas as tabelas e constraints no banco de dados."""
    Base.metadata.create_all(bind=bind_engine)

def drop_db(bind_engine=engine):
    """Remove todas as tabelas do banco de dados."""
    Base.metadata.drop_all(bind=bind_engine)

def get_db_session() -> Session:
    """Retorna uma nova sessão do banco de dados."""
    return SessionLocal()
