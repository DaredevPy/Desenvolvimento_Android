# backend/tests/test_rbac.py
import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.app import security
from backend.db import session as db_session
from backend.db.models import Base, User

SECRET_TESTE = "chave-de-teste-com-mais-de-32-bytes-para-hmac-sha256-0123456789"


class TestRbac(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._secret_original = os.environ.get("SECRET_KEY")
        os.environ["SECRET_KEY"] = SECRET_TESTE
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(cls.engine)
        cls._patcher = mock.patch.object(db_session, "SessionLocal", sessionmaker(bind=cls.engine))
        cls._patcher.start()
        cls.client = TestClient(app)
        with sessionmaker(bind=cls.engine)() as db:
            db.add(User(
                email="rbac-admin@test.com",
                password_hash=security.hash_password("senha@123"),
                role="ADMINISTRADOR",
            ))
            db.commit()

    @classmethod
    def tearDownClass(cls):
        cls._patcher.stop()
        cls.engine.dispose()
        if cls._secret_original is None:
            del os.environ["SECRET_KEY"]
        else:
            os.environ["SECRET_KEY"] = cls._secret_original

    @classmethod
    def token_para(cls, email):
        resposta = cls.client.post(
            "/api/v1/auth/login", json={"email": email, "senha": "senha@123"}
        )
        assert resposta.status_code == 200, resposta.text
        return resposta.json()["access_token"]

    def acessar(self, caminho, email):
        return self.client.get(
            f"/api/v1/rbac/test/{caminho}",
            headers={"Authorization": f"Bearer {self.token_para(email)}"},
        )

    def test_cliente_acessa_endpoint_cliente_200(self):
        self.registrar_se_necessario("rbac-cliente@test.com")
        resposta = self.acessar("client", "rbac-cliente@test.com")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {"status": "ok", "role": "CLIENTE"})

    def test_prestador_acessa_endpoint_prestador_200(self):
        self.registrar_se_necessario("rbac-prestador@test.com", role="PRESTADOR")
        resposta = self.acessar("provider", "rbac-prestador@test.com")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {"status": "ok", "role": "PRESTADOR"})

    def test_administrador_acessa_endpoint_administrador_200(self):
        resposta = self.acessar("admin", "rbac-admin@test.com")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {"status": "ok", "role": "ADMINISTRADOR"})

    def test_cliente_acessa_administrador_403(self):
        self.registrar_se_necessario("rbac-cliente@test.com")
        resposta = self.acessar("admin", "rbac-cliente@test.com")
        self.assertEqual(resposta.status_code, 403)

    def test_prestador_acessa_administrador_403(self):
        self.registrar_se_necessario("rbac-prestador@test.com", role="PRESTADOR")
        resposta = self.acessar("admin", "rbac-prestador@test.com")
        self.assertEqual(resposta.status_code, 403)

    def test_cliente_acessa_prestador_403(self):
        self.registrar_se_necessario("rbac-cliente@test.com")
        resposta = self.acessar("provider", "rbac-cliente@test.com")
        self.assertEqual(resposta.status_code, 403)

    def test_prestador_acessa_cliente_403(self):
        self.registrar_se_necessario("rbac-prestador@test.com", role="PRESTADOR")
        resposta = self.acessar("client", "rbac-prestador@test.com")
        self.assertEqual(resposta.status_code, 403)

    def test_requisicao_sem_token_401(self):
        resposta = self.client.get("/api/v1/rbac/test/admin")
        self.assertEqual(resposta.status_code, 401)

    def test_token_invalido_401(self):
        resposta = self.client.get(
            "/api/v1/rbac/test/admin", headers={"Authorization": "Bearer lixo"}
        )
        self.assertEqual(resposta.status_code, 401)

    def test_role_nao_autorizada_recebe_403_e_nunca_401(self):
        self.registrar_se_necessario("rbac-cliente@test.com")
        resposta = self.acessar("provider", "rbac-cliente@test.com")
        self.assertEqual(resposta.status_code, 403)
        corpo = resposta.json()
        self.assertNotIn("WWW-Authenticate", resposta.headers)

    def test_autorizacao_independente_do_corpo_da_requisicao(self):
        self.registrar_se_necessario("rbac-cliente@test.com")
        token = self.token_para("rbac-cliente@test.com")
        resposta = self.client.request(
            "GET",
            "/api/v1/rbac/test/admin?role=ADMINISTRADOR",
            headers={"Authorization": f"Bearer {token}"},
            json={"role": "ADMINISTRADOR"},
        )
        self.assertEqual(resposta.status_code, 403)
        self.assertNotEqual(resposta.json().get("role"), "ADMINISTRADOR")

    def registrar_se_necessario(self, email, role=None):
        payload = {"email": email, "senha": "senha@123"}
        if role is not None:
            payload["role"] = role
        resposta = self.client.post("/api/v1/auth/register", json=payload)
        self.assertIn(resposta.status_code, (201, 409))


if __name__ == "__main__":
    unittest.main()
