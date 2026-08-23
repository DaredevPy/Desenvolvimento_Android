# backend/tests/test_conferencia.py
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

from backend.app.main import app
from backend.db import session as db_session
from backend.db.models import Base, Collection, CollectionItemChecked, CollectionItemDeclared, Tire

SECRET_TESTE = "chave-de-teste-com-mais-de-32-bytes-para-hmac-sha256-0123456789"

SENHA = "senha@123"
DADOS_PERFIL = {"nome_razao_social": "Pneus Conferidos LTDA", "telefone": "(11) 98888-7777"}
_CPF_SEQ = count(40_000_000_000_009, 17)


def payload_pneu(**extras):
    base = {"marca": "Michelin", "medida": "275/80R22.5", "dot": "2526"}
    base.update(extras)
    return base


class TestConferencia(unittest.TestCase):
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
            dados["dados_veiculo_json"] = {"placa": "DEF2E34", "tipo": "truck"}
        resposta = self.client.post(
            f"/api/v1/profile/{rota}", json=dados, headers=self.headers_de(email)
        )
        self.assertIn(resposta.status_code, (201, 409), resposta.text)

    def criar_coleta_solicitada(self, cliente="conf-cliente@test.com"):
        self.garantir_perfil(cliente)
        resposta = self.client.post(
            "/api/v1/collections",
            json={
                "endereco_origem_json": {"rua": "Rua da Borracharia", "numero": "50", "cidade": "Santos"},
                "data_agendada": datetime.now(timezone.utc).isoformat(),
                "itens": [
                    {"marca": "Michelin", "dimensao": "275/80R22.5", "quantidade_declarada": 250}
                ],
            },
            headers=self.headers_de(cliente),
        )
        self.assertEqual(resposta.status_code, 201, resposta.text)
        return resposta.json()

    def levar_ate_conferencia(self, cliente, prestador):
        coleta = self.criar_coleta_solicitada(cliente)
        self.garantir_perfil(prestador, rota="provider")
        cabecalhos = self.headers_de(prestador)
        self.assertEqual(
            self.client.post(f"/api/v1/collections/{coleta['id']}/aceitar", headers=cabecalhos).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/collections/{coleta['id']}/status",
                json={"novo_status": "EM_DESLOCAMENTO"},
                headers=cabecalhos,
            ).status_code,
            200,
        )
        return coleta["id"], cabecalhos

    def pneus_no_banco(self, coleta_id):
        with sessionmaker(bind=self.engine)() as db:
            return db.scalars(select(Tire).where(Tire.collection_id == coleta_id)).all()

    # --- início da conferência ---

    def test_01_prestador_atribuido_inicia_conferencia_sem_redigitacao(self):
        coleta_id, cabecalhos = self.levar_ate_conferencia("conf-inic-c@test.com", "conf-inic-p@test.com")
        resposta = self.client.post(f"/api/v1/collections/{coleta_id}/conferencia/iniciar", headers=cabecalhos)
        self.assertEqual(resposta.status_code, 200, resposta.text)
        corpo = resposta.json()
        self.assertEqual(corpo["status"], "EM_CONFERENCIA")
        self.assertEqual(corpo["itens_declarados"][0]["quantidade_declarada"], 250)

        with sessionmaker(bind=self.engine)() as db:
            self.assertEqual(db.get(Collection, coleta_id).status, "EM_CONFERENCIA")

    def test_02_outro_prestador_nao_inicia_e_inexistente_e_indistinguivel_404(self):
        coleta_id, _ = self.levar_ate_conferencia("conf-out-c@test.com", "conf-out-p1@test.com")
        self.garantir_perfil("conf-out-p2@test.com", rota="provider")
        intruso = self.headers_de("conf-out-p2@test.com")

        alheia = self.client.post(f"/api/v1/collections/{coleta_id}/conferencia/iniciar", headers=intruso)
        inexistente = self.client.post(
            f"/api/v1/collections/{uuid_lib.uuid4()}/conferencia/iniciar", headers=intruso
        )
        self.assertEqual(alheia.status_code, 404)
        self.assertEqual(inexistente.status_code, 404)
        self.assertEqual(alheia.json(), inexistente.json())

    def test_03_cliente_nao_inicia_conferencia_403(self):
        coleta_id, _ = self.levar_ate_conferencia("conf-cl-c@test.com", "conf-cl-p@test.com")
        resposta = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/iniciar",
            headers=self.headers_de("conf-cl-c@test.com"),
        )
        self.assertEqual(resposta.status_code, 403)

    def test_04_operacoes_fora_do_estado_correto_rejeitadas_409(self):
        coleta_id, cabecalhos = self.levar_ate_conferencia("conf-est-c@test.com", "conf-est-p@test.com")
        antes_da_conferencia = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/pneus",
            json={"pneus": [payload_pneu()]},
            headers=cabecalhos,
        )
        self.assertEqual(antes_da_conferencia.status_code, 409)

        self.assertEqual(
            self.client.post(f"/api/v1/collections/{coleta_id}/conferencia/iniciar", headers=cabecalhos).status_code,
            200,
        )
        repetido = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/iniciar", headers=cabecalhos
        )
        self.assertEqual(repetido.status_code, 409)

    # --- registro individual ---

    def test_05_pneus_persistem_individualmente_com_uuid_proprio(self):
        coleta_id, cabecalhos = self.levar_ate_conferencia("conf-reg-c@test.com", "conf-reg-p@test.com")
        self.client.post(f"/api/v1/collections/{coleta_id}/conferencia/iniciar", headers=cabecalhos)
        resposta = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/pneus",
            json={
                "pneus": [
                    {**payload_pneu(), "numero_fogo": "ABC123"},
                    {**payload_pneu(dot="1012"), "numero_fogo": "DEF456"},
                ]
            },
            headers=cabecalhos,
        )
        self.assertEqual(resposta.status_code, 201, resposta.text)
        ids = [pneu["id"] for pneu in resposta.json()]
        self.assertEqual(len(set(ids)), 2)

        pneus_db = self.pneus_no_banco(coleta_id)
        self.assertEqual(len(pneus_db), 2)
        antigo = next(p for p in pneus_db if p.numero_fogo == "DEF456")
        self.assertGreaterEqual(float(antigo.idade_calculada_anos), 10.0)
        self.assertTrue(antigo.alerta_idade_obsoleto)

    def test_06_quinhentos_pneus_com_mesmo_dot_sao_aceitos(self):
        coleta_id, cabecalhos = self.levar_ate_conferencia("conf-dot-c@test.com", "conf-dot-p@test.com")
        self.client.post(f"/api/v1/collections/{coleta_id}/conferencia/iniciar", headers=cabecalhos)
        lote = [
            payload_pneu(numero_fogo=f"FOGO-{i:04d}") for i in range(1, 501)
        ]
        resposta = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/pneus",
            json={"pneus": lote},
            headers=cabecalhos,
        )
        self.assertEqual(resposta.status_code, 201, resposta.text[:300])

        pneus_db = self.pneus_no_banco(coleta_id)
        self.assertEqual(len(pneus_db), 500)
        self.assertTrue(all(p.dot == "2526" for p in pneus_db))
        self.assertEqual(len({p.id for p in pneus_db}), 500)

    def test_07_dois_pneus_com_mesmo_dot_sem_numero_fogo_validos(self):
        coleta_id, cabecalhos = self.levar_ate_conferencia("conf-dupdot-c@test.com", "conf-dupdot-p@test.com")
        self.client.post(f"/api/v1/collections/{coleta_id}/conferencia/iniciar", headers=cabecalhos)
        resposta = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/pneus",
            json={"pneus": [payload_pneu(), payload_pneu()]},
            headers=cabecalhos,
        )
        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(len(self.pneus_no_banco(coleta_id)), 2)

    def test_08_numero_fogo_duplicado_na_mesma_coleta_bloqueado_definitivamente(self):
        coleta_id, cabecalhos = self.levar_ate_conferencia("conf-nfdup-c@test.com", "conf-nfdup-p@test.com")
        self.client.post(f"/api/v1/collections/{coleta_id}/conferencia/iniciar", headers=cabecalhos)

        primeiro = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/pneus",
            json={"pneus": [payload_pneu(numero_fogo="ABC123")]},
            headers=cabecalhos,
        )
        self.assertEqual(primeiro.status_code, 201)

        segundo = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/pneus",
            json={"pneus": [payload_pneu(numero_fogo="ABC123")]},
            headers=cabecalhos,
        )
        self.assertEqual(segundo.status_code, 409)
        self.assertIn("duplicado", segundo.json()["detail"].lower())
        self.assertEqual(len(self.pneus_no_banco(coleta_id)), 1)

        mesmo_lote = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/pneus",
            json={"pneus": [payload_pneu(numero_fogo="XYZ789"), payload_pneu(numero_fogo="XYZ789")]},
            headers=cabecalhos,
        )
        self.assertEqual(mesmo_lote.status_code, 409)

    def test_09_mesmo_numero_fogo_em_coletas_diferentes_permitido(self):
        coleta_a, cabecalhos = self.levar_ate_conferencia("conf-multi-c1@test.com", "conf-multi-p@test.com")
        self.client.post(f"/api/v1/collections/{coleta_a}/conferencia/iniciar", headers=cabecalhos)
        coleta_b, _ = self.levar_ate_conferencia("conf-multi-c2@test.com", "conf-multi-p@test.com")
        self.client.post(f"/api/v1/collections/{coleta_b}/conferencia/iniciar", headers=cabecalhos)

        for coleta in (coleta_a, coleta_b):
            resposta = self.client.post(
                f"/api/v1/collections/{coleta}/conferencia/pneus",
                json={"pneus": [payload_pneu(numero_fogo="ABC123")]},
                headers=cabecalhos,
            )
            self.assertEqual(resposta.status_code, 201, resposta.text)

        with sessionmaker(bind=self.engine)() as db:
            total = db.scalars(
                select(Tire).where(
                    Tire.numero_fogo == "ABC123",
                    Tire.collection_id.in_([coleta_a, coleta_b]),
                )
            ).all()
        self.assertEqual(len(total), 2)

    # --- número de fogo ilegível ---

    def test_10_ilegivel_exige_foto_e_observacao_e_proibe_numero(self):
        coleta_id, cabecalhos = self.levar_ate_conferencia("conf-ileg-c@test.com", "conf-ileg-p@test.com")
        self.client.post(f"/api/v1/collections/{coleta_id}/conferencia/iniciar", headers=cabecalhos)

        sem_evidencia = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/pneus",
            json={"pneus": [payload_pneu(numero_fogo_ilegivel=True)]},
            headers=cabecalhos,
        )
        self.assertEqual(sem_evidencia.status_code, 422)

        com_numero = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/pneus",
            json={
                "pneus": [
                    {
                        **payload_pneu(),
                        "numero_fogo": "ABC123",
                        "numero_fogo_ilegivel": True,
                        "observacoes": "Marcação desgastada",
                        "foto_pneu_url": "https://fotos.teste/abc.jpg",
                    }
                ]
            },
            headers=cabecalhos,
        )
        self.assertEqual(com_numero.status_code, 422)

        valido = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/pneus",
            json={
                "pneus": [
                    {
                        **payload_pneu(),
                        "numero_fogo_ilegivel": True,
                        "observacoes": "Marcação desgastada pelo uso",
                        "foto_pneu_url": "https://fotos.teste/abc.jpg",
                    }
                ]
            },
            headers=cabecalhos,
        )
        self.assertEqual(valido.status_code, 201, valido.text)
        pneu_db = self.pneus_no_banco(coleta_id)[0]
        self.assertTrue(pneu_db.numero_fogo_ilegivel)
        self.assertIsNone(pneu_db.numero_fogo)

    # --- quantidades e divergência ---

    def test_11_quantidade_declarada_preservada_apos_registros(self):
        coleta_id, cabecalhos = self.levar_ate_conferencia("conf-pres-c@test.com", "conf-pres-p@test.com")
        self.client.post(f"/api/v1/collections/{coleta_id}/conferencia/iniciar", headers=cabecalhos)
        self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/pneus",
            json={"pneus": [payload_pneu(numero_fogo=f"NF-{i}") for i in range(247)]},
            headers=cabecalhos,
        )

        with sessionmaker(bind=self.engine)() as db:
            itens_db = db.scalars(
                select(CollectionItemDeclared).where(CollectionItemDeclared.collection_id == coleta_id)
            ).all()
        self.assertEqual(len(itens_db), 1)
        self.assertEqual(itens_db[0].quantidade_declarada, 250)
        self.assertEqual(len(self.pneus_no_banco(coleta_id)), 247)

    def test_12_divergencia_registrada_com_justificativa_e_foto(self):
        coleta_id, cabecalhos = self.levar_ate_conferencia("conf-div-c@test.com", "conf-div-p@test.com")
        self.client.post(f"/api/v1/collections/{coleta_id}/conferencia/iniciar", headers=cabecalhos)
        self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/pneus",
            json={"pneus": [payload_pneu(numero_fogo=f"NF-{i}") for i in range(3)]},
            headers=cabecalhos,
        )
        resposta = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/concluir",
            json={
                "quantidade_conferida": 3,
                "quantidade_coletada": 3,
                "justificativa_divergencia": "Cliente informou 250; apenas 3 disponíveis no local.",
                "fotos_divergencia_json": {"fotos": ["https://fotos.teste/divergencia1.jpg"]},
            },
            headers=cabecalhos,
        )
        self.assertEqual(resposta.status_code, 200, resposta.text)
        self.assertEqual(resposta.json()["status"], "CARREGADA")

        with sessionmaker(bind=self.engine)() as db:
            verificacao = db.scalars(
                select(CollectionItemChecked).where(CollectionItemChecked.collection_id == coleta_id)
            ).first()
            self.assertIsNotNone(verificacao)
            self.assertEqual(verificacao.quantidade_conferida, 3)
            self.assertEqual(verificacao.justificativa_divergencia[:8], "Cliente ")
            self.assertEqual(db.get(Collection, coleta_id).status, "CARREGADA")

        repetida = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/concluir",
            json={"quantidade_conferida": 3, "quantidade_coletada": 3},
            headers=cabecalhos,
        )
        self.assertEqual(repetida.status_code, 409)

    def test_13_divergencia_sem_justificativa_ou_foto_rejeitada_422(self):
        coleta_id, cabecalhos = self.levar_ate_conferencia("conf-evic-c@test.com", "conf-evic-p@test.com")
        self.client.post(f"/api/v1/collections/{coleta_id}/conferencia/iniciar", headers=cabecalhos)
        self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/pneus",
            json={"pneus": [payload_pneu(numero_fogo="NF-1")]},
            headers=cabecalhos,
        )
        casos = [
            {"quantidade_conferida": 1, "quantidade_coletada": 1},
            {
                "quantidade_conferida": 1,
                "quantidade_coletada": 1,
                "justificativa_divergencia": "Faltam pneus.",
            },
            {
                "quantidade_conferida": 1,
                "quantidade_coletada": 1,
                "fotos_divergencia_json": {},
            },
        ]
        for caso in casos:
            resposta = self.client.post(
                f"/api/v1/collections/{coleta_id}/conferencia/concluir",
                json=caso,
                headers=cabecalhos,
            )
            self.assertEqual(resposta.status_code, 422, caso)

    def test_14_sem_divergencia_nao_exige_evidencia(self):
        coleta_id, cabecalhos = self.levar_ate_conferencia("conf-ok-c@test.com", "conf-ok-p@test.com")
        self.client.post(f"/api/v1/collections/{coleta_id}/conferencia/iniciar", headers=cabecalhos)
        self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/pneus",
            json={"pneus": [payload_pneu(numero_fogo=f"NF-{i}") for i in range(250)]},
            headers=cabecalhos,
        )
        resposta = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/concluir",
            json={"quantidade_conferida": 250, "quantidade_coletada": 250},
            headers=cabecalhos,
        )
        self.assertEqual(resposta.status_code, 200, resposta.text)

    def test_15_quantidade_coletada_deve_corresponder_aos_pneus_registrados(self):
        coleta_id, cabecalhos = self.levar_ate_conferencia("conf-count-c@test.com", "conf-count-p@test.com")
        self.client.post(f"/api/v1/collections/{coleta_id}/conferencia/iniciar", headers=cabecalhos)
        self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/pneus",
            json={"pneus": [payload_pneu(numero_fogo=f"NF-{i}") for i in range(3)]},
            headers=cabecalhos,
        )
        resposta = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/concluir",
            json={
                "quantidade_conferida": 5,
                "quantidade_coletada": 5,
                "justificativa_divergencia": "Contagem manual divergiu.",
                "fotos_divergencia_json": {"fotos": ["https://fotos.teste/x.jpg"]},
            },
            headers=cabecalhos,
        )
        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(len(self.pneus_no_banco(coleta_id)), 3)
        with sessionmaker(bind=self.engine)() as db:
            self.assertEqual(db.get(Collection, coleta_id).status, "EM_CONFERENCIA")

    # --- idade do DOT calculada no backend ---

    def test_16_idade_calculada_no_backend_e_cliente_nao_envia_campos_proibidos(self):
        coleta_id, cabecalhos = self.levar_ate_conferencia("conf-idade-c@test.com", "conf-idade-p@test.com")
        self.client.post(f"/api/v1/collections/{coleta_id}/conferencia/iniciar", headers=cabecalhos)

        for campos_proibidos in (
            {"idade_calculada_anos": 0.0},
            {"alerta_idade_obsoleto": False},
            {"semana_fabricacao": 25},
            {"ano_fabricacao": 26},
            {"collection_id": str(uuid_lib.uuid4())},
            {"provider_id": str(uuid_lib.uuid4())},
        ):
            tentativa = self.client.post(
                f"/api/v1/collections/{coleta_id}/conferencia/pneus",
                json={"pneus": [{**payload_pneu(dot="1015"), **campos_proibidos}]},
                headers=cabecalhos,
            )
            self.assertEqual(tentativa.status_code, 422, campos_proibidos)

        resposta = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/pneus",
            json={"pneus": [{**payload_pneu(dot="1015")}]},
            headers=cabecalhos,
        )
        self.assertEqual(resposta.status_code, 201)
        pneu = resposta.json()[0]
        ano_referencia = datetime.now(timezone.utc).year
        idade_esperada = float(ano_referencia - 2015)
        if datetime.now(timezone.utc).isocalendar().week < 10:
            idade_esperada -= 1.0
        self.assertEqual(pneu["idade_calculada_anos"], idade_esperada)
        self.assertTrue(pneu["alerta_idade_obsoleto"])

    def test_17_dot_formato_invalido_rejeitado_422(self):
        coleta_id, cabecalhos = self.levar_ate_conferencia("conf-dotinv-c@test.com", "conf-dotinv-p@test.com")
        self.client.post(f"/api/v1/collections/{coleta_id}/conferencia/iniciar", headers=cabecalhos)
        for dot_invalido in ("252", "25266", "AB26", "0026", "2553x"):
            tentativa = self.client.post(
                f"/api/v1/collections/{coleta_id}/conferencia/pneus",
                json={"pneus": [payload_pneu(dot=dot_invalido)]},
                headers=cabecalhos,
            )
            self.assertEqual(tentativa.status_code, 422, dot_invalido)

    # --- ownership dos pneus ---

    def test_18_prestador_errado_nao_acessa_pneus_e_cliente_nao_acessa_conferencia(self):
        coleta_id, _ = self.levar_ate_conferencia("conf-own-c@test.com", "conf-own-p1@test.com")
        self.client.post(f"/api/v1/collections/{coleta_id}/conferencia/iniciar", headers=self.headers_de("conf-own-p1@test.com"))
        self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/pneus",
            json={"pneus": [payload_pneu(numero_fogo="NF-1")]},
            headers=self.headers_de("conf-own-p1@test.com"),
        )

        self.garantir_perfil("conf-own-p2@test.com", rota="provider")
        intruso = self.headers_de("conf-own-p2@test.com")
        leitura_intrusa = self.client.get(f"/api/v1/collections/{coleta_id}/conferencia/pneus", headers=intruso)
        leitura_vazia = self.client.get(
            f"/api/v1/collections/{uuid_lib.uuid4()}/conferencia/pneus", headers=intruso
        )
        escrita_intrusa = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/pneus",
            json={"pneus": [payload_pneu()]},
            headers=intruso,
        )
        self.assertEqual(leitura_intrusa.status_code, 404)
        self.assertEqual(leitura_vazia.status_code, 404)
        self.assertEqual(leitura_intrusa.json(), leitura_vazia.json())
        self.assertEqual(escrita_intrusa.status_code, 404)
        self.assertNotIn("NF-1", leitura_intrusa.text)

        cliente = self.headers_de("conf-own-c@test.com")
        self.assertEqual(
            self.client.get(f"/api/v1/collections/{coleta_id}/conferencia/pneus", headers=cliente).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/collections/{coleta_id}/conferencia/concluir",
                json={"quantidade_conferida": 1, "quantidade_coletada": 1},
                headers=cliente,
            ).status_code,
            403,
        )


if __name__ == "__main__":
    unittest.main()
