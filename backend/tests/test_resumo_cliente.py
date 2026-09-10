# backend/tests/test_resumo_cliente.py
# Missão 56: CLIENTE dono de coleta FINALIZADA recebe os pneus conferidos
# no GET /api/v1/collections/{id} (Resumo/Comprovante — doc 05 Etapa 6 §1).
import os
import unittest
import uuid as uuid_lib
from datetime import date, datetime, timezone
from itertools import count
from unittest import mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import security
from backend.app.main import app
from backend.db import session as db_session
from backend.db.models import Base, User

SECRET_TESTE = "chave-de-teste-com-mais-de-32-bytes-para-hmac-sha256-0123456789"

SENHA = "senha@123"
DADOS_PERFIL = {"nome_razao_social": "Resumo Cliente LTDA", "telefone": "(11) 96666-5555"}
_CPF_SEQ = count(80_000_000_000_009, 13)
_NF_SEQ = count(900001)

CAMPOS_PNEU = {
    "dot",
    "marca",
    "medida",
    "numero_fogo",
    "numero_fogo_ilegivel",
    "idade_calculada_anos",
    "alerta_idade_obsoleto",
}


def payload_pneu(**extras):
    base = {"marca": "Michelin", "medida": "275/80R22.5", "dot": "2526"}
    base.update(extras)
    return base


class TestResumoCliente(unittest.TestCase):
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
        # Banco por teste: price_rules é global e a validação de sobreposição
        # impediria faixas de testes diferentes conviverem na mesma base.
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self._patcher = mock.patch.object(
            db_session, "SessionLocal", sessionmaker(bind=self.engine)
        )
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self.engine.dispose()

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
            dados["dados_veiculo_json"] = {"placa": "RC2A11", "tipo": "truck"}
        resposta = self.client.post(
            f"/api/v1/profile/{rota}", json=dados, headers=self.headers_de(email)
        )
        self.assertIn(resposta.status_code, (201, 409), resposta.text)

    def admin_headers(self, email):
        with sessionmaker(bind=self.engine)() as db:
            db.add(User(email=email, password_hash=security.hash_password(SENHA), role="ADMINISTRADOR"))
            db.commit()
        return self.headers_de(email)

    def criar_regra(self, cabecalhos, **campos):
        base = {
            "perfil_alvo": "CLIENTE",
            "faixa_inicio_quantidade": 0,
            "faixa_fim_quantidade": 10000,
            "valor_unitario": "4.00",
            "vigencia_inicio": date.today().isoformat(),
        }
        base.update(campos)
        return self.client.post("/api/v1/admin/pricing-rules", json=base, headers=cabecalhos)

    def coleta_carregada(self, cliente, prestador, registrados=3):
        """Cria coleta SOLICITADA e leva até CARREGADA com N pneus registrados."""
        self.garantir_perfil(cliente)
        resposta = self.client.post(
            "/api/v1/collections",
            json={
                "endereco_origem_json": {"rua": "Rua do Resumo", "numero": "7", "cidade": "Osasco"},
                "data_agendada": datetime.now(timezone.utc).isoformat(),
                "itens": [
                    {"marca": "Michelin", "dimensao": "275/80R22.5", "quantidade_declarada": 10}
                ],
            },
            headers=self.headers_de(cliente),
        )
        self.assertEqual(resposta.status_code, 201, resposta.text)
        coleta_id = resposta.json()["id"]
        self.garantir_perfil(prestador, rota="provider")
        cabecalhos = self.headers_de(prestador)
        self.assertEqual(
            self.client.post(f"/api/v1/collections/{coleta_id}/aceitar", headers=cabecalhos).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/collections/{coleta_id}/status",
                json={"novo_status": "EM_DESLOCAMENTO"},
                headers=cabecalhos,
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/collections/{coleta_id}/conferencia/iniciar", headers=cabecalhos
            ).status_code,
            200,
        )
        pneus = [
            payload_pneu(numero_fogo=f"{next(_NF_SEQ):06d}") for _ in range(registrados)
        ]
        resposta = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/pneus",
            json={"pneus": pneus},
            headers=cabecalhos,
        )
        self.assertEqual(resposta.status_code, 201, resposta.text)
        conclusao = {
            "quantidade_conferida": registrados,
            "quantidade_coletada": registrados,
            "justificativa_divergencia": "Cliente declarou 10; coletadas no local.",
            "fotos_divergencia_json": {"fotos": ["https://cdn.teste/resumo.jpg"]},
        }
        resposta = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/concluir",
            json=conclusao,
            headers=cabecalhos,
        )
        self.assertEqual(resposta.status_code, 200, resposta.text)
        return coleta_id, cabecalhos

    def finalizar_com_regras(self, coleta_id, cabecalhos):
        admin = self.admin_headers("rc-admin@test.com")
        self.assertEqual(self.criar_regra(admin).status_code, 201)
        self.assertEqual(
            self.criar_regra(admin, perfil_alvo="PRESTADOR", valor_unitario="2.50").status_code,
            201,
        )
        resposta = self.client.post(
            f"/api/v1/collections/{coleta_id}/finalizar", json={}, headers=cabecalhos
        )
        self.assertEqual(resposta.status_code, 200, resposta.text)
        self.assertEqual(resposta.json()["status"], "FINALIZADA")

    # --- casos da Missão 56 ---

    def test_01_dono_consulta_finalizada_e_recebe_pneus_conferidos(self):
        coleta_id, cabecalhos = self.coleta_carregada("rc-caso1-c@test.com", "rc-caso1-p@test.com")
        self.finalizar_com_regras(coleta_id, cabecalhos)

        resposta = self.client.get(
            f"/api/v1/collections/{coleta_id}", headers=self.headers_de("rc-caso1-c@test.com")
        )
        self.assertEqual(resposta.status_code, 200, resposta.text)
        corpo = resposta.json()
        self.assertEqual(corpo["status"], "FINALIZADA")
        pneus = corpo["pneus"]
        self.assertEqual(len(pneus), 3)
        for pneu in pneus:
            self.assertTrue(CAMPOS_PNEU.issubset(pneu.keys()), pneu)
            self.assertEqual(pneu["marca"], "Michelin")
            self.assertEqual(pneu["medida"], "275/80R22.5")
            self.assertEqual(pneu["dot"], "2526")
            self.assertIsNotNone(pneu["numero_fogo"])
            self.assertFalse(pneu["numero_fogo_ilegivel"])
            self.assertGreaterEqual(pneu["idade_calculada_anos"], 0.0)
            self.assertIn(pneu["alerta_idade_obsoleto"], (True, False))

    def test_02_nao_dono_nao_recebe_nada_404_anti_enumeracao(self):
        coleta_id, cabecalhos = self.coleta_carregada("rc-caso2-c@test.com", "rc-caso2-p@test.com")
        self.finalizar_com_regras(coleta_id, cabecalhos)

        self.garantir_perfil("rc-caso2-inv@test.com")
        cabecalhos_inv = self.headers_de("rc-caso2-inv@test.com")
        por_uuid_alheio = self.client.get(
            f"/api/v1/collections/{coleta_id}", headers=cabecalhos_inv
        )
        por_uuid_falso = self.client.get(
            f"/api/v1/collections/{uuid_lib.uuid4()}", headers=cabecalhos_inv
        )
        self.assertEqual(por_uuid_alheio.status_code, 404)
        self.assertEqual(por_uuid_falso.status_code, 404)
        self.assertEqual(por_uuid_alheio.json(), por_uuid_falso.json())
        self.assertNotIn("pneus", por_uuid_alheio.text)

    def test_03_prestador_nao_acessa_consulta_destinada_ao_cliente(self):
        coleta_id, cabecalhos = self.coleta_carregada("rc-caso3-c@test.com", "rc-caso3-p@test.com")
        self.finalizar_com_regras(coleta_id, cabecalhos)

        resposta = self.client.get(f"/api/v1/collections/{coleta_id}", headers=cabecalhos)
        self.assertEqual(resposta.status_code, 403)
        self.assertNotIn("pneus", resposta.text)

    def test_04_coleta_nao_finalizada_nao_expoe_pneus(self):
        coleta_id, cabecalhos = self.coleta_carregada("rc-caso4-c@test.com", "rc-caso4-p@test.com")

        resposta = self.client.get(
            f"/api/v1/collections/{coleta_id}", headers=self.headers_de("rc-caso4-c@test.com")
        )
        self.assertEqual(resposta.status_code, 200, resposta.text)
        self.assertNotIn("pneus", resposta.json())


if __name__ == "__main__":
    unittest.main()