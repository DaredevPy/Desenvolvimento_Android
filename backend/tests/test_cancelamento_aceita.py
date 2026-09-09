# backend/tests/test_cancelamento_aceita.py
# Missão 55.3 — Auditoria final do cancelamento pós-ACEITA.
# Cobre especificamente o fluxo ACEITA -> CANCELADA (PRESTADOR/ADMINISTRADOR)
# com justificativa (X-Justificativa) e idempotência (X-Idempotency-Key UUIDv4),
# máquina de estados, autorização, reprodução idempotente e auditoria.
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
from backend.db.models import AuditLog, Base, Collection, IdempotencyRecord, User

SECRET_TESTE = "chave-de-teste-com-mais-de-32-bytes-para-hmac-sha256-0123456789"

SENHA = "senha@123"
DADOS_PERFIL = {
    "nome_razao_social": "Cancelamento Aceita Teste LTDA",
    "telefone": "(11) 95555-4444",
}
_CPF_SEQ = count(70_000_000_000_007, 17)

_ESTADOS_POR_PASSO = [
    "EM_DESLOCAMENTO",
    "EM_CONFERENCIA",
    "CARREGADA",
]


def payload_coleta():
    return {
        "endereco_origem_json": {"rua": "Rua da Oficina", "numero": "200", "cidade": "São Paulo"},
        "data_agendada": datetime.now(timezone.utc).isoformat(),
        "itens": [{"marca": "Michelin", "dimensao": "275/80R22.5", "quantidade_declarada": 120}],
    }


class TestCancelamentoAceita(unittest.TestCase):
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

    def criar_coleta_aceita(self, sufixo="a", prestador_email=None):
        """Cria uma coleta SOLICITADA e a leva a ACEITA por um prestador."""
        cliente_email = f"ca-cil{sufixo}@test.com"
        self.garantir_perfil(cliente_email)
        cliente = self.headers_de(cliente_email)
        resposta = self.client.post("/api/v1/collections", json=payload_coleta(), headers=cliente)
        self.assertEqual(resposta.status_code, 201, resposta.text)
        coleta_id = resposta.json()["id"]

        prestador_email = prestador_email or f"ca-prest{sufixo}@test.com"
        self.garantir_perfil(prestador_email, rota="provider")
        prestador = self.headers_de(prestador_email)
        aceite = self.client.post(f"/api/v1/collections/{coleta_id}/aceitar", headers=prestador)
        self.assertEqual(aceite.status_code, 200, aceite.text)
        return cliente, prestador, coleta_id

    def cancelar_com(self, cabecalhos, coleta_id, *, justificativa=None, chave=None):
        headers = dict(cabecalhos)
        if justificativa is not None:
            headers["X-Justificativa"] = justificativa
        if chave is not None:
            headers["X-Idempotency-Key"] = chave
        return self.client.post(f"/api/v1/collections/{coleta_id}/cancelar", headers=headers)

    def avançar_ate(self, coleta_id, prestador, estado):
        for passo in _ESTADOS_POR_PASSO:
            resposta = self.client.post(
                f"/api/v1/collections/{coleta_id}/status",
                json={"novo_status": passo},
                headers=prestador,
            )
            self.assertEqual(resposta.status_code, 200, f"{passo}: {resposta.text}")
            if passo == estado:
                break

    def audits_cancel(self, coleta_id):
        with sessionmaker(bind=self.engine)() as db:
            return db.scalars(
                select(AuditLog).where(
                    AuditLog.acao == "CANCELACAO_COLETA",
                    AuditLog.entidade_id == coleta_id,
                )
            ).all()

    def registros_cancelacao(self, coleta_id=None):
        with sessionmaker(bind=self.engine)() as db:
            consulta = select(IdempotencyRecord).where(IdempotencyRecord.escopo == "CANCELACAO")
            if coleta_id is not None:
                consulta = consulta.where(IdempotencyRecord.recurso_id == coleta_id)
            return db.scalars(consulta).all()

    # --- fluxo principal ACEITA -> CANCELADA ---

    def test_01_prestador_responsavel_cancela_aceita_com_sucesso(self):
        _, prestador, coleta_id = self.criar_coleta_aceita("01")
        chave = str(uuid_lib.uuid4())
        resposta = self.cancelar_com(
            prestador, coleta_id, justificativa="Cliente desistiu no local.", chave=chave
        )
        self.assertEqual(resposta.status_code, 200, resposta.text)
        self.assertEqual(resposta.json()["status"], "CANCELADA")
        self.assertEqual(resposta.json()["justificativa"], "Cliente desistiu no local.")

        with sessionmaker(bind=self.engine)() as db:
            coleta = db.get(Collection, coleta_id)
            self.assertEqual(coleta.status, "CANCELADA")
            self.assertIsNotNone(coleta.provider_id)

        audits = self.audits_cancel(coleta_id)
        self.assertEqual(len(audits), 1)
        self.assertEqual(audits[0].valor_novo_json, {"status": "CANCELADA", "justificativa": "Cliente desistiu no local."})
        registros = self.registros_cancelacao(coleta_id)
        self.assertEqual(len(registros), 1)
        self.assertEqual(registros[0].chave, chave)
        self.assertEqual(registros[0].recurso_id, coleta_id)

    def test_02_replay_mesma_chave_nao_duplica_efeito_nem_auditoria(self):
        _, prestador, coleta_id = self.criar_coleta_aceita("02")
        chave = str(uuid_lib.uuid4())
        primeira = self.cancelar_com(prestador, coleta_id, justificativa="Motivo X.", chave=chave)
        self.assertEqual(primeira.status_code, 200, primeira.text)

        replay = self.cancelar_com(prestador, coleta_id, justificativa="Motivo X.", chave=chave)
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertEqual(replay.json(), primeira.json())

        self.assertEqual(len(self.audits_cancel(coleta_id)), 1)
        self.assertEqual(len(self.registros_cancelacao(coleta_id)), 1)
        with sessionmaker(bind=self.engine)() as db:
            self.assertEqual(db.get(Collection, coleta_id).status, "CANCELADA")

    def test_03_mesma_chave_com_justificativa_diferente_eh_rejeitada_409(self):
        _, prestador, coleta_id = self.criar_coleta_aceita("03")
        chave = str(uuid_lib.uuid4())
        primeira = self.cancelar_com(prestador, coleta_id, justificativa="Motivo X.", chave=chave)
        self.assertEqual(primeira.status_code, 200, primeira.text)

        divergente = self.cancelar_com(prestador, coleta_id, justificativa="Outro motivo.", chave=chave)
        self.assertEqual(divergente.status_code, 409, divergente.text)

    def test_04_chave_obrigatoria_e_uuidv4(self):
        _, prestador, coleta_id = self.criar_coleta_aceita("04")

        sem_chave = self.cancelar_com(prestador, coleta_id, justificativa="Motivo.")
        self.assertEqual(sem_chave.status_code, 422, sem_chave.text)

        chave_v1 = "11111111-1111-1111-1111-111111111111"
        chave_invalida = self.cancelar_com(prestador, coleta_id, justificativa="Motivo.", chave=chave_v1)
        self.assertEqual(chave_invalida.status_code, 422, chave_invalida.text)

        chave_lixo = self.cancelar_com(prestador, coleta_id, justificativa="Motivo.", chave="nao-e-um-uuid")
        self.assertEqual(chave_lixo.status_code, 422, chave_lixo.text)

    def test_05_justificativa_obrigatoria_e_texto_livre(self):
        _, prestador, coleta_id = self.criar_coleta_aceita("05")
        chave = str(uuid_lib.uuid4())

        sem_just = self.cancelar_com(prestador, coleta_id, chave=chave)
        self.assertEqual(sem_just.status_code, 422, sem_just.text)

        just_branco = self.cancelar_com(prestador, coleta_id, justificativa="   ", chave=chave)
        self.assertEqual(just_branco.status_code, 422, just_branco.text)

        just_curta = self.cancelar_com(prestador, coleta_id, justificativa="X", chave=chave)
        self.assertEqual(just_curta.status_code, 200, just_curta.text)

    def test_06_prestador_nao_responsavel_nao_cancela_404(self):
        _, _, coleta_id = self.criar_coleta_aceita("06")
        self.garantir_perfil("ca-outsider@test.com", rota="provider")
        outsider = self.headers_de("ca-outsider@test.com")
        resposta = self.cancelar_com(
            outsider, coleta_id, justificativa="Tentativa alheia.", chave=str(uuid_lib.uuid4())
        )
        self.assertEqual(resposta.status_code, 404, resposta.text)
        with sessionmaker(bind=self.engine)() as db:
            self.assertEqual(db.get(Collection, coleta_id).status, "ACEITA")
        self.assertEqual(self.audits_cancel(coleta_id), [])

    def test_07_cliente_nao_cancela_apos_aceita_409(self):
        cliente, _, coleta_id = self.criar_coleta_aceita("07")
        resposta = self.cancelar_com(cliente, coleta_id, justificativa="Tentativa.")
        self.assertEqual(resposta.status_code, 409, resposta.text)
        with sessionmaker(bind=self.engine)() as db:
            self.assertEqual(db.get(Collection, coleta_id).status, "ACEITA")

    def test_08_admin_cancela_qualquer_coleta_aceita(self):
        from backend.app import security

        email = "ca-admin@test.com"
        with sessionmaker(bind=self.engine)() as db:
            db.add(User(email=email, password_hash=security.hash_password(SENHA), role="ADMINISTRADOR"))
            db.commit()
        admin = self.headers_de(email)
        _, _, coleta_id = self.criar_coleta_aceita("08")
        resposta = self.cancelar_com(
            admin, coleta_id, justificativa="Intervencao administrativa.", chave=str(uuid_lib.uuid4())
        )
        self.assertEqual(resposta.status_code, 200, resposta.text)
        with sessionmaker(bind=self.engine)() as db:
            self.assertEqual(db.get(Collection, coleta_id).status, "CANCELADA")

    def test_09_estados_incompativeis_continuam_bloqueados_409(self):
        for sufixo, estado in [
            ("09a", "EM_DESLOCAMENTO"),
            ("09b", "EM_CONFERENCIA"),
            ("09c", "CARREGADA"),
        ]:
            _, prestador, coleta_id = self.criar_coleta_aceita(sufixo)
            self.avançar_ate(coleta_id, prestador, estado)
            resposta = self.cancelar_com(
                prestador,
                coleta_id,
                justificativa="Tentativa em estado incompativel.",
                chave=str(uuid_lib.uuid4()),
            )
            self.assertEqual(resposta.status_code, 409, f"{estado}: {resposta.text}")

    def test_10_finalizada_nao_cancela_409(self):
        _, prestador, coleta_id = self.criar_coleta_aceita("10")
        self.avançar_ate(coleta_id, prestador, "CARREGADA")
        with sessionmaker(bind=self.engine)() as db:
            coleta = db.get(Collection, coleta_id)
            coleta.status = "FINALIZADA"
            coleta.data_finalizacao = datetime.now(timezone.utc)
            db.commit()

        bloqueio = self.cancelar_com(
            prestador, coleta_id, justificativa="Tentativa sobre FINALIZADA.", chave=str(uuid_lib.uuid4())
        )
        self.assertEqual(bloqueio.status_code, 409, bloqueio.text)

    def test_11_chave_de_outro_usuario_eh_404_uniforme(self):
        _, prestador_dono, coleta_id = self.criar_coleta_aceita("11")
        self.garantir_perfil("ca-d11-b@test.com", rota="provider")
        outro = self.headers_de("ca-d11-b@test.com")

        chave = str(uuid_lib.uuid4())
        dono_cancela = self.cancelar_com(
            prestador_dono, coleta_id, justificativa="Motivo do dono.", chave=chave
        )
        self.assertEqual(dono_cancela.status_code, 200, dono_cancela.text)

        replay_alheio = self.cancelar_com(
            outro, coleta_id, justificativa="Motivo do dono.", chave=chave
        )
        self.assertEqual(replay_alheio.status_code, 404, replay_alheio.text)

    def test_12_coleta_inexistente_404(self):
        self.garantir_perfil("ca-e12@test.com", rota="provider")
        prestador = self.headers_de("ca-e12@test.com")
        resposta = self.cancelar_com(
            prestador, str(uuid_lib.uuid4()), justificativa="Motivo.", chave=str(uuid_lib.uuid4())
        )
        self.assertEqual(resposta.status_code, 404, resposta.text)


if __name__ == "__main__":
    unittest.main()