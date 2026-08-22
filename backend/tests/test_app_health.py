# backend/tests/test_app_health.py
import unittest
from unittest import mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.db import session as db_session

client = TestClient(app)


class TestHealthEndpoints(unittest.TestCase):
    def test_health_retorna_ok(self):
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_health_db_executa_consulta_com_banco_disponivel(self):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        with mock.patch.object(db_session, "SessionLocal", sessionmaker(bind=engine)):
            response = client.get("/health/db")
        engine.dispose()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})

    def test_health_db_banco_indisponivel_retorna_503_sem_dados_internos(self):
        engine = create_engine("sqlite:///./diretorio_inexistente_health/banco.db")
        with mock.patch.object(db_session, "SessionLocal", sessionmaker(bind=engine)):
            response = client.get("/health/db")
        engine.dispose()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "error", "database": "unavailable"})
        self.assertNotIn("DATABASE_URL", response.text)
        self.assertNotIn("Traceback", response.text)

    def test_health_db_utiliza_sessao_padrao_da_aplicacao(self):
        response = client.get("/health/db")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})


if __name__ == "__main__":
    unittest.main()
