# backend/tests/test_ownership.py
import os
import unittest
import uuid as uuid_lib
from itertools import count
from unittest import mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import security
from backend.app.main import app
from backend.db import session as db_session
from backend.db.models import Base, Profile, User

SECRET_TESTE = "chave-de-teste-com-mais-de-32-bytes-para-hmac-sha256-0123456789"

SENHA = "senha@123"
DADOS_PERFIL = {"nome_razao_social": "Dono do Perfil LTDA", "telefone": "(11) 98888-7777"}
_CPF_SEQ = count(70_000_000_000_001, 11)


class TestOwnership(unittest.TestCase):
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

    # --- auxiliares ---

    def registrar(self, email, role="CLIENTE"):
        resposta = self.client.post(
            "/api/v1/auth/register", json={"email": email, "senha": SENHA, "role": role}
        )
        self.assertIn(resposta.status_code, (201, 409), resposta.text)

    def headers_de(self, email):
        resposta = self.client.post("/api/v1/auth/login", json={"email": email, "senha": SENHA})
        self.assertEqual(resposta.status_code, 200, resposta.text[:200])
        return {"Authorization": f"Bearer {resposta.json()['access_token']}"}

    def novo_cpf(self):
        return str(next(_CPF_SEQ))

    def garantir_perfil(self, email, rota="client"):
        self.registrar(email, role="PRESTADOR" if rota == "provider" else "CLIENTE")
        resposta = self.client.post(
            f"/api/v1/profile/{rota}",
            json={**DADOS_PERFIL, "cpf_cnpj": self.novo_cpf()},
            headers=self.headers_de(email),
        )
        self.assertIn(resposta.status_code, (201, 409), resposta.text)

    def perfil_id_de(self, email):
        with sessionmaker(bind=self.engine)() as db:
            user_id = db.scalars(select(User).where(User.email == email)).first().id
            return db.scalars(select(Profile).where(Profile.user_id == user_id)).first().id

    def perfil_do_banco(self, email):
        with sessionmaker(bind=self.engine)() as db:
            user_id = db.scalars(select(User).where(User.email == email)).first().id
            return db.scalars(select(Profile).where(Profile.user_id == user_id)).first()

    def criar_admin_direto_no_banco(self, email):
        with sessionmaker(bind=self.engine)() as db:
            db.add(User(email=email, password_hash=security.hash_password(SENHA), role="ADMINISTRADOR"))
            db.commit()

    # --- 1: dono acessa o próprio recurso pelo UUID ---

    def test_01_dono_acessa_proprio_recurso_por_uuid(self):
        self.garantir_perfil("own-dono-c@test.com")
        cabecalhos = self.headers_de("own-dono-c@test.com")
        resposta = self.client.get(
            f"/api/v1/ownership/test/perfil/{self.perfil_id_de('own-dono-c@test.com')}",
            headers=cabecalhos,
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["nome_razao_social"], DADOS_PERFIL["nome_razao_social"])

        self.garantir_perfil("own-dono-p@test.com", rota="provider")
        resposta_p = self.client.get(
            f"/api/v1/ownership/test/perfil/{self.perfil_id_de('own-dono-p@test.com')}",
            headers=self.headers_de("own-dono-p@test.com"),
        )
        self.assertEqual(resposta_p.status_code, 200)

    def test_02_dono_atualiza_proprio_recurso_por_uuid(self):
        self.garantir_perfil("own-upd@test.com")
        perfil_id = self.perfil_id_de("own-upd@test.com")
        resposta = self.client.put(
            f"/api/v1/ownership/test/perfil/{perfil_id}",
            json={"telefone": "11912345678"},
            headers=self.headers_de("own-upd@test.com"),
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["telefone"], "11912345678")
        self.assertEqual(self.perfil_do_banco("own-upd@test.com").telefone, "11912345678")

    # --- 2 e 5: recurso alheio e manipulação de UUID na URL ---

    def test_03_recurso_alheio_e_inexistente_sao_indistinguiveis(self):
        self.garantir_perfil("own-vitima@test.com")
        self.garantir_perfil("own-invasor@test.com")
        self.garantir_perfil("own-inv-prest@test.com", rota="provider")
        perfil_alheio = self.perfil_id_de("own-vitima@test.com")
        cabecalhos = self.headers_de("own-invasor@test.com")

        alheio = self.client.get(
            f"/api/v1/ownership/test/perfil/{perfil_alheio}", headers=cabecalhos
        )
        inexistente = self.client.get(
            f"/api/v1/ownership/test/perfil/{uuid_lib.uuid4()}", headers=cabecalhos
        )
        self.assertEqual(alheio.status_code, 404)
        self.assertEqual(inexistente.status_code, 404)
        self.assertEqual(alheio.json(), inexistente.json())
        self.assertNotIn("own-vitima@test.com".split("@")[0], alheio.text.lower())
        self.assertNotIn(DADOS_PERFIL["nome_razao_social"].lower(), alheio.text.lower())

        cruzado = self.client.get(
            f"/api/v1/ownership/test/perfil/{perfil_alheio}",
            headers=self.headers_de("own-inv-prest@test.com"),
        )
        self.assertEqual(cruzado.status_code, 404)

    def test_04_manipular_uuid_na_url_nao_concede_acesso(self):
        self.garantir_perfil("own-url-a@test.com")
        self.garantir_perfil("own-url-b@test.com")
        cabecalhos = self.headers_de("own-url-b@test.com")
        uuid_real_alheio = str(self.perfil_id_de("own-url-a@test.com"))
        tentativas = [
            uuid_real_alheio,
            uuid_real_alheio.upper(),
            f"{uuid_real_alheio}/",
            str(uuid_lib.uuid4()),
            "nao-e-um-uuid",
        ]
        for alvo in tentativas:
            resposta = self.client.get(f"/api/v1/ownership/test/perfil/{alvo}", headers=cabecalhos)
            self.assertEqual(resposta.status_code, 404, alvo)
            self.assertNotIn("own-url-a", resposta.text.lower())

    # --- 3: não autenticado ---

    def test_05_nao_autenticado_recebe_401_sem_vazar_dados(self):
        self.garantir_perfil("own-anon@test.com")
        perfil_id = self.perfil_id_de("own-anon@test.com")
        leitura = self.client.get(f"/api/v1/ownership/test/perfil/{perfil_id}")
        escrita = self.client.put(
            f"/api/v1/ownership/test/perfil/{perfil_id}", json={"telefone": "11999999999"}
        )
        self.assertEqual(leitura.status_code, 401)
        self.assertEqual(escrita.status_code, 401)
        texto = (leitura.text + escrita.text).lower()
        self.assertNotIn(DADOS_PERFIL["telefone"], texto)
        self.assertNotIn(DADOS_PERFIL["nome_razao_social"].lower(), texto)

    # --- 4: manipulação de recurso alheio ---

    def test_06_alterar_recurso_alheio_negado_e_banco_intacto(self):
        self.garantir_perfil("own-alvo@test.com")
        self.garantir_perfil("own-atk@test.com")
        perfil_alheio = self.perfil_id_de("own-alvo@test.com")
        telefone_original = self.perfil_do_banco("own-alvo@test.com").telefone

        resposta = self.client.put(
            f"/api/v1/ownership/test/perfil/{perfil_alheio}",
            json={"telefone": "11900000000"},
            headers=self.headers_de("own-atk@test.com"),
        )
        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(resposta.json(), {"detail": "Recurso não encontrado."})

        perfil_apos = self.perfil_do_banco("own-alvo@test.com")
        self.assertEqual(perfil_apos.telefone, telefone_original)
        dono = self.client.get(
            f"/api/v1/ownership/test/perfil/{perfil_alheio}",
            headers=self.headers_de("own-alvo@test.com"),
        )
        self.assertEqual(dono.json()["telefone"], telefone_original)

    # --- 6: ownership forjado no corpo/query ---

    def test_07_user_id_no_corpo_ou_query_nao_assume_propriedade(self):
        self.garantir_perfil("own-forjado@test.com")
        self.garantir_perfil("own-falsario@test.com")
        perfil_alheio = self.perfil_id_de("own-forjado@test.com")
        falsario_id = None
        with sessionmaker(bind=self.engine)() as db:
            falsario_id = db.scalars(
                select(User).where(User.email == "own-falsario@test.com")
            ).first().id

        corpo = self.client.put(
            f"/api/v1/ownership/test/perfil/{perfil_alheio}",
            json={"telefone": "11911111111", "user_id": falsario_id},
            headers=self.headers_de("own-falsario@test.com"),
        )
        self.assertEqual(corpo.status_code, 422)

        query = self.client.get(
            f"/api/v1/ownership/test/perfil/{perfil_alheio}?user_id={falsario_id}",
            headers=self.headers_de("own-falsario@test.com"),
        )
        self.assertEqual(query.status_code, 404)

        vitima = self.perfil_do_banco("own-forjado@test.com")
        self.assertNotEqual(vitima.user_id, falsario_id)
        self.assertEqual(vitima.telefone, DADOS_PERFIL["telefone"])

    # --- 7: administrador segue a documentação (sem privilégio inventado) ---

    def test_08_administrador_nao_acessa_nem_altera_recurso_alheio(self):
        self.garantir_perfil("own-admin-alvo@test.com")
        self.criar_admin_direto_no_banco("own-admin@test.com")
        cabecalhos_admin = self.headers_de("own-admin@test.com")
        perfil_alheio = self.perfil_id_de("own-admin-alvo@test.com")
        telefone_original = self.perfil_do_banco("own-admin-alvo@test.com").telefone

        leitura = self.client.get(
            f"/api/v1/ownership/test/perfil/{perfil_alheio}", headers=cabecalhos_admin
        )
        escrita = self.client.put(
            f"/api/v1/ownership/test/perfil/{perfil_alheio}",
            json={"telefone": "11922222222"},
            headers=cabecalhos_admin,
        )
        self.assertEqual(leitura.status_code, 403)
        self.assertEqual(escrita.status_code, 403)
        self.assertEqual(self.perfil_do_banco("own-admin-alvo@test.com").telefone, telefone_original)


if __name__ == "__main__":
    unittest.main()
