# backend/tests/test_idempotencia.py
import os
import tempfile
import threading
import unittest
import uuid as uuid_lib
from datetime import datetime, timezone
from itertools import count
from unittest import mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from backend.app.main import app
from backend.db import session as db_session
from backend.db.models import Base, Collection, Tire

SECRET_TESTE = "chave-de-teste-com-mais-de-32-bytes-para-hmac-sha256-0123456789"

SENHA = "senha@123"
DADOS_PERFIL = {"nome_razao_social": "Idempotencia Teste LTDA", "telefone": "(11) 95555-4444"}
_CPF_SEQ = count(10_000_000_001, 37)
_CHAVE_A = "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
_CHAVE_B = "0f8fad5b-d9cb-469f-a165-70867728950e"


class TestIdempotencia(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._secret_original = os.environ.get("SECRET_KEY")
        os.environ["SECRET_KEY"] = SECRET_TESTE
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        if cls._secret_original is None:
            del os.environ["SECRET_KEY"]
        else:
            os.environ["SECRET_KEY"] = cls._secret_original

    def setUp(self):
        # Arquivo + NullPool: uma conexão por requisição, como no PostgreSQL.
        # StaticPool compartilharia UMA conexão sqlite entre as threads do
        # teste de corrida e invalidaria a prova de concorrência.
        self._arquivo_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._arquivo_db.close()
        self.engine = create_engine(
            f"sqlite:///{self._arquivo_db.name}",
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
        )
        Base.metadata.create_all(self.engine)
        self._patcher = mock.patch.object(
            db_session, "SessionLocal", sessionmaker(bind=self.engine)
        )
        self._patcher.start()
        # Congela o timestamp do payload: retries reais reenviam bytes idênticos.
        self._agora = datetime.now(timezone.utc).isoformat()

    def tearDown(self):
        self._patcher.stop()
        self.engine.dispose()
        os.unlink(self._arquivo_db.name)

    # --- auxiliares ---

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
            dados["dados_veiculo_json"] = {"placa": "IDM1C33", "tipo": "truck"}
        resposta = self.client.post(
            f"/api/v1/profile/{rota}", json=dados, headers=self.headers_de(email)
        )
        self.assertIn(resposta.status_code, (201, 409), resposta.text)

    def payload_coleta(self, **campos):
        base = {
            "endereco_origem_json": {"rua": "Rua da Idempotência", "numero": "12", "cidade": "Praia Grande"},
            "data_agendada": self._agora,
            "itens": [
                {"marca": "Goodyear", "dimensao": "275/80R22.5", "quantidade_declarada": 100}
            ],
        }
        base.update(campos)
        return base

    def criar(self, cabecalhos, payload=None, chave=None):
        cabecalhos = dict(cabecalhos)
        if chave is not None:
            cabecalhos["X-Idempotency-Key"] = chave
        return self.client.post(
            "/api/v1/collections", json=payload or self.payload_coleta(), headers=cabecalhos
        )

    def coletas_no_banco(self, chave=None):
        with sessionmaker(bind=self.engine)() as db:
            consulta = select(Collection)
            if chave is not None:
                consulta = consulta.where(Collection.idempotency_key == chave)
            return db.scalars(consulta.order_by(Collection.created_at.asc())).all()

    # --- comportamento básico ---

    def test_01_primeira_requisicao_com_chave_executa_normalmente(self):
        self.garantir_perfil("idm-c1@test.com")
        resposta = self.criar(self.headers_de("idm-c1@test.com"), chave=_CHAVE_A)
        self.assertEqual(resposta.status_code, 201, resposta.text)
        coletas = self.coletas_no_banco(_CHAVE_A)
        self.assertEqual(len(coletas), 1)
        self.assertIsNotNone(coletas[0].idempotency_request_hash)
        self.assertIsNotNone(coletas[0].idempotency_response_json)

    def test_02_reenvio_da_mesma_operacao_nao_duplica(self):
        self.garantir_perfil("idm-c2@test.com")
        cabecalhos = self.headers_de("idm-c2@test.com")
        primeira = self.criar(cabecalhos, chave=_CHAVE_A)
        self.assertEqual(primeira.status_code, 201, primeira.text)
        segunda = self.criar(cabecalhos, chave=_CHAVE_A)
        # Doc 09 §4.1: replay devolve a resposta armazenada com HTTP 200.
        self.assertEqual(segunda.status_code, 200, segunda.text)
        self.assertEqual(primeira.json(), segunda.json())
        self.assertEqual(len(self.coletas_no_banco()), 1)

    def test_03_mesma_chave_com_operacao_diferente_rejeitada(self):
        self.garantir_perfil("idm-c3@test.com")
        cabecalhos = self.headers_de("idm-c3@test.com")
        primeira = self.criar(cabecalhos, chave=_CHAVE_A)
        self.assertEqual(primeira.status_code, 201)
        divergente = self.payload_coleta(
            itens=[{"marca": "Goodyear", "dimensao": "275/80R22.5", "quantidade_declarada": 250}]
        )
        resposta = self.criar(cabecalhos, divergente, chave=_CHAVE_A)
        self.assertEqual(resposta.status_code, 409, resposta.text)
        self.assertIn("diferente", resposta.json()["detail"])
        self.assertEqual(len(self.coletas_no_banco()), 1)

    def test_04_usuario_b_nao_reutiliza_chave_do_usuario_a(self):
        self.garantir_perfil("idm-a4@test.com")
        self.garantir_perfil("idm-b4@test.com")
        self.assertEqual(
            self.criar(self.headers_de("idm-a4@test.com"), chave=_CHAVE_A).status_code, 201
        )
        resposta = self.criar(self.headers_de("idm-b4@test.com"), chave=_CHAVE_A)
        # Anti-enumeração: chave alheia é indistinguível de inexistente.
        self.assertEqual(resposta.status_code, 404, resposta.text)
        self.assertEqual(resposta.json()["detail"], "Recurso não encontrado.")
        self.assertEqual(len(self.coletas_no_banco()), 1)

    def test_05_chave_invalida_ou_nao_v4_rejeitada(self):
        self.garantir_perfil("idm-c5@test.com")
        cabecalhos = self.headers_de("idm-c5@test.com")
        resposta = self.criar(cabecalhos, chave="nao-e-uuid")
        self.assertEqual(resposta.status_code, 422)
        resposta = self.criar(cabecalhos, chave=str(uuid_lib.uuid1()))
        self.assertEqual(resposta.status_code, 422)
        self.assertEqual(len(self.coletas_no_banco()), 0)

    def test_06_requests_simultaneos_criam_apenas_uma_coleta(self):
        self.garantir_perfil("idm-c6@test.com")
        cabecalhos = dict(self.headers_de("idm-c6@test.com"), **{"X-Idempotency-Key": _CHAVE_A})
        barreira = threading.Barrier(2)
        respostas = []

        def disparar():
            # Cliente HTTP próprio por thread: TestClient não é thread-safe.
            cliente_http = TestClient(app)
            corpo = self.payload_coleta()
            try:
                barreira.wait(timeout=10)
                respostas.append(cliente_http.post("/api/v1/collections", json=corpo, headers=cabecalhos))
            except Exception as erro:  # propaga falhas de thread p/ asserção
                respostas.append(erro)

        fios = [threading.Thread(target=disparar) for _ in range(2)]
        for fio in fios:
            fio.start()
        for fio in fios:
            fio.join(timeout=30)
        self.assertEqual(len(respostas), 2)
        for resposta in respostas:
            self.assertIn(resposta.status_code, (200, 201), str(resposta))
        self.assertEqual(len(self.coletas_no_banco(_CHAVE_A)), 1)
        self.assertEqual(len(self.coletas_no_banco()), 1)

    def test_07_falha_antes_do_commit_nao_consome_a_chave(self):
        self.garantir_perfil("idm-c7@test.com")
        cabecalhos = self.headers_de("idm-c7@test.com")
        quebrado = self.payload_coleta(
            itens=[{"marca": "Goodyear", "dimensao": "275/80R22.5", "quantidade_declarada": -1}]
        )
        self.assertEqual(self.criar(cabecalhos, quebrado, chave=_CHAVE_A).status_code, 422)
        self.assertEqual(len(self.coletas_no_banco()), 0)
        recuperacao = self.criar(cabecalhos, chave=_CHAVE_A)
        self.assertEqual(recuperacao.status_code, 201, recuperacao.text)
        self.assertEqual(len(self.coletas_no_banco(_CHAVE_A)), 1)

    def test_08_fluxo_sem_cabecalho_permanece_intacto(self):
        self.garantir_perfil("idm-c8@test.com")
        resposta = self.criar(self.headers_de("idm-c8@test.com"))
        self.assertEqual(resposta.status_code, 201, resposta.text)
        self.assertIn("codigo_identificador", resposta.json())
        coleta = self.coletas_no_banco()[0]
        self.assertIsNone(coleta.idempotency_key)
        self.assertIsNone(coleta.idempotency_request_hash)
        self.assertIsNone(coleta.idempotency_response_json)

    def test_09_replay_retorna_resposta_armazenada_mesmo_com_estado_avancado(self):
        self.garantir_perfil("idm-c9@test.com")
        self.garantir_perfil("idm-p9@test.com", rota="provider")
        cliente = self.headers_de("idm-c9@test.com")
        prestador = self.headers_de("idm-p9@test.com")
        primeira = self.criar(cliente, chave=_CHAVE_A)
        self.assertEqual(primeira.status_code, 201)
        coleta_id = primeira.json()["id"]
        self.assertEqual(
            self.client.post(f"/api/v1/collections/{coleta_id}/aceitar", headers=prestador).status_code,
            200,
        )
        replay = self.criar(cliente, chave=_CHAVE_A)
        self.assertEqual(replay.status_code, 200)
        # Resposta EXATA do primeiro processamento (doc 09 §4.1), não o estado atual.
        self.assertEqual(replay.json()["status"], "SOLICITADA")
        self.assertEqual(replay.json()["id"], coleta_id)
        with sessionmaker(bind=self.engine)() as db:
            estado_atual = db.get(Collection, coleta_id).status
        self.assertEqual(estado_atual, "ACEITA")

    # --- regras críticas preservadas ---

    def test_10_ownership_e_rbac_permanecem(self):
        self.garantir_perfil("idm-p10@test.com", rota="provider")
        resposta = self.criar(self.headers_de("idm-p10@test.com"))
        self.assertEqual(resposta.status_code, 403)
        self.garantir_perfil("idm-a10@test.com")
        self.garantir_perfil("idm-b10@test.com")
        criador = self.headers_de("idm-a10@test.com")
        outro = self.headers_de("idm-b10@test.com")
        coleta_id = self.criar(criador).json()["id"]
        leitura = self.client.get(f"/api/v1/collections/{coleta_id}", headers=outro)
        self.assertEqual(leitura.status_code, 404)

    def test_11_dot_repetido_continua_permitido(self):
        self.garantir_perfil("idm-c11@test.com")
        self.garantir_perfil("idm-p11@test.com", rota="provider")
        cliente = self.headers_de("idm-c11@test.com")
        prestador = self.headers_de("idm-p11@test.com")
        resposta = self.criar(cliente, chave=_CHAVE_A)
        coleta_id = resposta.json()["id"]
        self.client.post(f"/api/v1/collections/{coleta_id}/aceitar", headers=prestador)
        self.client.post(
            f"/api/v1/collections/{coleta_id}/status",
            json={"novo_status": "EM_DESLOCAMENTO"},
            headers=prestador,
        )
        self.client.post(f"/api/v1/collections/{coleta_id}/conferencia/iniciar", headers=prestador)
        pneus = [
            {"marca": "Goodyear", "medida": "275/80R22.5", "dot": "2526"},
            {"marca": "Goodyear", "medida": "275/80R22.5", "dot": "2526"},
        ]
        registrados = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/pneus",
            json={"pneus": pneus},
            headers=prestador,
        )
        self.assertEqual(registrados.status_code, 201, registrados.text)
        with sessionmaker(bind=self.engine)() as db:
            dots = db.scalars(select(Tire.dot).where(Tire.collection_id == coleta_id)).all()
        self.assertEqual(dots, ["2526", "2526"])

    def test_12_numero_fogo_duplicado_continua_bloqueado_na_mesma_coleta(self):
        self.garantir_perfil("idm-c12@test.com")
        self.garantir_perfil("idm-p12@test.com", rota="provider")
        cliente = self.headers_de("idm-c12@test.com")
        prestador = self.headers_de("idm-p12@test.com")
        coleta_id = self.criar(cliente, chave=_CHAVE_A).json()["id"]
        self.client.post(f"/api/v1/collections/{coleta_id}/aceitar", headers=prestador)
        self.client.post(
            f"/api/v1/collections/{coleta_id}/status",
            json={"novo_status": "EM_DESLOCAMENTO"},
            headers=prestador,
        )
        self.client.post(f"/api/v1/collections/{coleta_id}/conferencia/iniciar", headers=prestador)
        duplicado = [
            {"marca": "Goodyear", "medida": "275/80R22.5", "dot": "1012", "numero_fogo": "NF777"},
            {"marca": "Goodyear", "medida": "275/80R22.5", "dot": "1012", "numero_fogo": "NF777"},
        ]
        resposta = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/pneus",
            json={"pneus": duplicado},
            headers=prestador,
        )
        self.assertEqual(resposta.status_code, 409)
        with sessionmaker(bind=self.engine)() as db:
            total = len(db.scalars(select(Tire.id).where(Tire.collection_id == coleta_id)).all())
        self.assertEqual(total, 0)
