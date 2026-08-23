# backend/tests/test_collections.py
import os
import unittest
import uuid as uuid_lib
from datetime import datetime, timezone
from itertools import count
from unittest import mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.collections import _stmt_aceite
from backend.app.main import app
from backend.db import session as db_session
from backend.db.models import Base, Client, Collection, Profile, Provider, User

SECRET_TESTE = "chave-de-teste-com-mais-de-32-bytes-para-hmac-sha256-0123456789"

SENHA = "senha@123"
DADOS_PERFIL = {"nome_razao_social": "Transportadora Teste LTDA", "telefone": "(11) 98888-7777"}
_CPF_SEQ = count(50_000_000_000_007, 13)


def payload_coleta(**extras):
    base = {
        "endereco_origem_json": {"rua": "Rua da Oficina", "numero": "100", "cidade": "São Paulo"},
        "data_agendada": datetime.now(timezone.utc).isoformat(),
        "itens": [
            {"marca": "Michelin", "dimensao": "275/80R22.5", "quantidade_declarada": 250}
        ],
    }
    base.update(extras)
    return base


class TestCollections(unittest.TestCase):
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

    # --- auxiliares (cada teste garante seus próprios dados) ---

    def registrar(self, email, role):
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
        role = "PRESTADOR" if rota == "provider" else "CLIENTE"
        self.registrar(email, role)
        dados = {**DADOS_PERFIL, "cpf_cnpj": self.novo_cpf()}
        if rota == "provider":
            dados["dados_veiculo_json"] = {"placa": "ABC1D23", "tipo": "truck"}
        resposta = self.client.post(
            f"/api/v1/profile/{rota}", json=dados, headers=self.headers_de(email)
        )
        self.assertIn(resposta.status_code, (201, 409), resposta.text)

    def criar_coleta(self, email="col-cliente@test.com"):
        self.garantir_perfil(email)
        resposta = self.client.post(
            "/api/v1/collections", json=payload_coleta(), headers=self.headers_de(email)
        )
        self.assertEqual(resposta.status_code, 201, resposta.text)
        return resposta.json()

    def provider_id_de(self, email):
        with sessionmaker(bind=self.engine)() as db:
            user_id = db.scalars(select(User).where(User.email == email)).first().id
            return db.scalars(
                select(Provider).join(Profile, Provider.profile_id == Profile.id).where(Profile.user_id == user_id)
            ).first().id

    # --- criação ---

    def test_01_cliente_cria_coleta_solicitada_com_itens(self):
        corpo = self.criar_coleta()
        self.assertEqual(corpo["status"], "SOLICITADA")
        self.assertIsNone(corpo["provider_id"])
        self.assertTrue(corpo["codigo_identificador"].startswith("COL-"))
        self.assertEqual(len(corpo["itens"]), 1)
        self.assertEqual(corpo["itens"][0]["quantidade_declarada"], 250)

        with sessionmaker(bind=self.engine)() as db:
            coleta = db.get(Collection, corpo["id"])
            self.assertIsNotNone(coleta)
            client_id_esperado = db.scalars(
                select(Client).join(Profile, Client.profile_id == Profile.id).where(
                    Profile.user_id == db.scalars(select(User).where(User.email == "col-cliente@test.com")).first().id
                )
            ).first().id
            self.assertEqual(coleta.client_id, client_id_esperado)
            self.assertEqual(coleta.status, "SOLICITADA")
            self.assertEqual(len(coleta.items_declared), 1)

    def test_02_rotas_protegidas_sem_token_401(self):
        self.assertEqual(self.client.post("/api/v1/collections", json=payload_coleta()).status_code, 401)
        self.assertEqual(self.client.get("/api/v1/collections").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/collections/disponiveis").status_code, 401)
        self.assertEqual(
            self.client.post(f"/api/v1/collections/{uuid_lib.uuid4()}/aceitar").status_code, 401
        )

    def test_03_prestador_nao_cria_coleta_403(self):
        self.garantir_perfil("col-prest@test.com", rota="provider")
        resposta = self.client.post(
            "/api/v1/collections", json=payload_coleta(), headers=self.headers_de("col-prest@test.com")
        )
        self.assertEqual(resposta.status_code, 403)

    def test_04_cliente_sem_perfil_nao_cria_404(self):
        self.registrar("col-semperfil@test.com", "CLIENTE")
        resposta = self.client.post(
            "/api/v1/collections", json=payload_coleta(), headers=self.headers_de("col-semperfil@test.com")
        )
        self.assertEqual(resposta.status_code, 404)

    def test_05_campos_proibidos_e_invalidos_rejeitados_422(self):
        self.garantir_perfil("col-valid@test.com")
        cabecalhos = self.headers_de("col-valid@test.com")
        casos = [
            payload_coleta(client_id=str(uuid_lib.uuid4())),
            payload_coleta(provider_id=str(uuid_lib.uuid4())),
            payload_coleta(status="ACEITA"),
            payload_coleta(idempotency_key=str(uuid_lib.uuid4())),
            payload_coleta(snapshot_valor_cliente=100.0),
            payload_coleta(itens=[]),
            payload_coleta(itens=[{"marca": "X", "dimensao": "Y", "quantidade_declarada": 0}]),
            payload_coleta(itens=[{"marca": "X", "dimensao": "Y", "quantidade_declarada": -5}]),
            payload_coleta(data_agendada="2026-03-01T10:00:00"),
            payload_coleta(endereco_origem_json={}),
            payload_coleta(campo_inexistente="x"),
        ]
        for caso in casos:
            resposta = self.client.post("/api/v1/collections", json=caso, headers=cabecalhos)
            self.assertEqual(resposta.status_code, 422, caso)

    # --- consulta pelo cliente ---

    def test_06_cliente_lista_apenas_proprias_coletas(self):
        primeira = self.criar_coleta("col-lista-a@test.com")
        segunda = self.criar_coleta("col-lista-a@test.com")
        alheia = self.criar_coleta("col-lista-b@test.com")

        resposta = self.client.get("/api/v1/collections", headers=self.headers_de("col-lista-a@test.com"))
        self.assertEqual(resposta.status_code, 200)
        ids = {coleta["id"] for coleta in resposta.json()}
        self.assertIn(primeira["id"], ids)
        self.assertIn(segunda["id"], ids)
        self.assertNotIn(alheia["id"], ids)

    def test_07_coleta_alheia_e_inexistente_indistinguiveis_404(self):
        alheia = self.criar_coleta("col-detalhe-vitima@test.com")
        self.garantir_perfil("col-detalhe-inv@test.com")
        cabecalhos = self.headers_de("col-detalhe-inv@test.com")

        por_uuid_alheio = self.client.get(
            f"/api/v1/collections/{alheia['id']}", headers=cabecalhos
        )
        por_uuid_falso = self.client.get(
            f"/api/v1/collections/{uuid_lib.uuid4()}", headers=cabecalhos
        )
        self.assertEqual(por_uuid_alheio.status_code, 404)
        self.assertEqual(por_uuid_falso.status_code, 404)
        self.assertEqual(por_uuid_alheio.json(), por_uuid_falso.json())
        self.assertNotIn("Rua da Oficina", por_uuid_alheio.text)

    def test_08_dono_consulta_proprias_por_uuid(self):
        criada = self.criar_coleta()
        resposta = self.client.get(
            f"/api/v1/collections/{criada['id']}", headers=self.headers_de("col-cliente@test.com")
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["codigo_identificador"], criada["codigo_identificador"])
        self.assertEqual(resposta.json()["endereco_origem_json"]["cidade"], "São Paulo")

    # --- visão do prestador e aceite ---

    def test_09_prestador_visualiza_disponiveis_somente_solicitadas(self):
        disponivel = self.criar_coleta("col-disp-vitima@test.com")
        cancelada = self.criar_coleta("col-disp-cancel@test.com")
        cabecalhos_cancel = self.headers_de("col-disp-cancel@test.com")
        self.client.post(f"/api/v1/collections/{cancelada['id']}/cancelar", headers=cabecalhos_cancel)

        self.garantir_perfil("col-prestador@test.com", rota="provider")
        cabecalhos = self.headers_de("col-prestador@test.com")
        resposta = self.client.get("/api/v1/collections/disponiveis", headers=cabecalhos)
        self.assertEqual(resposta.status_code, 200)
        ids = {coleta["id"] for coleta in resposta.json()}
        self.assertIn(disponivel["id"], ids)
        self.assertNotIn(cancelada["id"], ids)
        itens = next(c for c in resposta.json() if c["id"] == disponivel["id"])["itens"]
        self.assertEqual(itens[0]["quantidade_declarada"], 250)

    def test_10_prestador_aceita_coleta_disponivel(self):
        criada = self.criar_coleta("col-aceite-vitima@test.com")
        self.garantir_perfil("col-aceite-prest@test.com", rota="provider")
        resposta = self.client.post(
            f"/api/v1/collections/{criada['id']}/aceitar",
            headers=self.headers_de("col-aceite-prest@test.com"),
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["status"], "ACEITA")

        with sessionmaker(bind=self.engine)() as db:
            coleta = db.get(Collection, criada["id"])
            self.assertEqual(coleta.status, "ACEITA")
            self.assertEqual(coleta.provider_id, self.provider_id_de("col-aceite-prest@test.com"))

    def test_11_segundo_aceite_da_mesma_coleta_rejeitado_409(self):
        criada = self.criar_coleta("col-seg-vitima@test.com")
        self.garantir_perfil("col-seg-p1@test.com", rota="provider")
        self.garantir_perfil("col-seg-p2@test.com", rota="provider")

        primeiro = self.client.post(
            f"/api/v1/collections/{criada['id']}/aceitar",
            headers=self.headers_de("col-seg-p1@test.com"),
        )
        segundo = self.client.post(
            f"/api/v1/collections/{criada['id']}/aceitar",
            headers=self.headers_de("col-seg-p2@test.com"),
        )
        self.assertEqual(primeiro.status_code, 200)
        self.assertEqual(segundo.status_code, 409)

        with sessionmaker(bind=self.engine)() as db:
            coleta = db.get(Collection, criada["id"])
            self.assertEqual(coleta.provider_id, self.provider_id_de("col-seg-p1@test.com"))

    def test_12_cliente_nao_aceita_coleta_403(self):
        criada = self.criar_coleta("col-cl-aceite@test.com")
        resposta = self.client.post(
            f"/api/v1/collections/{criada['id']}/aceitar",
            headers=self.headers_de("col-cl-aceite@test.com"),
        )
        self.assertEqual(resposta.status_code, 403)

    def test_13_mecanismo_transacional_garante_vencedor_unico_no_corrida(self):
        criada = self.criar_coleta("col-race-vitima@test.com")
        self.garantir_perfil("col-race-p1@test.com", rota="provider")
        self.garantir_perfil("col-race-p2@test.com", rota="provider")
        pid1 = self.provider_id_de("col-race-p1@test.com")
        pid2 = self.provider_id_de("col-race-p2@test.com")

        # Dois prestadores leem a mesma coleta SOLICITADA simultaneamente.
        fabrica = sessionmaker(bind=self.engine)
        with fabrica() as sessao_p1, fabrica() as sessao_p2:
            for sessao in (sessao_p1, sessao_p2):
                vista = sessao.get(Collection, criada["id"])
                self.assertEqual(vista.status, "SOLICITADA")
                self.assertIsNone(vista.provider_id)

            vencedor = sessao_p1.execute(_stmt_aceite(criada["id"], pid1))
            perdedor = sessao_p2.execute(_stmt_aceite(criada["id"], pid2))
            sessao_p1.commit()
            sessao_p2.commit()

        self.assertEqual(vencedor.rowcount, 1)
        self.assertEqual(perdedor.rowcount, 0)

        with fabrica() as db:
            coleta = db.get(Collection, criada["id"])
            self.assertEqual(coleta.provider_id, pid1)
            self.assertEqual(coleta.status, "ACEITA")

    def test_14_ids_forjados_nao_alteram_ownership(self):
        vitima = self.criar_coleta("col-forge-vitima@test.com")
        self.garantir_perfil("col-forge-inv@test.com")
        cabecalhos_inv = self.headers_de("col-forge-inv@test.com")

        falsificado = self.client.post(
            "/api/v1/collections",
            json=payload_coleta(client_id=vitima["id"]),
            headers=cabecalhos_inv,
        )
        self.assertEqual(falsificado.status_code, 422)

        aceite_forjado = self.client.post(
            "/api/v1/collections",
            json=payload_coleta(provider_id=str(uuid_lib.uuid4())),
            headers=cabecalhos_inv,
        )
        self.assertEqual(aceite_forjado.status_code, 422)

        cancelamento_alheio = self.client.post(
            f"/api/v1/collections/{vitima['id']}/cancelar", headers=cabecalhos_inv
        )
        inexistente = self.client.post(
            f"/api/v1/collections/{uuid_lib.uuid4()}/cancelar", headers=cabecalhos_inv
        )
        self.assertEqual(cancelamento_alheio.status_code, 404)
        self.assertEqual(inexistente.status_code, 404)
        self.assertEqual(cancelamento_alheio.json(), inexistente.json())

        # Prestador estranho não avança status de coleta atribuída a outro prestador.
        self.garantir_perfil("col-forge-p1@test.com", rota="provider")
        self.garantir_perfil("col-forge-p2@test.com", rota="provider")
        self.client.post(
            f"/api/v1/collections/{vitima['id']}/aceitar",
            headers=self.headers_de("col-forge-p1@test.com"),
        )
        avanco_alheio = self.client.post(
            f"/api/v1/collections/{vitima['id']}/status",
            json={"novo_status": "EM_DESLOCAMENTO"},
            headers=self.headers_de("col-forge-p2@test.com"),
        )
        self.assertEqual(avanco_alheio.status_code, 404)
        with sessionmaker(bind=self.engine)() as db:
            self.assertEqual(db.get(Collection, vitima["id"]).status, "ACEITA")

    # --- máquina de estados ---

    def test_15_transicoes_invalidas_rejeitadas_409(self):
        criada = self.criar_coleta("col-trans-vitima@test.com")
        self.garantir_perfil("col-trans-p@test.com", rota="provider")
        cabecalhos = self.headers_de("col-trans-p@test.com")

        salto_para_carregada = self.client.post(
            f"/api/v1/collections/{criada['id']}/status",
            json={"novo_status": "CARREGADA"},
            headers=cabecalhos,
        )
        self.assertEqual(salto_para_carregada.status_code, 404)

        self.client.post(f"/api/v1/collections/{criada['id']}/aceitar", headers=cabecalhos)
        salto_pos_aceite = self.client.post(
            f"/api/v1/collections/{criada['id']}/status",
            json={"novo_status": "CARREGADA"},
            headers=cabecalhos,
        )
        self.assertEqual(salto_pos_aceite.status_code, 409)

        status_forjado = self.client.post(
            f"/api/v1/collections/{criada['id']}/status",
            json={"novo_status": "FINALIZADA"},
            headers=cabecalhos,
        )
        self.assertIn(status_forjado.status_code, (409, 422))

        cliente_tenta_avancar = self.client.post(
            f"/api/v1/collections/{criada['id']}/status",
            json={"novo_status": "EM_DESLOCAMENTO"},
            headers=self.headers_de("col-trans-vitima@test.com"),
        )
        self.assertEqual(cliente_tenta_avancar.status_code, 403)

        cliente_cancela_aceita = self.client.post(
            f"/api/v1/collections/{criada['id']}/cancelar",
            headers=self.headers_de("col-trans-vitima@test.com"),
        )
        self.assertEqual(cliente_cancela_aceita.status_code, 409)

    def test_16_fluxo_valido_do_prestador_ate_carregada(self):
        criada = self.criar_coleta("col-fluxo-vitima@test.com")
        self.garantir_perfil("col-fluxo-p@test.com", rota="provider")
        cabecalhos = self.headers_de("col-fluxo-p@test.com")
        self.client.post(f"/api/v1/collections/{criada['id']}/aceitar", headers=cabecalhos)

        for status in ("EM_DESLOCAMENTO", "EM_CONFERENCIA", "CARREGADA"):
            resposta = self.client.post(
                f"/api/v1/collections/{criada['id']}/status",
                json={"novo_status": status},
                headers=cabecalhos,
            )
            self.assertEqual(resposta.status_code, 200, status)
            self.assertEqual(resposta.json()["status"], status)

        repetido = self.client.post(
            f"/api/v1/collections/{criada['id']}/status",
            json={"novo_status": "EM_DESLOCAMENTO"},
            headers=cabecalhos,
        )
        self.assertEqual(repetido.status_code, 409)
        with sessionmaker(bind=self.engine)() as db:
            self.assertEqual(db.get(Collection, criada["id"]).status, "CARREGADA")

    # --- cancelamento pelo dono ---

    def test_17_cliente_cancela_proprias_solicitadas(self):
        criada = self.criar_coleta("col-cancela@test.com")
        cabecalhos = self.headers_de("col-cancela@test.com")

        resposta = self.client.post(f"/api/v1/collections/{criada['id']}/cancelar", headers=cabecalhos)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["status"], "CANCELADA")

        repetida = self.client.post(f"/api/v1/collections/{criada['id']}/cancelar", headers=cabecalhos)
        self.assertEqual(repetida.status_code, 409)

        self.garantir_perfil("col-cancela-p@test.com", rota="provider")
        aceite_apos_cancel = self.headers_de("col-cancela-p@test.com")
        tentativa = self.client.post(
            f"/api/v1/collections/{criada['id']}/aceitar", headers=aceite_apos_cancel
        )
        self.assertEqual(tentativa.status_code, 409)

        disponiveis = self.client.get("/api/v1/collections/disponiveis", headers=aceite_apos_cancel)
        ids = {coleta["id"] for coleta in disponiveis.json()}
        self.assertNotIn(criada["id"], ids)


if __name__ == "__main__":
    unittest.main()
