# backend/tests/test_contestacao.py
# Missão 14: FINALIZADA -> CONTESTADA (docs 03 §2.1, 04 §2, 05 §1).
import os
import tempfile
import threading
import unittest
from datetime import date, datetime, timezone
from itertools import count
from unittest import mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from backend.app import security
from backend.app.main import app
from backend.db import session as db_session
from backend.db.models import (
    AuditLog,
    Base,
    Collection,
    CollectionItemDeclared,
    FinancialTransaction,
    Tire,
    User,
)

SECRET_TESTE = "chave-de-teste-com-mais-de-32-bytes-para-hmac-sha256-0123456789"
SENHA = "senha@123"
DADOS_PERFIL = {"nome_razao_social": "Contestacao Teste LTDA", "telefone": "(11) 92222-1111"}
_CPF_SEQ = count(30_000_000_001, 71)


class TestContestacao(unittest.TestCase):
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
        # Arquivo + NullPool: uma conexão por requisição (semântica PostgreSQL),
        # necessária à prova de concorrência.
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
            dados["dados_veiculo_json"] = {"placa": "CTT1B44", "tipo": "truck"}
        resposta = self.client.post(
            f"/api/v1/profile/{rota}", json=dados, headers=self.headers_de(email)
        )
        self.assertIn(resposta.status_code, (201, 409), resposta.text)

    def admin_headers(self, email="adm-contest@test.com"):
        with sessionmaker(bind=self.engine)() as db:
            db.add(User(email=email, password_hash=security.hash_password(SENHA), role="ADMINISTRADOR"))
            db.commit()
        return self.headers_de(email)

    def criar_regras(self, admin):
        base = {
            "faixa_inicio_quantidade": 0,
            "faixa_fim_quantidade": 10000,
            "vigencia_inicio": date.today().isoformat(),
        }
        for perfil, valor in (("CLIENTE", "4.00"), ("PRESTADOR", "2.50")):
            resposta = self.client.post(
                "/api/v1/admin/pricing-rules",
                json={**base, "perfil_alvo": perfil, "valor_unitario": valor},
                headers=admin,
            )
            self.assertEqual(resposta.status_code, 201, resposta.text)

    def criar_coleta(self, cliente, prestador):
        resposta = self.client.post(
            "/api/v1/collections",
            json={
                "endereco_origem_json": {"rua": "Rua da Contestação", "numero": "99", "cidade": "Guarujá"},
                "data_agendada": self._agora,
                "itens": [
                    {"marca": "Michelin", "dimensao": "275/80R22.5", "quantidade_declarada": 250}
                ],
            },
            headers=cliente,
        )
        self.assertEqual(resposta.status_code, 201, resposta.text)
        coleta_id = resposta.json()["id"]
        self.client.post(f"/api/v1/collections/{coleta_id}/aceitar", headers=prestador)
        return coleta_id

    def pneus(self, quantidade, prefixo_nf):
        return [
            {"marca": "Michelin", "medida": "275/80R22.5", "dot": "2526", "numero_fogo": f"{prefixo_nf}{i:03d}"}
            for i in range(quantidade)
        ]

    def enviar_pneus(self, prestador, coleta_id, pneus):
        return self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/pneus",
            json={"pneus": pneus},
            headers=prestador,
        )

    def concluir(self, prestador, coleta_id):
        return self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/concluir",
            json={
                "quantidade_conferida": 250,
                "quantidade_coletada": 2,
                "justificativa_divergencia": "Divergência documentada no teste.",
                "fotos_divergencia_json": {"fotos": ["foto.jpg"]},
            },
            headers=prestador,
        )

    def levar_ate(self, estado, sufixo):
        """Leva uma coleta nova até o estado informado e devolve o id."""
        self.garantir_perfil(f"ctt-c{sufixo}@test.com")
        self.garantir_perfil(f"ctt-p{sufixo}@test.com", rota="provider")
        cliente = self.headers_de(f"ctt-c{sufixo}@test.com")
        prestador = self.headers_de(f"ctt-p{sufixo}@test.com")

        def nova_coleta():
            resposta = self.client.post(
                "/api/v1/collections",
                json={
                    "endereco_origem_json": {"rua": "R", "numero": "1", "cidade": "C"},
                    "data_agendada": self._agora,
                    "itens": [{"marca": "M", "dimensao": "D", "quantidade_declarada": 10}],
                },
                headers=cliente,
            )
            self.assertEqual(resposta.status_code, 201, resposta.text)
            return resposta.json()["id"]

        if estado == "SOLICITADA":
            coleta_id = nova_coleta()
        elif estado == "CANCELADA":
            coleta_id = nova_coleta()
            self.assertEqual(
                self.client.post(f"/api/v1/collections/{coleta_id}/cancelar", headers=cliente).status_code,
                200,
            )
        else:
            coleta_id = self.criar_coleta(cliente, prestador)  # ACEITA
            if estado == "CONTESTADA":
                self.finalizar(cliente, prestador, coleta_id, sufixo)
                self.assertEqual(self.contestar(cliente, coleta_id).status_code, 200)
            elif estado == "FINALIZADA":
                self.finalizar(cliente, prestador, coleta_id, sufixo)
            else:
                passos = {
                    "ACEITA": [],
                    "EM_DESLOCAMENTO": [("status", {"novo_status": "EM_DESLOCAMENTO"})],
                    "EM_CONFERENCIA": [
                        ("status", {"novo_status": "EM_DESLOCAMENTO"}),
                        ("iniciar", None),
                    ],
                    "CARREGADA": [
                        ("status", {"novo_status": "EM_DESLOCAMENTO"}),
                        ("iniciar", None),
                        ("pneus", None),
                        ("concluir", None),
                    ],
                }
                for acao, corpo in passos[estado]:
                    if acao == "status":
                        r = self.client.post(
                            f"/api/v1/collections/{coleta_id}/status", json=corpo, headers=prestador
                        )
                    elif acao == "iniciar":
                        r = self.client.post(
                            f"/api/v1/collections/{coleta_id}/conferencia/iniciar", headers=prestador
                        )
                    elif acao == "pneus":
                        r = self.enviar_pneus(prestador, coleta_id, self.pneus(2, "NFC"))
                    else:
                        r = self.concluir(prestador, coleta_id)
                    self.assertIn(r.status_code, (200, 201), r.text)
        with sessionmaker(bind=self.engine)() as db:
            atual = db.get(Collection, coleta_id).status
        self.assertEqual(atual, estado)
        return cliente, prestador, coleta_id

    def finalizar(self, cliente, prestador, coleta_id, sufixo):
        self.client.post(
            f"/api/v1/collections/{coleta_id}/status",
            json={"novo_status": "EM_DESLOCAMENTO"},
            headers=prestador,
        )
        self.client.post(f"/api/v1/collections/{coleta_id}/conferencia/iniciar", headers=prestador)
        self.assertEqual(
            self.enviar_pneus(prestador, coleta_id, self.pneus(2, f"NF{sufixo}")).status_code, 201
        )
        self.assertEqual(self.concluir(prestador, coleta_id).status_code, 200)
        self.criar_regras(self.admin_headers())
        resposta = self.client.post(
            f"/api/v1/collections/{coleta_id}/finalizar", json={}, headers=prestador
        )
        self.assertEqual(resposta.status_code, 200, resposta.text)

    def contestar(self, cabecalhos, coleta_id, json=None):
        return self.client.post(
            f"/api/v1/collections/{coleta_id}/contestar", json=json or {}, headers=cabecalhos
        )

    # --- 1: contestação válida / 10: transição exata ---

    def test_01_contestacao_valida_transiciona_finalizada_para_contestada(self):
        cliente, _, coleta_id = self.levar_ate("FINALIZADA", "s01")
        with sessionmaker(bind=self.engine)() as db:
            self.assertEqual(db.get(Collection, coleta_id).status, "FINALIZADA")
        resposta = self.contestar(cliente, coleta_id)
        self.assertEqual(resposta.status_code, 200, resposta.text)
        self.assertEqual(resposta.json(), {"id": coleta_id, "status": "CONTESTADA"})
        with sessionmaker(bind=self.engine)() as db:
            self.assertEqual(db.get(Collection, coleta_id).status, "CONTESTADA")

    # --- 2/3: autenticação e papel ---

    def test_02_exige_autenticacao(self):
        _, _, coleta_id = self.levar_ate("FINALIZADA", "s02")
        resposta = self.client.post(f"/api/v1/collections/{coleta_id}/contestar", json={})
        self.assertEqual(resposta.status_code, 401)

    def test_03_prestador_recebe_403(self):
        cliente, prestador, coleta_id = self.levar_ate("FINALIZADA", "s03")
        resposta = self.contestar(prestador, coleta_id)
        self.assertEqual(resposta.status_code, 403)
        with sessionmaker(bind=self.engine)() as db:
            self.assertEqual(db.get(Collection, coleta_id).status, "FINALIZADA")

    # --- 4/5: anti-enumeração e ownership ---

    def test_04_coleta_inexistente_eh_indistinguivel(self):
        self.garantir_perfil("ctt-c04@test.com")
        resposta = self.contestar(self.headers_de("ctt-c04@test.com"), str(__import__("uuid").uuid4()))
        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(resposta.json()["detail"], "Recurso não encontrado.")

    def test_05_coleta_de_terceiro_eh_indistinguivel(self):
        cliente_a, _, coleta_id = self.levar_ate("FINALIZADA", "s05a")
        self.garantir_perfil("ctt-c05b@test.com")  # outro cliente
        intruso = self.headers_de("ctt-c05b@test.com")
        resposta = self.contestar(intruso, coleta_id)
        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(resposta.json()["detail"], "Recurso não encontrado.")
        with sessionmaker(bind=self.engine)() as db:
            self.assertEqual(db.get(Collection, coleta_id).status, "FINALIZADA")

    # --- 6/7: máquina de estados ---

    def test_06_estado_diferente_de_finalizada_rejeitado(self):
        cliente, _, coleta_id = self.levar_ate("CARREGADA", "s06")
        resposta = self.contestar(cliente, coleta_id)
        self.assertEqual(resposta.status_code, 409)
        self.assertIn("Transição inválida", resposta.json()["detail"])

    def test_07_nenhum_outro_salto_para_contestada_eh_permutido(self):
        cliente, prestador, coleta_id = self.levar_ate("SOLICITADA", "s07")
        self.assertEqual(self.contestar(cliente, coleta_id).status_code, 409)
        self.assertEqual(
            self.client.post(
                f"/api/v1/collections/{coleta_id}/aceitar", headers=prestador
            ).status_code,
            200,
        )
        self.assertEqual(self.contestar(cliente, coleta_id).status_code, 409)  # ACEITA
        cliente_d, _, coleta_d = self.levar_ate("EM_DESLOCAMENTO", "s07d")
        self.assertEqual(self.contestar(cliente_d, coleta_d).status_code, 409)
        cliente_e, _, coleta_e = self.levar_ate("EM_CONFERENCIA", "s07e")
        self.assertEqual(self.contestar(cliente_e, coleta_e).status_code, 409)
        cliente_f, _, coleta_f = self.levar_ate("CARREGADA", "s07f")
        self.assertEqual(self.contestar(cliente_f, coleta_f).status_code, 409)
        cliente_g, _, coleta_g = self.levar_ate("CANCELADA", "s07g")
        self.assertEqual(self.contestar(cliente_g, coleta_g).status_code, 409)
        # CONTESTADA é terminal: segunda contestação não re-executa nem audita duas vezes.
        cliente_h, _, coleta_h = self.levar_ate("CONTESTADA", "s07h")
        logs_antes = self.logs_de(coleta_h)
        self.assertEqual(self.contestar(cliente_h, coleta_h).status_code, 409)
        self.assertEqual(len(self.logs_de(coleta_h)), len(logs_antes))

    def logs_de(self, coleta_id):
        with sessionmaker(bind=self.engine)() as db:
            return db.scalars(
                select(AuditLog).where(
                    AuditLog.entidade_afetada == "collections",
                    AuditLog.entidade_id == coleta_id,
                    AuditLog.acao == "CONTESTACAO_COLETA",
                )
            ).all()

    # --- 8: payload estrito ---

    def test_08_corpo_com_campo_extra_rejeitado(self):
        cliente, _, coleta_id = self.levar_ate("FINALIZADA", "s08")
        resposta = self.contestar(cliente, coleta_id, json={"justificativa": "x"})
        # Docs não definem payload de contestação: campo extra é rejeitado.
        self.assertEqual(resposta.status_code, 422)

    # --- 12: concorrência ---

    def test_09_concorrencia_produz_apenas_um_efeito(self):
        cliente, _, coleta_id = self.levar_ate("FINALIZADA", "s09")
        barreira = threading.Barrier(2)
        respostas = []

        def disparar():
            http = TestClient(app)
            try:
                barreira.wait(timeout=10)
                respostas.append(http.post(f"/api/v1/collections/{coleta_id}/contestar", json={}, headers=cliente))
            except Exception as erro:
                respostas.append(erro)

        fios = [threading.Thread(target=disparar) for _ in range(2)]
        for fio in fios:
            fio.start()
        for fio in fios:
            fio.join(timeout=30)
        self.assertEqual(len(respostas), 2)
        for resposta in respostas:
            self.assertIn(getattr(resposta, "status_code", None), (200, 409), str(resposta))
        self.assertTrue(any(r.status_code == 200 for r in respostas))
        with sessionmaker(bind=self.engine)() as db:
            self.assertEqual(db.get(Collection, coleta_id).status, "CONTESTADA")
        self.assertEqual(len(self.logs_de(coleta_id)), 1)

    # --- 13/14: financeiro e snapshots intactos ---

    def test_13_lancamentos_e_snapshots_permanecem_intactos(self):
        cliente, _, coleta_id = self.levar_ate("FINALIZADA", "s13")
        with sessionmaker(bind=self.engine)() as db:
            coleta_antes = db.get(Collection, coleta_id)
            snap_cliente = float(coleta_antes.snapshot_valor_cliente)
            snap_prestador = float(coleta_antes.snapshot_valor_prestador)
            lancamentos_antes = [
                (l.id, l.tipo_entidade, str(l.valor_total), str(l.data_vencimento))
                for l in db.scalars(
                    select(FinancialTransaction).where(FinancialTransaction.collection_id == coleta_id)
                ).all()
            ]
        self.assertEqual(len(lancamentos_antes), 2)
        self.assertEqual(self.contestar(cliente, coleta_id).status_code, 200)
        with sessionmaker(bind=self.engine)() as db:
            coleta_depois = db.get(Collection, coleta_id)
            self.assertEqual(float(coleta_depois.snapshot_valor_cliente), snap_cliente)
            self.assertEqual(float(coleta_depois.snapshot_valor_prestador), snap_prestador)
            lancamentos_depois = [
                (l.id, l.tipo_entidade, str(l.valor_total), str(l.data_vencimento))
                for l in db.scalars(
                    select(FinancialTransaction).where(FinancialTransaction.collection_id == coleta_id)
                ).all()
            ]
        self.assertEqual(lancamentos_depois, lancamentos_antes)

    # --- 15/16/17: pneus, DOT e número de fogo intactos ---

    def test_14_pneus_dot_e_numero_de_fogo_permanecem_intactos(self):
        cliente, _, coleta_id = self.levar_ate("FINALIZADA", "s14")
        with sessionmaker(bind=self.engine)() as db:
            pneus_antes = sorted(
                (t.id, t.dot, t.numero_fogo, str(t.idade_calculada_anos))
                for t in db.scalars(select(Tire).where(Tire.collection_id == coleta_id)).all()
            )
            itens_antes = [
                (i.marca, i.dimensao, i.quantidade_declarada)
                for i in db.scalars(
                    select(CollectionItemDeclared).where(CollectionItemDeclared.collection_id == coleta_id)
                ).all()
            ]
        self.assertEqual(self.contestar(cliente, coleta_id).status_code, 200)
        with sessionmaker(bind=self.engine)() as db:
            pneus_depois = sorted(
                (t.id, t.dot, t.numero_fogo, str(t.idade_calculada_anos))
                for t in db.scalars(select(Tire).where(Tire.collection_id == coleta_id)).all()
            )
            itens_depois = [
                (i.marca, i.dimensao, i.quantidade_declarada)
                for i in db.scalars(
                    select(CollectionItemDeclared).where(CollectionItemDeclared.collection_id == coleta_id)
                ).all()
            ]
        self.assertEqual(pneus_depois, pneus_antes)
        self.assertEqual(itens_depois, itens_antes)

    # --- 18: auditoria ---

    def test_15_auditoria_registra_quem_quando_e_estados(self):
        cliente, _, coleta_id = self.levar_ate("FINALIZADA", "s15")
        self.assertEqual(self.contestar(cliente, coleta_id).status_code, 200)
        logs = self.logs_de(coleta_id)
        self.assertEqual(len(logs), 1)
        log = logs[0]
        self.assertIsNotNone(log.user_id)
        self.assertEqual(log.acao, "CONTESTACAO_COLETA")
        self.assertEqual(log.entidade_afetada, "collections")
        self.assertEqual(log.entidade_id, coleta_id)
        self.assertEqual(log.valor_anterior_json, {"status": "FINALIZADA"})
        self.assertEqual(log.valor_novo_json, {"status": "CONTESTADA"})
        self.assertIsNotNone(log.created_at)
        self.assertTrue(log.ip_origem)

    # --- matriz doc 04: ADMIN pode atuar na mediação ---

    def test_16_administrador_pode_contestar_conforme_matriz(self):
        _, _, coleta_id = self.levar_ate("FINALIZADA", "s16")
        admin = self.admin_headers(email="adm-mediador@test.com")
        resposta = self.contestar(admin, coleta_id)
        self.assertEqual(resposta.status_code, 200, resposta.text)
        logs = self.logs_de(coleta_id)
        self.assertEqual(len(logs), 1)
        with sessionmaker(bind=self.engine)() as db:
            self.assertEqual(db.get(User, logs[0].user_id).role, "ADMINISTRADOR")
        # Inexistente continua indistinguível para o admin.
        import uuid as uuid_lib
        inexistentes = self.contestar(admin, str(uuid_lib.uuid4()))
        self.assertEqual(inexistentes.status_code, 404)
