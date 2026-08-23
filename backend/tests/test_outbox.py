# backend/tests/test_outbox.py
# Missão 13: idempotência offline em pneus/conclusão/finalização (doc 09 §§2/4.1).
import os
import tempfile
import threading
import unittest
import uuid as uuid_lib
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
    Base,
    Collection,
    CollectionItemChecked,
    FinancialTransaction,
    IdempotencyRecord,
    Tire,
    User,
)

SECRET_TESTE = "chave-de-teste-com-mais-de-32-bytes-para-hmac-sha256-0123456789"
SENHA = "senha@123"
DADOS_PERFIL = {"nome_razao_social": "Outbox Teste LTDA", "telefone": "(13) 95555-3333"}
_CPF_SEQ = count(20_000_000_001, 53)
_CHAVE_A = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_CHAVE_B = "3f2a8c41-9d0e-4b7a-a1c5-6e8f2d9b0c33"
_CHAVE_C = "5e4d3c2b-1a09-48f7-b6e5-d4c3b2a19080"


class TestOutbox(unittest.TestCase):
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
        # Arquivo + NullPool: uma conexão por requisição, semântica PostgreSQL;
        # necessária para o teste de corrida (StaticPool compartilharia conexão).
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
            dados["dados_veiculo_json"] = {"placa": "OBX1A11", "tipo": "truck"}
        resposta = self.client.post(
            f"/api/v1/profile/{rota}", json=dados, headers=self.headers_de(email)
        )
        self.assertIn(resposta.status_code, (201, 409), resposta.text)

    def admin_headers(self, email="adm-outbox@test.com"):
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
        resposta = self.client.post("/api/v1/admin/pricing-rules", json=base, headers=cabecalhos)
        self.assertEqual(resposta.status_code, 201, resposta.text)

    def criar_coleta(self, cliente, prestador):
        resposta = self.client.post(
            "/api/v1/collections",
            json={
                "endereco_origem_json": {"rua": "Rua do Outbox", "numero": "7", "cidade": "Santos"},
                "data_agendada": self._agora,
                "itens": [
                    {"marca": "Pirelli", "dimensao": "295/80R22.5", "quantidade_declarada": 250}
                ],
            },
            headers=cliente,
        )
        self.assertEqual(resposta.status_code, 201, resposta.text)
        coleta_id = resposta.json()["id"]
        self.client.post(f"/api/v1/collections/{coleta_id}/aceitar", headers=prestador)
        self.client.post(
            f"/api/v1/collections/{coleta_id}/status",
            json={"novo_status": "EM_DESLOCAMENTO"},
            headers=prestador,
        )
        self.client.post(f"/api/v1/collections/{coleta_id}/conferencia/iniciar", headers=prestador)
        return coleta_id

    def pneus(self, quantidade, dot="2526", prefixo_nf=None):
        lista = []
        for indice in range(quantidade):
            pneu = {"marca": "Pirelli", "medida": "295/80R22.5", "dot": dot}
            if prefixo_nf is not None:
                pneu["numero_fogo"] = f"{prefixo_nf}{indice:04d}"
            lista.append(pneu)
        return lista

    def enviar_pneus(self, prestador, coleta_id, pneus, chave=None):
        cabecalhos = dict(prestador)
        if chave is not None:
            cabecalhos["X-Idempotency-Key"] = chave
        return self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/pneus",
            json={"pneus": pneus},
            headers=cabecalhos,
        )

    def pneus_no_banco(self, coleta_id):
        with sessionmaker(bind=self.engine)() as db:
            return db.scalars(select(Tire.id).where(Tire.collection_id == coleta_id)).all()

    def registros_idempotencia(self, escopo=None):
        with sessionmaker(bind=self.engine)() as db:
            consulta = select(IdempotencyRecord)
            if escopo is not None:
                consulta = consulta.where(IdempotencyRecord.escopo == escopo)
            return db.scalars(consulta.order_by(IdempotencyRecord.created_at.asc())).all()

    # --- 1 a 7: ciclo completo do lote de pneus ---

    def test_01_primeiro_envio_do_lote_executa_normalmente(self):
        self.garantir_perfil("obx-c1@test.com")
        self.garantir_perfil("obx-p1@test.com", rota="provider")
        prestador = self.headers_de("obx-p1@test.com")
        coleta_id = self.criar_coleta(self.headers_de("obx-c1@test.com"), prestador)
        resposta = self.enviar_pneus(
            prestador, coleta_id, self.pneus(3, prefixo_nf="NFA"), chave=_CHAVE_A
        )
        self.assertEqual(resposta.status_code, 201, resposta.text)
        self.assertEqual(len(resposta.json()), 3)
        self.assertEqual(len(self.pneus_no_banco(coleta_id)), 3)
        registros = self.registros_idempotencia("PNEUS")
        self.assertEqual(len(registros), 1)
        self.assertEqual(registros[0].chave, _CHAVE_A)
        self.assertEqual(registros[0].recurso_id, coleta_id)

    def test_02_replay_do_lote_nao_insere_pneus_novamente(self):
        self.garantir_perfil("obx-c2@test.com")
        self.garantir_perfil("obx-p2@test.com", rota="provider")
        prestador = self.headers_de("obx-p2@test.com")
        coleta_id = self.criar_coleta(self.headers_de("obx-c2@test.com"), prestador)
        lote = self.pneus(3, prefixo_nf="NFB")
        primeira = self.enviar_pneus(prestador, coleta_id, lote, chave=_CHAVE_A)
        self.assertEqual(primeira.status_code, 201, primeira.text)
        segunda = self.enviar_pneus(prestador, coleta_id, lote, chave=_CHAVE_A)
        self.assertEqual(segunda.status_code, 200, segunda.text)
        self.assertEqual(primeira.json(), segunda.json())
        self.assertEqual(len(self.pneus_no_banco(coleta_id)), 3)
        self.assertEqual(len(self.registros_idempotencia()), 1)

    def test_03_mesma_chave_com_lote_diferente_rejeitado(self):
        self.garantir_perfil("obx-c3@test.com")
        self.garantir_perfil("obx-p3@test.com", rota="provider")
        prestador = self.headers_de("obx-p3@test.com")
        coleta_id = self.criar_coleta(self.headers_de("obx-c3@test.com"), prestador)
        primeira = self.enviar_pneus(
            prestador, coleta_id, self.pneus(2, dot="1012", prefixo_nf="NFC"), chave=_CHAVE_A
        )
        self.assertEqual(primeira.status_code, 201, primeira.text)
        divergente = self.enviar_pneus(
            prestador, coleta_id, self.pneus(5, dot="1012", prefixo_nf="NFC"), chave=_CHAVE_A
        )
        self.assertEqual(divergente.status_code, 409, divergente.text)
        self.assertIn("diferente", divergente.json()["detail"])
        self.assertEqual(len(self.pneus_no_banco(coleta_id)), 2)

    def test_04_chave_de_outro_usuario_eh_indistinguivel_de_inexistente(self):
        self.garantir_perfil("obx-c4@test.com")
        self.garantir_perfil("obx-p4a@test.com", rota="provider")
        self.garantir_perfil("obx-p4b@test.com", rota="provider")
        dono = self.headers_de("obx-p4a@test.com")
        alheio = self.headers_de("obx-p4b@test.com")
        coleta_alheia = self.criar_coleta(self.headers_de("obx-c4@test.com"), alheio)
        resposta = self.enviar_pneus(
            dono, coleta_alheia, self.pneus(1, prefixo_nf="NFD"), chave=_CHAVE_A
        )
        self.assertEqual(resposta.status_code, 404, resposta.text)
        self.assertEqual(resposta.json()["detail"], "Recurso não encontrado.")
        self.assertEqual(len(self.pneus_no_banco(coleta_alheia)), 0)

    def test_05_requests_simultaneos_produzem_apenas_um_efeito(self):
        self.garantir_perfil("obx-c5@test.com")
        self.garantir_perfil("obx-p5@test.com", rota="provider")
        prestador = dict(
            self.headers_de("obx-p5@test.com"), **{"X-Idempotency-Key": _CHAVE_A}
        )
        coleta_id = self.criar_coleta(self.headers_de("obx-c5@test.com"), prestador)
        corpo = {"pneus": self.pneus(3, prefixo_nf="NFE")}
        barreira = threading.Barrier(2)
        respostas = []

        def disparar():
            cliente_http = TestClient(app)
            try:
                barreira.wait(timeout=10)
                respostas.append(
                    cliente_http.post(
                        f"/api/v1/collections/{coleta_id}/conferencia/pneus",
                        json=corpo,
                        headers=prestador,
                    )
                )
            except Exception as erro:
                respostas.append(erro)

        fios = [threading.Thread(target=disparar) for _ in range(2)]
        for fio in fios:
            fio.start()
        for fio in fios:
            fio.join(timeout=30)
        self.assertEqual(len(respostas), 2)
        for resposta in respostas:
            # No sqlite o FOR UPDATE é ignorado: além de 200/201, o perdedor
            # pode receber 409 de NF duplicado se passar do replay antes do
            # commit do vencedor. O efeito único é o contrato obrigatório.
            self.assertIn(resposta.status_code, (200, 201, 409), str(resposta))
        self.assertTrue(any(r.status_code in (200, 201) for r in respostas))
        self.assertEqual(len(self.pneus_no_banco(coleta_id)), 3)
        self.assertEqual(len(self.registros_idempotencia()), 1)

    def test_06_falha_no_meio_do_lote_nao_deixa_registro_parcial(self):
        self.garantir_perfil("obx-c6@test.com")
        self.garantir_perfil("obx-p6@test.com", rota="provider")
        prestador = self.headers_de("obx-p6@test.com")
        coleta_id = self.criar_coleta(self.headers_de("obx-c6@test.com"), prestador)
        lote_quebrado = self.pneus(2, prefixo_nf="NFF") + [{"marca": "Pirelli", "medida": "295/80R22.5", "dot": "2526", "numero_fogo": "NFF0000"}]
        resposta = self.enviar_pneus(
            prestador, coleta_id, lote_quebrado, chave=_CHAVE_A
        )
        self.assertEqual(resposta.status_code, 409, resposta.text)
        # Tudo-ou-nada: nenhum dos 3 permanece gravado...
        self.assertEqual(len(self.pneus_no_banco(coleta_id)), 0)
        # ...e a chave NÃO fica associada a operação parcial.
        self.assertEqual(len(self.registros_idempotencia()), 0)

    def test_07_retry_valido_apos_falha_executa_com_a_mesma_chave(self):
        self.garantir_perfil("obx-c7@test.com")
        self.garantir_perfil("obx-p7@test.com", rota="provider")
        prestador = self.headers_de("obx-p7@test.com")
        coleta_id = self.criar_coleta(self.headers_de("obx-c7@test.com"), prestador)
        quebrado = self.pneus(1, prefixo_nf="NFG") * 2
        self.assertEqual(
            self.enviar_pneus(prestador, coleta_id, quebrado, chave=_CHAVE_A).status_code, 409
        )
        recuperacao = self.enviar_pneus(
            prestador, coleta_id, self.pneus(2, prefixo_nf="NFG"), chave=_CHAVE_A
        )
        self.assertEqual(recuperacao.status_code, 201, recuperacao.text)
        self.assertEqual(len(self.pneus_no_banco(coleta_id)), 2)
        self.assertEqual(len(self.registros_idempotencia()), 1)

    # --- 8 e 9: regras críticas DOT / número de fogo ---

    def test_08_quinhentos_pneus_com_o_mesmo_dot_sao_aceitos(self):
        self.garantir_perfil("obx-c8@test.com")
        self.garantir_perfil("obx-p8@test.com", rota="provider")
        prestador = self.headers_de("obx-p8@test.com")
        coleta_id = self.criar_coleta(self.headers_de("obx-c8@test.com"), prestador)
        resposta = self.enviar_pneus(
            prestador, coleta_id, self.pneus(500, dot="2526"), chave=_CHAVE_A
        )
        self.assertEqual(resposta.status_code, 201, resposta.text[:300])
        self.assertEqual(len(self.pneus_no_banco(coleta_id)), 500)

    def test_09_numero_fogo_duplicado_na_mesma_coleta_continua_409(self):
        self.garantir_perfil("obx-c9@test.com")
        self.garantir_perfil("obx-p9@test.com", rota="provider")
        prestador = self.headers_de("obx-p9@test.com")
        coleta_id = self.criar_coleta(self.headers_de("obx-c9@test.com"), prestador)
        primeiro = self.enviar_pneus(
            prestador, coleta_id, self.pneus(1, prefixo_nf="NFZ"), chave=_CHAVE_A
        )
        self.assertEqual(primeiro.status_code, 201, primeiro.text)
        repetido = self.enviar_pneus(
            prestador, coleta_id, self.pneus(1, prefixo_nf="NFZ"), chave=_CHAVE_B
        )
        # Bloqueio definitivo na MESMA coleta; idempotência não o contorna
        # (chaves distintas => sem replay possível).
        self.assertEqual(repetido.status_code, 409, repetido.text)
        self.assertEqual(len(self.pneus_no_banco(coleta_id)), 1)

    # --- 10 a 12: conclusão e finalização ---

    def fluxo_ate_carregada(self, sufixo):
        self.garantir_perfil(f"obx-c{sufixo}@test.com")
        self.garantir_perfil(f"obx-p{sufixo}@test.com", rota="provider")
        cliente = self.headers_de(f"obx-c{sufixo}@test.com")
        prestador = self.headers_de(f"obx-p{sufixo}@test.com")
        coleta_id = self.criar_coleta(cliente, prestador)
        self.assertEqual(
            self.enviar_pneus(
                prestador, coleta_id, self.pneus(2, prefixo_nf=f"NF{sufixo}"), chave=_CHAVE_A
            ).status_code,
            201,
        )
        return coleta_id, prestador

    def concluir(self, prestador, coleta_id, chave=None):
        cabecalhos = dict(prestador)
        if chave is not None:
            cabecalhos["X-Idempotency-Key"] = chave
        return self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/concluir",
            json={
                "quantidade_conferida": 250,
                "quantidade_coletada": 2,
                "justificativa_divergencia": "Divergência documentada no teste.",
                "fotos_divergencia_json": {"fotos": ["foto-divergencia.jpg"]},
            },
            headers=cabecalhos,
        )

    def test_10_conclusao_duplicada_produz_um_unico_efeito(self):
        coleta_id, prestador = self.fluxo_ate_carregada("s10")
        primeira = self.concluir(prestador, coleta_id, chave=_CHAVE_B)
        self.assertEqual(primeira.status_code, 200, primeira.text)
        self.assertEqual(primeira.json(), {"id": coleta_id, "status": "CARREGADA"})
        repetida = self.concluir(prestador, coleta_id, chave=_CHAVE_B)
        # Mesma operação reenviada => replay, nunca segunda conclusão.
        self.assertEqual(repetida.status_code, 200, repetida.text)
        self.assertEqual(repetida.json(), primeira.json())
        outra_chave = self.concluir(prestador, coleta_id, chave=_CHAVE_A)
        self.assertEqual(outra_chave.status_code, 409)
        with sessionmaker(bind=self.engine)() as db:
            concluidas = db.scalars(
                select(CollectionItemChecked.id).where(
                    CollectionItemChecked.collection_id == coleta_id
                )
            ).all()
        self.assertEqual(len(concluidas), 1)

    def test_11_finalizacao_duplicada_cria_um_unico_par_de_lancamentos(self):
        coleta_id, prestador = self.fluxo_ate_carregada("s11")
        admin = self.admin_headers()
        self.criar_regra(admin, perfil_alvo="CLIENTE", valor_unitario="4.00")
        self.criar_regra(admin, perfil_alvo="PRESTADOR", valor_unitario="2.50")
        self.assertEqual(self.concluir(prestador, coleta_id, chave=_CHAVE_B).status_code, 200)

        def finalizar(chave=None):
            cabecalhos = dict(prestador)
            if chave is not None:
                cabecalhos["X-Idempotency-Key"] = chave
            return self.client.post(
                f"/api/v1/collections/{coleta_id}/finalizar", json={}, headers=cabecalhos
            )

        primeira = finalizar(chave=_CHAVE_C)
        self.assertEqual(primeira.status_code, 200, primeira.text)
        repetida = finalizar(chave=_CHAVE_C)
        # Replay da MESMA finalização: mesma resposta, nenhum lançamento novo.
        self.assertEqual(repetida.status_code, 200, repetida.text)
        self.assertEqual(repetida.json(), primeira.json())
        sem_chave = finalizar()
        self.assertEqual(sem_chave.status_code, 409)
        with sessionmaker(bind=self.engine)() as db:
            lancamentos = db.scalars(
                select(FinancialTransaction).where(FinancialTransaction.collection_id == coleta_id)
            ).all()
        self.assertEqual(len(lancamentos), 2)
        self.assertEqual({l.tipo_entidade for l in lancamentos}, {"CLIENTE", "PRESTADOR"})
        self.assertEqual(len(self.registros_idempotencia("FINALIZACAO")), 1)

    def test_12_snapshots_permanecem_imutaveis_apos_replays(self):
        coleta_id, prestador = self.fluxo_ate_carregada("s12")
        admin = self.admin_headers(email="adm-snap@test.com")
        self.criar_regra(admin, perfil_alvo="CLIENTE", valor_unitario="4.00")
        self.criar_regra(admin, perfil_alvo="PRESTADOR", valor_unitario="2.50")
        self.assertEqual(self.concluir(prestador, coleta_id, chave=_CHAVE_B).status_code, 200)
        primeira = self.client.post(
            f"/api/v1/collections/{coleta_id}/finalizar",
            json={},
            headers={**prestador, "X-Idempotency-Key": _CHAVE_C},
        )
        self.assertEqual(primeira.status_code, 200, primeira.text)
        for _ in range(2):
            repetida = self.client.post(
                f"/api/v1/collections/{coleta_id}/finalizar",
                json={},
                headers={**prestador, "X-Idempotency-Key": _CHAVE_C},
            )
            self.assertEqual(repetida.json(), primeira.json())
        with sessionmaker(bind=self.engine)() as db:
            coleta = db.get(Collection, coleta_id)
            cliente = float(coleta.snapshot_valor_cliente)
            prestador_valor = float(coleta.snapshot_valor_prestador)
            estado = coleta.status
        self.assertEqual((cliente, prestador_valor), (8.00, 5.00))
        self.assertEqual(estado, "FINALIZADA")

    # --- 13: RBAC e ownership preservados ---

    def test_13_rbac_e_ownership_permanecem_em_todos_os_fluxos(self):
        self.garantir_perfil("obx-c13@test.com")
        self.garantir_perfil("obx-p13a@test.com", rota="provider")
        self.garantir_perfil("obx-p13b@test.com", rota="provider")
        cliente = self.headers_de("obx-c13@test.com")
        dono = self.headers_de("obx-p13a@test.com")
        intruso = self.headers_de("obx-p13b@test.com")
        coleta_id = self.criar_coleta(cliente, dono)
        for metodo, caminho, corpo in (
            ("post", f"/api/v1/collections/{coleta_id}/conferencia/pneus", {"pneus": self.pneus(1)}),
            ("post", f"/api/v1/collections/{coleta_id}/conferencia/concluir", {"quantidade_conferida": 250, "quantidade_coletada": 0}),
            ("post", f"/api/v1/collections/{coleta_id}/finalizar", {}),
        ):
            proibido = getattr(self.client, metodo)(caminho, json=corpo, headers=cliente)
            self.assertEqual(proibido.status_code, 403, f"{caminho}: {proibido.text}")
        invadido = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/pneus",
            json={"pneus": self.pneus(1)},
            headers=intruso,
        )
        self.assertEqual(invadido.status_code, 404, invadido.text)
        self.assertEqual(invadido.json()["detail"], "Recurso não encontrado.")
