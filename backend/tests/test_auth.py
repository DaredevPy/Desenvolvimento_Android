# backend/tests/test_auth.py
import os
import unittest
from unittest import mock

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.app import security
from backend.db import session as db_session
from backend.db.models import Base, User

MSG_INVALIDAS = "Credenciais inválidas."
SECRET_TESTE = "chave-de-teste-com-mais-de-32-bytes-para-hmac-sha256-0123456789"


class TestAuth(unittest.TestCase):
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

    @classmethod
    def tearDownClass(cls):
        cls._patcher.stop()
        cls.engine.dispose()
        if cls._secret_original is None:
            del os.environ["SECRET_KEY"]
        else:
            os.environ["SECRET_KEY"] = cls._secret_original

    def registrar(self, email, senha="senha@123", role=None):
        payload = {"email": email, "senha": senha}
        if role is not None:
            payload["role"] = role
        return self.client.post("/api/v1/auth/register", json=payload)

    def login(self, email, senha):
        return self.client.post("/api/v1/auth/login", json={"email": email, "senha": senha})

    def hash_armazenado(self, email):
        with sessionmaker(bind=self.engine)() as db:
            usuario = db.scalars(select(User).where(User.email == email)).first()
            return usuario.password_hash if usuario else None

    def test_registro_usuario_valido(self):
        resposta = self.registrar("auth-registro@test.com", role="PRESTADOR")
        self.assertEqual(resposta.status_code, 201)
        corpo = resposta.json()
        self.assertEqual(corpo["email"], "auth-registro@test.com")
        self.assertEqual(corpo["role"], "PRESTADOR")
        self.assertIn("id", corpo)

    def test_role_padrao_e_cliente(self):
        resposta = self.registrar("auth-padrao@test.com")
        self.assertEqual(resposta.json()["role"], "CLIENTE")

    def test_senha_nunca_armazenada_em_texto_puro(self):
        senha = "minha-senha-secreta-unica"
        self.registrar("auth-textopuro@test.com", senha)
        armazenado = self.hash_armazenado("auth-textopuro@test.com")
        self.assertIsNotNone(armazenado)
        self.assertNotIn(senha, armazenado)

    def test_senha_armazenada_como_hash_argon2id(self):
        self.registrar("auth-hash@test.com")
        armazenado = self.hash_armazenado("auth-hash@test.com")
        self.assertTrue(armazenado.startswith("$argon2id$"))

    def test_login_credenciais_validas(self):
        self.registrar("auth-login@test.com", "senha-correta")
        resposta = self.login("auth-login@test.com", "senha-correta")
        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.json()
        self.assertEqual(corpo["token_type"], "bearer")
        self.assertIn("access_token", corpo)

    def test_login_senha_invalida(self):
        self.registrar("auth-senhaerro@test.com", "senha-correta")
        resposta = self.login("auth-senhaerro@test.com", "senha-errada")
        self.assertEqual(resposta.status_code, 401)
        self.assertEqual(resposta.json()["detail"], MSG_INVALIDAS)

    def test_login_usuario_inexistente_mensagem_idêntica(self):
        self.registrar("auth-enum@test.com", "senha-correta")
        resposta_inexistente = self.login("fantasma@test.com", "qualquer-senha")
        resposta_senha_errada = self.login("auth-enum@test.com", "senha-errada")
        self.assertEqual(resposta_inexistente.status_code, 401)
        self.assertEqual(resposta_inexistente.json(), resposta_senha_errada.json())

    def test_token_valido_identifica_usuario(self):
        self.registrar("auth-token@test.com")
        token = self.login("auth-token@test.com", "senha@123").json()["access_token"]
        payload = jwt.decode(token, SECRET_TESTE, algorithms=["HS256"])
        with sessionmaker(bind=self.engine)() as db:
            usuario = db.scalars(select(User).where(User.email == "auth-token@test.com")).first()
        self.assertEqual(payload["sub"], usuario.id)
        self.assertEqual(payload["role"], "CLIENTE")

    def test_auth_me_sem_token_retorna_401(self):
        resposta = self.client.get("/api/v1/auth/me")
        self.assertEqual(resposta.status_code, 401)

    def test_auth_me_token_invalido_retorna_401(self):
        resposta = self.client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer nao-e-um-jwt"}
        )
        self.assertEqual(resposta.status_code, 401)

    def test_auth_me_autenticado_retorna_dados(self):
        self.registrar("auth-me@test.com")
        token = self.login("auth-me@test.com", "senha@123").json()["access_token"]
        resposta = self.client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.json()
        self.assertEqual(corpo["email"], "auth-me@test.com")
        self.assertEqual(corpo["role"], "CLIENTE")
        self.assertEqual(corpo["status"], "ATIVO")

    def test_token_assinado_com_chave_errada_e_expirado_rejeitados(self):
        token_errado = jwt.encode({"sub": "x"}, "outra-chave-de-teste-com-mais-de-32-bytes-0123456789", algorithm="HS256")
        r1 = self.client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token_errado}"}
        )
        self.assertEqual(r1.status_code, 401)
        with mock.patch.object(security, "ACCESS_TOKEN_EXPIRE_MINUTES", -1):
            token_expirado = security.create_access_token("usuario-x", "CLIENTE")
        r2 = self.client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token_expirado}"}
        )
        self.assertEqual(r2.status_code, 401)

    def test_registro_email_duplicado(self):
        self.registrar("auth-duplicado@test.com")
        resposta = self.registrar("auth-duplicado@test.com", "outra-senha")
        self.assertEqual(resposta.status_code, 409)

    def test_role_administrador_rejeitada_no_cadastro_publico(self):
        resposta = self.registrar("auth-admin-publico@test.com", role="ADMINISTRADOR")
        self.assertEqual(resposta.status_code, 422)

    def test_email_invalido_rejeitado(self):
        resposta = self.registrar("nao-e-email")
        self.assertEqual(resposta.status_code, 422)


if __name__ == "__main__":
    unittest.main()
