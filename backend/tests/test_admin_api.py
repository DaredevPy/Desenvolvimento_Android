# backend/tests/test_admin_api.py
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
    User,
)

SECRET_TESTE = "chave-de-teste-com-mais-de-32-bytes-para-hmac-sha256-0123456789"

SENHA = "senha@123"
DADOS_PERFIL = {"nome_razao_social": "Admin API Teste LTDA", "telefone": "(11) 96666-5555"}
_CPF_SEQ = count(80_000_000_000_007, 31)
_NF_SEQ = count(900001)


def payload_pneu(**extras):
    base = {"marca": "Pirelli", "medida": "275/80R22.5", "dot": "1519"}
    base.update(extras)
    return base


class TestAdminApi(unittest.TestCase):
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
        # Banco por teste: mesmas razões da suíte de financeiro.
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
            dados["dados_veiculo_json"] = {"placa": "ADM1B22", "tipo": "truck"}
        resposta = self.client.post(
            f"/api/v1/profile/{rota}", json=dados, headers=self.headers_de(email)
        )
        self.assertIn(resposta.status_code, (201, 409), resposta.text)

    def admin_headers(self, email="adm-api@test.com"):
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
                "endereco_origem_json": {"rua": "Rua do Admin", "numero": "30", "cidade": "São Vicente"},
                "data_agendada": datetime.now(timezone.utc).isoformat(),
                "itens": [
                    {"marca": "Pirelli", "dimensao": "275/80R22.5", "quantidade_declarada": declarada}
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
        pneus = [payload_pneu(numero_fogo=f"{next(_NF_SEQ):06d}") for _ in range(registrados)]
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
            conclusao["fotos_divergencia_json"] = {"fotos": ["https://cdn.teste/adm.jpg"]}
        resposta = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/concluir",
            json=conclusao,
            headers=cabecalhos,
        )
        self.assertEqual(resposta.status_code, 200, resposta.text)
        return coleta_id

    def finalizar(self, coleta_id, cabecalhos):
        return self.client.post(
            f"/api/v1/collections/{coleta_id}/finalizar", json={}, headers=cabecalhos
        )

    def banco(self):
        return sessionmaker(bind=self.engine)()

    # --- regras de preço ---

    def test_01_admin_lista_regras_com_filtros_e_paginacao(self):
        admin = self.admin_headers("adm-regras@test.com")
        self.criar_regra(admin, perfil_alvo="CLIENTE", valor_unitario="4.00")
        self.criar_regra(admin, perfil_alvo="PRESTADOR", valor_unitario="2.50")
        resposta = self.client.get("/api/v1/admin/pricing-rules", headers=admin)
        self.assertEqual(resposta.status_code, 200, resposta.text)
        corpo = resposta.json()
        self.assertEqual(corpo["total"], 2)
        perfis = {item["perfil_alvo"]: item for item in corpo["itens"]}
        self.assertEqual(perfis["CLIENTE"]["valor_unitario"], 4.0)
        self.assertTrue(perfis["CLIENTE"]["ativo"])
        self.assertIsNotNone(perfis["CLIENTE"]["vigencia_inicio"])

        resposta = self.client.get(
            "/api/v1/admin/pricing-rules?perfil_alvo=PRESTADOR&por_pagina=1&page=1",
            headers=admin,
        )
        corpo = resposta.json()
        self.assertEqual(corpo["total"], 1)
        self.assertEqual(len(corpo["itens"]), 1)
        self.assertEqual(corpo["itens"][0]["valor_unitario"], 2.5)

    def test_02_cliente_recebe_403_em_regras(self):
        self.garantir_perfil("adm-cli-r@test.com")
        resposta = self.client.get(
            "/api/v1/admin/pricing-rules", headers=self.headers_de("adm-cli-r@test.com")
        )
        self.assertEqual(resposta.status_code, 403)

    def test_03_prestador_recebe_403_em_regras(self):
        self.garantir_perfil("adm-prm-r@test.com", rota="provider")
        resposta = self.client.get(
            "/api/v1/admin/pricing-rules", headers=self.headers_de("adm-prm-r@test.com")
        )
        self.assertEqual(resposta.status_code, 403)

    # --- auditoria ---

    def test_04_admin_consulta_auditoria_com_filtros(self):
        admin = self.admin_headers("adm-aud@test.com")
        regra_id = self.criar_regra(admin).json()["id"]
        self.client.patch(
            f"/api/v1/admin/pricing-rules/{regra_id}",
            json={"valor_unitario": "6.00", "justificativa": "Reajuste."},
            headers=admin,
        )
        resposta = self.client.get("/api/v1/admin/audit-logs", headers=admin)
        self.assertEqual(resposta.status_code, 200, resposta.text)
        self.assertEqual(resposta.json()["total"], 2)
        acoes = {item["acao"] for item in resposta.json()["itens"]}
        self.assertEqual(acoes, {"CRIACAO_REGRA_PRECO", "ALTERACAO_REGRA_PRECO"})

        resposta = self.client.get(
            "/api/v1/admin/audit-logs?acao=ALTERACAO_REGRA_PRECO&entidade_afetada=price_rules",
            headers=admin,
        )
        itens = resposta.json()["itens"]
        self.assertEqual(len(itens), 1)
        self.assertEqual(float(itens[0]["valor_anterior_json"]["valor_unitario"]), 4.0)
        self.assertEqual(float(itens[0]["valor_novo_json"]["valor_unitario"]), 6.0)

        # Filtros de auditoria são UTC (decisão Missão 11); date.today()
        # local difere do dia UTC após 21h no Brasil (UTC-3).
        hoje = datetime.now(timezone.utc).date().isoformat()
        resposta = self.client.get(
            f"/api/v1/admin/audit-logs?data_inicio={hoje}&data_fim={hoje}", headers=admin
        )
        self.assertEqual(resposta.json()["total"], 2)
        resposta = self.client.get(
            f"/api/v1/admin/audit-logs?data_fim=1999-01-01", headers=admin
        )
        self.assertEqual(resposta.json()["total"], 0)

    def test_05_audit_logs_sao_somente_leitura(self):
        admin = self.admin_headers("adm-leitura@test.com")
        regra_id = self.criar_regra(admin).json()["id"]
        with self.banco() as db:
            log_antes = db.scalars(select(AuditLog)).first()
            original = dict(valor_novo_json=log_antes.valor_novo_json, acao=log_antes.acao)

        for metodo in ("patch", "put", "delete"):
            kwargs = {"headers": admin}
            if metodo in ("patch", "put"):
                kwargs["json"] = {"valor_novo_json": {}}
            resposta = getattr(self.client, metodo)(
                f"/api/v1/admin/audit-logs/{log_antes.id}", **kwargs
            )
            self.assertIn(resposta.status_code, (404, 405))
        resposta = self.client.post(
            "/api/v1/admin/audit-logs", json={}, headers=admin
        )
        self.assertIn(resposta.status_code, (404, 405))

        with self.banco() as db:
            log_depois = db.get(AuditLog, log_antes.id)
            self.assertEqual(log_depois.acao, original["acao"])
            self.assertEqual(log_depois.valor_novo_json, original["valor_novo_json"])
            # Nenhum log extra foi criado pelas tentativas.
            self.assertEqual(len(db.scalars(select(AuditLog)).all()), 1)
        self.assertTrue(regra_id)

    # --- coletas operacionais ---

    def test_06_admin_lista_coletas_operacional(self):
        admin = self.admin_headers()
        cliente, prestador = "adm-op-c@test.com", "adm-op-p@test.com"
        coleta_id = self.coleta_carregada(cliente, prestador)
        resposta = self.client.get("/api/v1/admin/collections", headers=admin)
        self.assertEqual(resposta.status_code, 200, resposta.text)
        corpo = resposta.json()
        self.assertEqual(corpo["total"], 1)
        item = corpo["itens"][0]
        self.assertEqual(item["id"], coleta_id)
        self.assertEqual(item["status"], "CARREGADA")
        self.assertEqual(item["cliente_email"], cliente)
        self.assertEqual(item["prestador_email"], prestador)
        self.assertEqual(item["quantidade_declarada"], 250)
        self.assertEqual(item["quantidade_conferida"], 3)
        self.assertEqual(item["quantidade_coletada"], 3)
        self.assertIsNone(item["snapshot_valor_cliente"])
        self.assertIsNone(item["snapshot_valor_prestador"])

        resposta = self.client.get(
            "/api/v1/admin/collections?status=CARREGADA", headers=admin
        )
        self.assertEqual(resposta.json()["total"], 1)
        resposta = self.client.get(
            "/api/v1/admin/collections?status=FINALIZADA", headers=admin
        )
        self.assertEqual(resposta.json()["total"], 0)

    def test_07_admin_consulta_coleta_de_terceiros(self):
        admin = self.admin_headers()
        coleta_id = self.coleta_carregada("adm-ter-c@test.com", "adm-ter-p@test.com")
        resposta = self.client.get(f"/api/v1/admin/collections/{coleta_id}", headers=admin)
        self.assertEqual(resposta.status_code, 200, resposta.text)
        self.assertEqual(resposta.json()["cliente_email"], "adm-ter-c@test.com")

    def test_08_admin_detalha_coleta_com_divergencia(self):
        admin = self.admin_headers()
        cliente = "adm-det-c@test.com"
        coleta_id = self.coleta_carregada(cliente, "adm-det-p@test.com", declarada=250, registrados=3)
        resposta = self.client.get(f"/api/v1/admin/collections/{coleta_id}", headers=admin)
        self.assertEqual(resposta.status_code, 200, resposta.text)
        detalhe = resposta.json()
        self.assertEqual(detalhe["status"], "CARREGADA")
        self.assertEqual(len(detalhe["itens_declarados"]), 1)
        self.assertEqual(detalhe["itens_declarados"][0]["quantidade_declarada"], 250)
        self.assertEqual(len(detalhe["conferencia"]), 1)
        conferencia = detalhe["conferencia"][0]
        self.assertEqual(conferencia["quantidade_coletada"], 3)
        self.assertIn("Faltam pneus", conferencia["justificativa_divergencia"])
        self.assertTrue(conferencia["fotos_divergencia_json"]["fotos"])
        self.assertEqual(detalhe["cliente_email"], cliente)

    def test_09_pneus_individuais_no_detalhe(self):
        admin = self.admin_headers()
        coleta_id = self.coleta_carregada("adm-pneu-c@test.com", "adm-pneu-p@test.com", registrados=2)
        resposta = self.client.get(f"/api/v1/admin/collections/{coleta_id}", headers=admin)
        pneus = resposta.json()["pneus"]
        self.assertEqual(len(pneus), 2)
        numeros = {pneu["numero_fogo"] for pneu in pneus}
        self.assertEqual(len(numeros), 2)
        primeiro = pneus[0]
        self.assertEqual(primeiro["dot"], "1519")
        self.assertEqual(primeiro["semana_fabricacao"], 15)
        self.assertEqual(primeiro["ano_fabricacao"], 19)
        self.assertGreaterEqual(primeiro["idade_calculada_anos"], 0)
        self.assertFalse(primeiro["numero_fogo_ilegivel"])

    def test_10_informacoes_financeiras_no_detalhe(self):
        admin = self.admin_headers()
        self.criar_regra(admin, valor_unitario="4.00")
        self.criar_regra(admin, perfil_alvo="PRESTADOR", valor_unitario="2.50")
        coleta_id = self.coleta_carregada("adm-fin-c@test.com", "adm-fin-p@test.com", registrados=3)
        prestador = self.headers_de("adm-fin-p@test.com")
        resposta = self.finalizar(coleta_id, prestador)
        self.assertEqual(resposta.status_code, 200, resposta.text)

        detalhe = self.client.get(f"/api/v1/admin/collections/{coleta_id}", headers=admin).json()
        self.assertEqual(detalhe["snapshot_valor_cliente"], 12.0)
        self.assertEqual(detalhe["snapshot_valor_prestador"], 7.5)
        lancamentos = detalhe["lancamentos_financeiros"]
        self.assertEqual(len(lancamentos), 2)
        por_tipo = {l["tipo_entidade"]: l for l in lancamentos}
        self.assertEqual(float(por_tipo["CLIENTE"]["valor_total"]), 12.0)
        self.assertEqual(float(por_tipo["PRESTADOR"]["valor_total"]), 7.5)
        self.assertEqual(por_tipo["CLIENTE"]["status_pagamento"], "PENDENTE")

    # --- proteção de acesso e de histórico financeiro ---

    def test_11_cliente_sem_acesso_administrativo(self):
        self.garantir_perfil("adm-neg-c@test.com")
        cabecalhos = self.headers_de("adm-neg-c@test.com")
        rotas = (
            "/api/v1/admin/pricing-rules",
            "/api/v1/admin/audit-logs",
            "/api/v1/admin/collections",
        )
        for rota in rotas:
            resposta = self.client.get(rota, headers=cabecalhos)
            self.assertEqual(resposta.status_code, 403, rota)

    def test_12_prestador_sem_acesso_administrativo(self):
        self.garantir_perfil("adm-neg-p@test.com", rota="provider")
        cabecalhos = self.headers_de("adm-neg-p@test.com")
        rotas = (
            "/api/v1/admin/pricing-rules",
            "/api/v1/admin/audit-logs",
            "/api/v1/admin/collections",
        )
        for rota in rotas:
            resposta = self.client.get(rota, headers=cabecalhos)
            self.assertEqual(resposta.status_code, 403, rota)

    def test_13_id_inexistente_tem_comportamento_seguro(self):
        admin = self.admin_headers()
        inexistente = str(uuid_lib.uuid4())
        resposta = self.client.get(f"/api/v1/admin/collections/{inexistente}", headers=admin)
        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(resposta.json()["detail"], "Recurso não encontrado.")
        resposta = self.client.get(f"/api/v1/admin/pricing-rules/{inexistente}", headers=admin)
        self.assertIn(resposta.status_code, (404, 405))

    def test_14_alteracao_financeira_historica_rejeitada(self):
        admin = self.admin_headers()
        self.criar_regra(admin, valor_unitario="4.00")
        self.criar_regra(admin, perfil_alvo="PRESTADOR", valor_unitario="2.50")
        coleta_id = self.coleta_carregada("adm-hist-c@test.com", "adm-hist-p@test.com", registrados=3)
        self.assertEqual(
            self.finalizar(coleta_id, self.headers_de("adm-hist-p@test.com")).status_code, 200
        )

        # ADMIN não recalcula nem refaz fechamento: /finalizar é exclusivo do prestador.
        resposta = self.finalizar(coleta_id, self.admin_headers("adm-tenta@test.com"))
        self.assertEqual(resposta.status_code, 403)
        # Sem rotas de escrita administrativas sobre coletas ou lançamentos.
        for metodo, rota in (
            ("patch", f"/api/v1/admin/collections/{coleta_id}"),
            ("delete", f"/api/v1/admin/collections/{coleta_id}"),
            ("patch", f"/api/v1/admin/collections/{coleta_id}/finalizar"),
            ("delete", f"/api/v1/admin/financial-transactions/{uuid_lib.uuid4()}"),
        ):
            kwargs = {"headers": admin}
            if metodo == "patch":
                kwargs["json"] = {}
            resposta = getattr(self.client, metodo)(rota, **kwargs)
            self.assertIn(resposta.status_code, (404, 405), rota)

    def test_15_snapshot_permanece_intacto(self):
        admin = self.admin_headers()
        self.criar_regra(admin, valor_unitario="4.00")
        self.criar_regra(admin, perfil_alvo="PRESTADOR", valor_unitario="2.50")
        coleta_id = self.coleta_carregada("adm-intac-c@test.com", "adm-intac-p@test.com", registrados=2)
        self.assertEqual(
            self.finalizar(coleta_id, self.headers_de("adm-intac-p@test.com")).status_code, 200
        )

        # Admin altera preços futuros (permitido e auditado)...
        with self.banco() as db:
            ids = db.scalars(select(PriceRule.id)).all()
        for regra_id in ids:
            self.client.patch(
                f"/api/v1/admin/pricing-rules/{regra_id}",
                json={"valor_unitario": "99.99", "justificativa": "Tabela nova."},
                headers=admin,
            )
        # ...mas o histórico permanece intacto.
        detalhe = self.client.get(f"/api/v1/admin/collections/{coleta_id}", headers=admin).json()
        self.assertEqual(detalhe["snapshot_valor_cliente"], 8.0)
        self.assertEqual(detalhe["snapshot_valor_prestador"], 5.0)
        with self.banco() as db:
            valores = db.scalars(
                select(FinancialTransaction.valor_total).where(
                    FinancialTransaction.collection_id == coleta_id
                )
            ).all()
            self.assertEqual(sorted(float(v) for v in valores), [5.0, 8.0])
            coleta = db.get(Collection, coleta_id)
            self.assertEqual(coleta.status, "FINALIZADA")
