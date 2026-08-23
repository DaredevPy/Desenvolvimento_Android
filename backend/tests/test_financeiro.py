# backend/tests/test_financeiro.py
import os
import unittest
import uuid as uuid_lib
from datetime import date, datetime, timezone
from itertools import count
from unittest import mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import security
from backend.app.main import app
from backend.db import session as db_session
from backend.db.models import (
    AuditLog,
    Base,
    Collection,
    FinancialTransaction,
    PriceRule,
    Profile,
    Tire,
    User,
)

SECRET_TESTE = "chave-de-teste-com-mais-de-32-bytes-para-hmac-sha256-0123456789"

SENHA = "senha@123"
DADOS_PERFIL = {"nome_razao_social": "Financeiro Teste LTDA", "telefone": "(11) 97777-6666"}
_CPF_SEQ = count(60_000_000_000_003, 23)
_NF_SEQ = count(700001)


def payload_pneu(**extras):
    base = {"marca": "Bridgestone", "medida": "295/80R22.5", "dot": "1012"}
    base.update(extras)
    return base


class TestFinanceiro(unittest.TestCase):
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
            dados["dados_veiculo_json"] = {"placa": "FIN2A11", "tipo": "truck"}
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

    def coleta_carregada(self, cliente, prestador, declarada=250, registrados=3):
        self.garantir_perfil(cliente)
        resposta = self.client.post(
            "/api/v1/collections",
            json={
                "endereco_origem_json": {"rua": "Rua do Financeiro", "numero": "10", "cidade": "Guarujá"},
                "data_agendada": datetime.now(timezone.utc).isoformat(),
                "itens": [
                    {"marca": "Bridgestone", "dimensao": "295/80R22.5", "quantidade_declarada": declarada}
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
        }
        if registrados != declarada:
            conclusao["justificativa_divergencia"] = "Faltam pneus no local."
            conclusao["fotos_divergencia_json"] = {"fotos": ["https://cdn.teste/fin.jpg"]}
        resposta = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/concluir",
            json=conclusao,
            headers=cabecalhos,
        )
        self.assertEqual(resposta.status_code, 200, resposta.text)
        return coleta_id, cabecalhos

    def finalizar(self, coleta_id, cabecalhos, corpo=None):
        return self.client.post(
            f"/api/v1/collections/{coleta_id}/finalizar", json=corpo or {}, headers=cabecalhos
        )

    def banco(self):
        return sessionmaker(bind=self.engine)()

    # --- regras de preço (ADMIN) ---

    def test_01_admin_cria_regra_com_auditoria(self):
        admin = self.admin_headers("fin-admin-cria@test.com")
        resposta = self.criar_regra(admin)
        self.assertEqual(resposta.status_code, 201, resposta.text)
        regra_id = resposta.json()["id"]
        with self.banco() as db:
            regra = db.get(PriceRule, regra_id)
            self.assertIsNotNone(regra)
            self.assertEqual(regra.perfil_alvo, "CLIENTE")
            self.assertTrue(regra.ativo)
            log = db.scalars(
                select(AuditLog).where(AuditLog.entidade_id == regra_id)
            ).first()
            self.assertIsNotNone(log)
            self.assertEqual(log.acao, "CRIACAO_REGRA_PRECO")

    def test_02_cliente_nao_cria_regra(self):
        self.garantir_perfil("fin-cli-regra@test.com")
        resposta = self.criar_regra(self.headers_de("fin-cli-regra@test.com"))
        self.assertEqual(resposta.status_code, 403)

    def test_03_prestador_nao_cria_regra(self):
        self.garantir_perfil("fin-prm-regra@test.com", rota="provider")
        resposta = self.criar_regra(self.headers_de("fin-prm-regra@test.com"))
        self.assertEqual(resposta.status_code, 403)

    def test_04_admin_altera_regra(self):
        admin = self.admin_headers("fin-admin-altera@test.com")
        regra_id = self.criar_regra(admin).json()["id"]
        resposta = self.client.patch(
            f"/api/v1/admin/pricing-rules/{regra_id}",
            json={"valor_unitario": "5.50", "justificativa": "Reajuste contratual."},
            headers=admin,
        )
        self.assertEqual(resposta.status_code, 200, resposta.text)
        with self.banco() as db:
            self.assertEqual(float(db.get(PriceRule, regra_id).valor_unitario), 5.50)

    def test_05_alteracao_fica_auditada(self):
        admin = self.admin_headers("fin-admin-audita@test.com")
        regra_id = self.criar_regra(admin).json()["id"]
        self.client.patch(
            f"/api/v1/admin/pricing-rules/{regra_id}",
            json={"valor_unitario": "6.00", "justificativa": "Correção de tabela."},
            headers=admin,
        )
        with self.banco() as db:
            log = db.scalars(
                select(AuditLog).where(
                    AuditLog.entidade_id == regra_id,
                    AuditLog.acao == "ALTERACAO_REGRA_PRECO",
                )
            ).first()
            self.assertIsNotNone(log)
            admin_id = db.scalars(select(User.id).where(User.email == "fin-admin-audita@test.com")).first()
            self.assertEqual(log.user_id, admin_id)
            self.assertEqual(float(log.valor_anterior_json["valor_unitario"]), 4.0)
            self.assertEqual(float(log.valor_novo_json["valor_unitario"]), 6.0)
            self.assertEqual(log.valor_novo_json["justificativa"], "Correção de tabela.")

    def test_06_valores_negativos_rejeitados(self):
        admin = self.admin_headers("fin-admin-neg@test.com")
        resposta = self.criar_regra(admin, valor_unitario="-4.00")
        self.assertEqual(resposta.status_code, 422)
        regra_id = self.criar_regra(admin).json()["id"]
        resposta = self.client.patch(
            f"/api/v1/admin/pricing-rules/{regra_id}",
            json={"valor_unitario": "-1.00", "justificativa": "Teste negativo."},
            headers=admin,
        )
        self.assertEqual(resposta.status_code, 422)

    def test_07_faixas_invalidas_e_conflitantes_rejeitadas(self):
        admin = self.admin_headers("fin-admin-faixa@test.com")
        resposta = self.criar_regra(
            admin, faixa_inicio_quantidade=500, faixa_fim_quantidade=100
        )
        self.assertEqual(resposta.status_code, 422)
        resposta = self.criar_regra(admin, faixa_inicio_quantidade=0, faixa_fim_quantidade=100)
        self.assertEqual(resposta.status_code, 201)
        resposta = self.criar_regra(admin, faixa_inicio_quantidade=50, faixa_fim_quantidade=150)
        self.assertEqual(resposta.status_code, 409)
        resposta = self.criar_regra(
            admin, perfil_alvo="PRESTADOR", faixa_inicio_quantidade=0, faixa_fim_quantidade=100
        )
        self.assertEqual(resposta.status_code, 201)
        resposta = self.criar_regra(
            admin, faixa_inicio_quantidade=200, faixa_fim_quantidade=300
        )
        self.assertEqual(resposta.status_code, 201)

    # --- fechamento financeiro ---

    def test_08_valores_independentes_cliente_prestador(self):
        admin = self.admin_headers("fin-admin-indep@test.com")
        self.criar_regra(admin)
        self.criar_regra(admin, perfil_alvo="PRESTADOR", valor_unitario="2.50")
        coleta_id, cabecalhos = self.coleta_carregada(
            "fin-indep-c@test.com", "fin-indep-p@test.com", registrados=3
        )
        resposta = self.finalizar(coleta_id, cabecalhos)
        self.assertEqual(resposta.status_code, 200, resposta.text)
        corpo = resposta.json()
        self.assertEqual(corpo["snapshot_valor_cliente"], 12.0)
        self.assertEqual(corpo["snapshot_valor_prestador"], 7.5)

    def test_09_calculo_usa_quantidade_coletada_nao_declarada(self):
        admin = self.admin_headers("fin-admin-qtd@test.com")
        self.criar_regra(admin, valor_unitario="4.00")
        self.criar_regra(admin, perfil_alvo="PRESTADOR", valor_unitario="2.50")
        coleta_id, cabecalhos = self.coleta_carregada(
            "fin-qtd-c@test.com", "fin-qtd-p@test.com", declarada=250, registrados=3
        )
        resposta = self.finalizar(coleta_id, cabecalhos)
        self.assertEqual(resposta.status_code, 200, resposta.text)
        corpo = resposta.json()
        self.assertEqual(corpo["quantidade_coletada"], 3)
        # Prova itens 9 e 10 da missão: usa 3 coletados, jamais os 250 declarados.
        self.assertEqual(corpo["snapshot_valor_cliente"], 12.0)
        self.assertNotEqual(corpo["snapshot_valor_cliente"], 1000.0)

    def test_10_snapshot_gravado_na_coleta(self):
        admin = self.admin_headers("fin-admin-snap@test.com")
        self.criar_regra(admin)
        self.criar_regra(admin, perfil_alvo="PRESTADOR", valor_unitario="2.50")
        coleta_id, cabecalhos = self.coleta_carregada(
            "fin-snap-c@test.com", "fin-snap-p@test.com", registrados=2
        )
        self.assertEqual(self.finalizar(coleta_id, cabecalhos).status_code, 200)
        with self.banco() as db:
            coleta = db.get(Collection, coleta_id)
            self.assertEqual(coleta.status, "FINALIZADA")
            self.assertEqual(float(coleta.snapshot_valor_cliente), 8.0)
            self.assertEqual(float(coleta.snapshot_valor_prestador), 5.0)
            self.assertIsNotNone(coleta.data_finalizacao)

    def test_11_lancamentos_desacoplados(self):
        admin = self.admin_headers("fin-admin-lanc@test.com")
        self.criar_regra(admin, valor_unitario="3.00")
        self.criar_regra(admin, perfil_alvo="PRESTADOR", valor_unitario="1.50")
        cliente, prestador = "fin-lanc-c@test.com", "fin-lanc-p@test.com"
        coleta_id, cabecalhos = self.coleta_carregada(cliente, prestador, registrados=4)
        resposta = self.finalizar(coleta_id, cabecalhos)
        self.assertEqual(resposta.status_code, 200, resposta.text)
        with self.banco() as db:
            perfil_cliente = db.scalars(
                select(Profile.id).join(User, Profile.user_id == User.id).where(User.email == cliente)
            ).first()
            perfil_prestador = db.scalars(
                select(Profile.id).join(User, Profile.user_id == User.id).where(User.email == prestador)
            ).first()
            lancamentos = db.scalars(
                select(FinancialTransaction).where(FinancialTransaction.collection_id == coleta_id)
            ).all()
            self.assertEqual(len(lancamentos), 2)
            por_tipo = {l.tipo_entidade: l for l in lancamentos}
            self.assertEqual(set(por_tipo), {"CLIENTE", "PRESTADOR"})
            self.assertEqual(float(por_tipo["CLIENTE"].valor_total), 12.0)
            self.assertEqual(float(por_tipo["PRESTADOR"].valor_total), 6.0)
            self.assertEqual(str(por_tipo["CLIENTE"].perfil_id), perfil_cliente)
            self.assertEqual(str(por_tipo["PRESTADOR"].perfil_id), perfil_prestador)
            self.assertEqual(por_tipo["CLIENTE"].status_pagamento, "PENDENTE")
            self.assertIsNone(por_tipo["PRESTADOR"].data_pagamento)

    def test_12_mudanca_de_regra_nao_altera_historico(self):
        admin = self.admin_headers("fin-admin-hist@test.com")
        self.criar_regra(admin, valor_unitario="4.00")
        self.criar_regra(admin, perfil_alvo="PRESTADOR", valor_unitario="2.50")
        coleta_id, cabecalhos = self.coleta_carregada(
            "fin-hist-c@test.com", "fin-hist-p@test.com", registrados=3
        )
        resposta = self.finalizar(coleta_id, cabecalhos)
        self.assertEqual(resposta.status_code, 200, resposta.text)
        with self.banco() as db:
            ids = db.scalars(select(PriceRule.id)).all()
        for regra_id in ids:
            self.client.patch(
                f"/api/v1/admin/pricing-rules/{regra_id}",
                json={"valor_unitario": "99.00", "justificativa": "Mudança pós-fechamento."},
                headers=admin,
            )
        with self.banco() as db:
            coleta = db.get(Collection, coleta_id)
            self.assertEqual(float(coleta.snapshot_valor_cliente), 12.0)
            self.assertEqual(float(coleta.snapshot_valor_prestador), 7.5)
            valores = db.scalars(
                select(FinancialTransaction.valor_total).where(
                    FinancialTransaction.collection_id == coleta_id
                )
            ).all()
            self.assertEqual(sorted(float(v) for v in valores), [7.5, 12.0])

    def test_13_snapshot_historico_rejeitado(self):
        admin = self.admin_headers("fin-admin-imut@test.com")
        self.criar_regra(admin)
        self.criar_regra(admin, perfil_alvo="PRESTADOR", valor_unitario="2.50")
        coleta_id, cabecalhos = self.coleta_carregada(
            "fin-imut-c@test.com", "fin-imut-p@test.com", registrados=2
        )
        self.assertEqual(self.finalizar(coleta_id, cabecalhos).status_code, 200)
        self.assertEqual(self.finalizar(coleta_id, cabecalhos).status_code, 409)
        resposta = self.client.post(
            f"/api/v1/collections/{coleta_id}/status",
            json={"novo_status": "EM_CONFERENCIA"},
            headers=cabecalhos,
        )
        self.assertIn(resposta.status_code, (409, 422))
        resposta = self.finalizar(
            coleta_id, cabecalhos, corpo={"snapshot_valor_cliente": 1.99}
        )
        self.assertEqual(resposta.status_code, 422)

    def test_14_fechamento_atomico_sem_regra(self):
        admin = self.admin_headers("fin-admin-atom@test.com")
        self.criar_regra(admin)  # somente CLIENTE
        coleta_id, cabecalhos = self.coleta_carregada(
            "fin-atom-c@test.com", "fin-atom-p@test.com", registrados=3
        )
        resposta = self.finalizar(coleta_id, cabecalhos)
        self.assertEqual(resposta.status_code, 409, resposta.text)
        self.assertIn("PRESTADOR", resposta.json()["detail"])
        with self.banco() as db:
            coleta = db.get(Collection, coleta_id)
            self.assertEqual(coleta.status, "CARREGADA")
            self.assertIsNone(coleta.snapshot_valor_cliente)
            self.assertIsNone(coleta.snapshot_valor_prestador)
            total = db.scalar(
                select(FinancialTransaction.id).where(FinancialTransaction.collection_id == coleta_id)
            )
            self.assertIsNone(total)

    def test_15_quantidade_fora_das_faixas_nao_gera_valor(self):
        admin = self.admin_headers("fin-admin-fora@test.com")
        self.criar_regra(admin, faixa_inicio_quantidade=100, faixa_fim_quantidade=1000)
        self.criar_regra(
            admin, perfil_alvo="PRESTADOR", faixa_inicio_quantidade=100, faixa_fim_quantidade=1000
        )
        coleta_id, cabecalhos = self.coleta_carregada(
            "fin-fora-c@test.com", "fin-fora-p@test.com", registrados=3
        )
        resposta = self.finalizar(coleta_id, cabecalhos)
        self.assertEqual(resposta.status_code, 409)
        with self.banco() as db:
            coleta = db.get(Collection, coleta_id)
            self.assertEqual(coleta.status, "CARREGADA")
            self.assertIsNone(coleta.snapshot_valor_cliente)

    def test_16_payload_forjado_rejeitado(self):
        admin = self.admin_headers("fin-admin-forj@test.com")
        resposta = self.criar_regra(admin, snapshot_valor_cliente=1.0)
        self.assertEqual(resposta.status_code, 422)
        resposta = self.criar_regra(admin, provider_id=str(uuid_lib.uuid4()))
        self.assertEqual(resposta.status_code, 422)
        self.criar_regra(admin)
        self.criar_regra(admin, perfil_alvo="PRESTADOR", valor_unitario="2.50")
        coleta_id, cabecalhos = self.coleta_carregada(
            "fin-forj-c@test.com", "fin-forj-p@test.com", registrados=2
        )
        resposta = self.finalizar(
            coleta_id,
            cabecalhos,
            corpo={"snapshot_valor_prestador": 999.99, "client_id": str(uuid_lib.uuid4())},
        )
        self.assertEqual(resposta.status_code, 422)

    def test_17_finalizacao_protegida_por_posse_e_role(self):
        admin = self.admin_headers("fin-admin-prot@test.com")
        self.criar_regra(admin)
        self.criar_regra(admin, perfil_alvo="PRESTADOR", valor_unitario="2.50")
        coleta_id, cabecalhos = self.coleta_carregada(
            "fin-prot-c@test.com", "fin-prot-p@test.com", registrados=2
        )
        self.garantir_perfil("fin-outro-p@test.com", rota="provider")
        resposta = self.finalizar(coleta_id, self.headers_de("fin-outro-p@test.com"))
        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(resposta.json()["detail"], "Recurso não encontrado.")
        self.garantir_perfil("fin-prot-c2@test.com")
        resposta = self.finalizar(coleta_id, self.headers_de("fin-prot-c2@test.com"))
        self.assertEqual(resposta.status_code, 403)
