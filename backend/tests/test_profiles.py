# backend/tests/test_profiles.py
import os
import unittest
from itertools import count
from unittest import mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.db import session as db_session
from backend.db.models import Base, Client, Profile, Provider, User

SECRET_TESTE = "chave-de-teste-com-mais-de-32-bytes-para-hmac-sha256-0123456789"

CLIENTE_A = {
    "nome_razao_social": "Cliente A LTDA",
    "telefone": "(11) 98888-7777",
}
PRESTADOR_P = {
    "nome_razao_social": "Prestador Silva ME",
    "telefone": "(21) 97777-6666",
    "dados_veiculo_json": {"placa": "ABC1D23", "tipo": "truck"},
}
_CPF_SEQ = count(90_000_000_000_001, 7)


def so_digitos(valor):
    return "".join(c for c in valor if c.isdigit())


class TestProfiles(unittest.TestCase):
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

    # --- auxiliares idempotentes (cada teste garante seus próprios dados) ---

    def registrar(self, email, role=None):
        payload = {"email": email, "senha": "senha@123"}
        if role is not None:
            payload["role"] = role
        resposta = self.client.post("/api/v1/auth/register", json=payload)
        self.assertIn(resposta.status_code, (201, 409), resposta.text)
        return resposta

    def headers_de(self, email):
        resposta = self.client.post(
            "/api/v1/auth/login", json={"email": email, "senha": "senha@123"}
        )
        if resposta.status_code != 200:
            self.fail(f"login {email} -> {resposta.status_code}: {resposta.text[:200]}")
        return {"Authorization": f"Bearer {resposta.json()['access_token']}"}

    def garantir_perfil(self, email, rota, dados):
        resposta = self.client.post(
            f"/api/v1/profile/{rota}", json=dados, headers=self.headers_de(email)
        )
        self.assertIn(resposta.status_code, (201, 409), resposta.text)

    def usuario_id(self, email):
        with sessionmaker(bind=self.engine)() as db:
            return db.scalars(select(User).where(User.email == email)).first().id

    def novo_cpf(self):
        return str(next(_CPF_SEQ))

    def perfil_no_banco(self, email):
        with sessionmaker(bind=self.engine)() as db:
            perfil = db.scalars(
                select(Profile).where(Profile.user_id == self.usuario_id(email))
            ).first()
            cliente = vinculo = None
            if perfil:
                cliente = db.scalars(select(Client).where(Client.profile_id == perfil.id)).first()
                vinculo = db.scalars(select(Provider).where(Provider.profile_id == perfil.id)).first()
            return perfil, cliente, vinculo

    # --- 1 a 3: ciclo CLIENTE ---

    def test_1_cliente_cria_proprio_perfil(self):
        self.registrar("prof-cria-c@test.com")
        cpf = self.novo_cpf()
        resposta = self.client.post(
            "/api/v1/profile/client",
            json={**CLIENTE_A, "cpf_cnpj": cpf},
            headers=self.headers_de("prof-cria-c@test.com"),
        )
        self.assertEqual(resposta.status_code, 201)
        corpo = resposta.json()
        self.assertEqual(corpo["nome_razao_social"], "Cliente A LTDA")
        self.assertEqual(corpo["cpf_cnpj"], cpf)
        perfil, cliente, _ = self.perfil_no_banco("prof-cria-c@test.com")
        self.assertIsNotNone(perfil)
        self.assertIsNotNone(cliente)
        self.assertEqual(perfil.user_id, self.usuario_id("prof-cria-c@test.com"))

    def test_2_cliente_consulta_proprio_perfil(self):
        self.registrar("prof-le-c@test.com")
        cpf = self.novo_cpf()
        self.garantir_perfil("prof-le-c@test.com", "client", {**CLIENTE_A, "cpf_cnpj": cpf})
        resposta = self.client.get(
            "/api/v1/profile/client", headers=self.headers_de("prof-le-c@test.com")
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["cpf_cnpj"], cpf)

    def test_3_cliente_atualiza_proprio_perfil(self):
        self.registrar("prof-upd-c@test.com")
        cpf = self.novo_cpf()
        self.garantir_perfil("prof-upd-c@test.com", "client", {**CLIENTE_A, "cpf_cnpj": cpf})
        resposta = self.client.put(
            "/api/v1/profile/client",
            json={"telefone": "11977776666"},
            headers=self.headers_de("prof-upd-c@test.com"),
        )
        self.assertEqual(resposta.status_code, 200)
        confirmacao = self.client.get(
            "/api/v1/profile/client", headers=self.headers_de("prof-upd-c@test.com")
        )
        self.assertEqual(confirmacao.json()["telefone"], "11977776666")
        self.assertEqual(confirmacao.json()["cpf_cnpj"], cpf)

    # --- 4 a 6: ciclo PRESTADOR ---

    def test_4_prestador_cria_proprio_perfil(self):
        self.registrar("prof-cria-p@test.com", role="PRESTADOR")
        cpf = self.novo_cpf()
        resposta = self.client.post(
            "/api/v1/profile/provider",
            json={**PRESTADOR_P, "cpf_cnpj": cpf, "chave_pix": f"pix{cpf[-6:]}@teste.com"},
            headers=self.headers_de("prof-cria-p@test.com"),
        )
        self.assertEqual(resposta.status_code, 201)
        corpo = resposta.json()
        self.assertEqual(corpo["status_operacional"], "DISPONIVEL")
        _, _, prestador = self.perfil_no_banco("prof-cria-p@test.com")
        self.assertIsNotNone(prestador)
        self.assertEqual(prestador.dados_veiculo_json["placa"], "ABC1D23")

    def test_5_prestador_consulta_proprio_perfil(self):
        self.registrar("prof-le-p@test.com", role="PRESTADOR")
        cpf = self.novo_cpf()
        pix = f"pix{cpf[-6:]}@teste.com"
        self.garantir_perfil(
            "prof-le-p@test.com", "provider", {**PRESTADOR_P, "cpf_cnpj": cpf, "chave_pix": pix}
        )
        resposta = self.client.get(
            "/api/v1/profile/provider", headers=self.headers_de("prof-le-p@test.com")
        )
        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.json()
        self.assertEqual(corpo["chave_pix"], pix)
        self.assertEqual(corpo["veiculo"]["placa"], "ABC1D23")

    def test_6_prestador_atualiza_proprio_perfil(self):
        self.registrar("prof-upd-p@test.com", role="PRESTADOR")
        cpf = self.novo_cpf()
        self.garantir_perfil(
            "prof-upd-p@test.com",
            "provider",
            {**PRESTADOR_P, "cpf_cnpj": cpf, "chave_pix": f"pix{cpf[-6:]}@teste.com"},
        )
        resposta = self.client.put(
            "/api/v1/profile/provider",
            json={"chave_pix": "novapix@prestador.com", "dados_veiculo_json": {"placa": "XYZ9K88"}},
            headers=self.headers_de("prof-upd-p@test.com"),
        )
        self.assertEqual(resposta.status_code, 200)
        confirmacao = self.client.get(
            "/api/v1/profile/provider", headers=self.headers_de("prof-upd-p@test.com")
        )
        self.assertEqual(confirmacao.json()["chave_pix"], "novapix@prestador.com")
        self.assertEqual(confirmacao.json()["veiculo"]["placa"], "XYZ9K88")

    # --- 7 a 9: RBAC e autenticação ---

    def test_7_cliente_bloqueado_em_endpoint_prestador_403(self):
        self.registrar("prof-rbac-c@test.com")
        cabecalhos = self.headers_de("prof-rbac-c@test.com")
        self.assertEqual(self.client.get("/api/v1/profile/provider", headers=cabecalhos).status_code, 403)
        self.assertEqual(
            self.client.post("/api/v1/profile/provider", json=PRESTADOR_P, headers=cabecalhos).status_code,
            403,
        )

    def test_8_prestador_bloqueado_em_endpoint_cliente_403(self):
        self.registrar("prof-rbac-p@test.com", role="PRESTADOR")
        cabecalhos = self.headers_de("prof-rbac-p@test.com")
        self.assertEqual(self.client.get("/api/v1/profile/client", headers=cabecalhos).status_code, 403)
        self.assertEqual(
            self.client.post("/api/v1/profile/client", json=CLIENTE_A, headers=cabecalhos).status_code,
            403,
        )

    def test_9_nao_autenticado_recebe_401(self):
        self.assertEqual(self.client.get("/api/v1/profile/client").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/profile/provider").status_code, 401)
        self.assertEqual(
            self.client.post("/api/v1/profile/client", json=CLIENTE_A).status_code, 401
        )

    # --- 10 a 12: ownership ---

    def test_10_usuario_nao_acessa_nem_altera_perfil_alheio(self):
        self.registrar("prof-a@test.com")
        self.registrar("prof-b@test.com")
        cpf_a = self.novo_cpf()
        cpf_b = self.novo_cpf()
        self.garantir_perfil("prof-a@test.com", "client", {**CLIENTE_A, "cpf_cnpj": cpf_a})
        self.garantir_perfil("prof-b@test.com", "client", {**CLIENTE_A, "cpf_cnpj": cpf_b})
        leitura_a = self.client.get("/api/v1/profile/client", headers=self.headers_de("prof-a@test.com"))
        self.assertNotEqual(leitura_a.json()["cpf_cnpj"], cpf_b)
        tentativa = self.client.put(
            "/api/v1/profile/client",
            json={"user_id": self.usuario_id("prof-b@test.com"), "nome_razao_social": "HACKEADO"},
            headers=self.headers_de("prof-a@test.com"),
        )
        self.assertIn(tentativa.status_code, (403, 422))
        leitura_b = self.client.get("/api/v1/profile/client", headers=self.headers_de("prof-b@test.com"))
        self.assertEqual(leitura_b.json()["cpf_cnpj"], cpf_b)
        self.assertNotEqual(leitura_b.json()["nome_razao_social"], "HACKEADO")

    def test_11_user_id_no_corpo_e_rejeitado_sem_mudar_dono(self):
        self.registrar("prof-bodyid@test.com")
        self.registrar("prof-alvo@test.com")
        resposta = self.client.post(
            "/api/v1/profile/client",
            json={
                **CLIENTE_A,
                "cpf_cnpj": self.novo_cpf(),
                "user_id": self.usuario_id("prof-alvo@test.com"),
            },
            headers=self.headers_de("prof-bodyid@test.com"),
        )
        self.assertEqual(resposta.status_code, 422)
        consulta_alvo = self.client.get(
            "/api/v1/profile/client", headers=self.headers_de("prof-alvo@test.com")
        )
        self.assertIn(consulta_alvo.status_code, (404, 200))

    def test_12_user_id_na_query_nao_permite_acesso_cruzado(self):
        self.registrar("prof-q-a@test.com")
        self.registrar("prof-q-b@test.com")
        cpf_a = self.novo_cpf()
        cpf_b = self.novo_cpf()
        self.garantir_perfil("prof-q-a@test.com", "client", {**CLIENTE_A, "cpf_cnpj": cpf_a})
        self.garantir_perfil("prof-q-b@test.com", "client", {**CLIENTE_A, "cpf_cnpj": cpf_b})
        resposta = self.client.get(
            f"/api/v1/profile/client?user_id={self.usuario_id('prof-q-b@test.com')}",
            headers=self.headers_de("prof-q-a@test.com"),
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["cpf_cnpj"], cpf_a)

    # --- 13: validação ---

    def test_13_dados_invalidos_rejeitados(self):
        self.registrar("prof-invalido@test.com")
        cabecalhos = self.headers_de("prof-invalido@test.com")
        casos = [
            {**CLIENTE_A, "cpf_cnpj": "1234567890"},
            {**CLIENTE_A, "cpf_cnpj": self.novo_cpf(), "nome_razao_social": ""},
            {**CLIENTE_A, "cpf_cnpj": self.novo_cpf(), "telefone": "123"},
            {**CLIENTE_A, "cpf_cnpj": self.novo_cpf(), "campo_inexistente": "x"},
        ]
        for caso in casos:
            resposta = self.client.post("/api/v1/profile/client", json=caso, headers=cabecalhos)
            self.assertEqual(resposta.status_code, 422, caso)

    # --- extras: duplicidade e estado ---

    def test_extra_post_duplicado_do_mesmo_usuario_409(self):
        self.registrar("prof-dup@test.com")
        self.garantir_perfil("prof-dup@test.com", "client", {**CLIENTE_A, "cpf_cnpj": self.novo_cpf()})
        resposta = self.client.post(
            "/api/v1/profile/client",
            json={**CLIENTE_A, "cpf_cnpj": self.novo_cpf()},
            headers=self.headers_de("prof-dup@test.com"),
        )
        self.assertEqual(resposta.status_code, 409)

    def test_extra_cpf_cnpj_unico_respeita_constraint_existente(self):
        self.registrar("prof-cpf1@test.com")
        self.registrar("prof-cpf2@test.com")
        cpf_compartilhado = self.novo_cpf()
        self.garantir_perfil("prof-cpf1@test.com", "client", {**CLIENTE_A, "cpf_cnpj": cpf_compartilhado})
        resposta = self.client.post(
            "/api/v1/profile/client",
            json={**CLIENTE_A, "cpf_cnpj": cpf_compartilhado, "nome_razao_social": "Outro Nome"},
            headers=self.headers_de("prof-cpf2@test.com"),
        )
        self.assertEqual(resposta.status_code, 409)

    def test_extra_put_get_sem_perfil_404(self):
        self.registrar("prof-vazio@test.com")
        cabecalhos = self.headers_de("prof-vazio@test.com")
        self.assertEqual(self.client.get("/api/v1/profile/client", headers=cabecalhos).status_code, 404)
        self.assertEqual(
            self.client.put(
                "/api/v1/profile/client", json={"telefone": "11912345678"}, headers=cabecalhos
            ).status_code,
            404,
        )

    # --- 14: vazamento de dados sensíveis ---

    def test_14_respostas_nao_expoem_autenticacao_nem_hash(self):
        self.registrar("prof-leak@test.com")
        self.garantir_perfil(
            "prof-leak@test.com", "client", {**CLIENTE_A, "cpf_cnpj": self.novo_cpf()}
        )
        respostas = [
            self.client.get("/api/v1/profile/client", headers=self.headers_de("prof-leak@test.com")),
            self.client.post("/api/v1/auth/register", json={"email": "prof-leak2@test.com", "senha": "x"}),
            self.client.get("/api/v1/profile/client"),
        ]
        for resposta in respostas:
            texto = resposta.text.lower()
            self.assertNotIn("password", texto)
            self.assertNotIn("hash", texto)
            self.assertNotIn("secret", texto)
            self.assertNotIn("access_token", texto)


if __name__ == "__main__":
    unittest.main()
