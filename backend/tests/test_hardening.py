# backend/tests/test_hardening.py
# Missão 15: hardening de segurança da API (rate limiting, cabeçalhos HTTP,
# limites de entrada) sem regressão de JWT/RBAC/ownership/idempotência/estados/
# regras financeiras.
import os
import tempfile
import time
import unittest
import uuid as uuid_lib
from datetime import date, datetime, timezone
from itertools import count
from unittest import mock

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from backend.app import main as app_main
from backend.app import rate_limit, security
from backend.app.main import app
from backend.db import session as db_session
from backend.db.models import Base, Collection, User

SECRET_TESTE = "chave-de-teste-com-mais-de-32-bytes-para-hmac-sha256-0123456789"
SENHA = "senha@123"
MSG_INVALIDAS = "Credenciais inválidas."
MSG_RATE_LIMIT = "Muitas requisições. Aguarde antes de tentar novamente."
NAO_ENCONTRADO = "Recurso não encontrado."
DADOS_PERFIL = {"nome_razao_social": "Hardening Teste LTDA", "telefone": "(11) 93333-2222"}
_CPF_SEQ = count(90_000_000_001, 37)

CABECALHOS_OBRIGATORIOS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


class TestHardening(unittest.TestCase):
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
        rate_limit.limpar_estado()
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
        self.agora = datetime.now(timezone.utc).isoformat()

    def tearDown(self):
        self._patcher.stop()
        self.engine.dispose()
        os.unlink(self._arquivo_db.name)
        rate_limit.limpar_estado()

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
        dados = {**DADOS_PERFIL, "cpf_cnpj": self.novo_cpf()}
        if rota == "provider":
            dados["dados_veiculo_json"] = {"placa": "HDN1B23", "tipo": "truck"}
            self.registrar(email, role="PRESTADOR")
        else:
            self.registrar(email)
        resposta = self.client.post(
            f"/api/v1/profile/{rota}", json=dados, headers=self.headers_de(email)
        )
        self.assertIn(resposta.status_code, (201, 409), resposta.text)

    def usuario_id(self, email):
        with sessionmaker(bind=self.engine)() as db:
            return db.scalars(select(User.id).where(User.email == email)).first()

    def admin_headers(self, email="adm-hard@test.com"):
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

    def payload_coleta(self, itens=None, endereco=None):
        return {
            "endereco_origem_json": endereco or {"rua": "Rua do Hardening", "numero": "15", "cidade": "Santos"},
            "data_agendada": self.agora,
            "itens": itens if itens is not None else [
                {"marca": "Michelin", "dimensao": "275/80R22.5", "quantidade_declarada": 250}
            ],
        }

    def criar_coleta(self, cliente):
        resposta = self.client.post("/api/v1/collections", json=self.payload_coleta(), headers=cliente)
        self.assertEqual(resposta.status_code, 201, resposta.text)
        return resposta.json()["id"]

    def pneu_payload(self, numero_fogo):
        return {"marca": "Michelin", "medida": "275/80R22.5", "dot": "2526", "numero_fogo": numero_fogo}

    def levar_ate_carregada(self, cliente, prestador, coleta_id, sufixo_nf):
        self.assertEqual(
            self.client.post(f"/api/v1/collections/{coleta_id}/aceitar", headers=prestador).status_code, 200
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/collections/{coleta_id}/status",
                json={"novo_status": "EM_DESLOCAMENTO"},
                headers=prestador,
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(f"/api/v1/collections/{coleta_id}/conferencia/iniciar", headers=prestador).status_code,
            200,
        )
        lote = [self.pneu_payload(f"HD{sufixo_nf}{i:03d}") for i in range(2)]
        self.assertEqual(
            self.client.post(
                f"/api/v1/collections/{coleta_id}/conferencia/pneus", json={"pneus": lote}, headers=prestador
            ).status_code,
            201,
        )
        conclusao = self.client.post(
            f"/api/v1/collections/{coleta_id}/conferencia/concluir",
            json={
                "quantidade_conferida": 250,
                "quantidade_coletada": 2,
                "justificativa_divergencia": "Divergência documentada.",
                "fotos_divergencia_json": {"fotos": ["foto.jpg"]},
            },
            headers=prestador,
        )
        self.assertEqual(conclusao.status_code, 200, conclusao.text)

    # --- 7: cabeçalhos de segurança presentes (requisito 7) ---

    def test_01_cabecalhos_seguranca_em_resposta_ok(self):
        resposta = self.client.get("/health")
        self.assertEqual(resposta.status_code, 200)
        for cabecalho, valor in CABECALHOS_OBRIGATORIOS.items():
            self.assertEqual(resposta.headers.get(cabecalho), valor, cabecalho)
        csp = resposta.headers.get("Content-Security-Policy")
        self.assertIn("default-src 'none'", csp)
        self.assertIn("frame-ancestors 'none'", csp)

    def test_02_cabecalhos_seguranca_em_respostas_de_erro(self):
        for metodo, caminho, kwargs in (
            (self.client.get, "/api/v1/auth/me", {}),
            (self.client.post, "/api/v1/auth/login", {"json": {"email": "invalido"}}),
            (self.client.get, "/api/v1/inexistente", {}),
        ):
            resposta = metodo(caminho, **kwargs)
            self.assertIn(resposta.status_code, (401, 422, 404))
            for cabecalho, valor in CABECALHOS_OBRIGATORIOS.items():
                self.assertEqual(resposta.headers.get(cabecalho), valor, cabecalho)

    # --- HSTS somente com HTTPS garantido (requisito 7) ---

    def test_03_hsts_condicionado_a_https_garantido(self):
        resposta = self.client.get("/health")
        self.assertIsNone(resposta.headers.get("Strict-Transport-Security"))
        with mock.patch.object(app_main, "HSTS_HABILITADO", True):
            resposta = self.client.get("/health")
        self.assertEqual(
            resposta.headers.get("Strict-Transport-Security"),
            "max-age=31536000; includeSubDomains",
        )

    # --- 8: corpo excessivo rejeitado antes das rotas ---

    def test_04_corpo_excessivo_rejeitado_413_sem_processar(self):
        resposta = self.client.post(
            "/api/v1/auth/register",
            json={"email": "hd-corpo@test.com", "senha": "a" * 1_100_000},
        )
        self.assertEqual(resposta.status_code, 413)
        with sessionmaker(bind=self.engine)() as db:
            self.assertIsNone(db.scalars(select(User).where(User.email == "hd-corpo@test.com")).first())

    # --- Swagger/OpenAPI segue utilizável no desenvolvimento local ---

    def test_05_documentacao_openapi_preservada_sem_csp(self):
        resposta = self.client.get("/openapi.json")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertIsNone(resposta.headers.get("Content-Security-Policy"))

    # --- 6: abaixo do limite continua funcionando / mecanismo desligado por padrão ---

    def test_06_rate_limit_desativado_por_padrao_nao_bloqueia(self):
        self.assertLessEqual(rate_limit.LIMITE_LOGIN, 0)
        self.assertLessEqual(rate_limit.LIMITE_REGISTRO, 0)
        self.registrar("hd-sem-limite@test.com")
        for i in range(8):
            resposta = self.client.post(
                "/api/v1/auth/login",
                json={"email": "hd-sem-limite@test.com", "senha": SENHA if i % 2 else "errada"},
            )
            self.assertIn(resposta.status_code, (200, 401))
            self.assertNotEqual(resposta.status_code, 429)

    # --- 4/5: login repetido sofre rate limit determinístico ---

    def test_07_login_repetido_excede_limite_e_recebe_429(self):
        self.registrar("hd-brute@test.com")
        with mock.patch.object(rate_limit, "LIMITE_LOGIN", 3):
            for _ in range(3):
                resposta = self.client.post(
                    "/api/v1/auth/login", json={"email": "hd-brute@test.com", "senha": "errada"}
                )
                self.assertEqual(resposta.status_code, 401)
            bloqueada = self.client.post(
                "/api/v1/auth/login", json={"email": "hd-brute@test.com", "senha": SENHA}
            )
        self.assertEqual(bloqueada.status_code, 429)
        self.assertEqual(bloqueada.json()["detail"], MSG_RATE_LIMIT)
        self.assertGreaterEqual(int(bloqueada.headers["Retry-After"]), 1)

    def test_08_janela_deslizante_e_deterministica(self):
        self.registrar("hd-janela@test.com")
        corpo = {"email": "hd-janela@test.com", "senha": "errada"}
        with mock.patch.object(rate_limit, "LIMITE_LOGIN", 2):
            self.assertEqual(self.client.post("/api/v1/auth/login", json=corpo).status_code, 401)
            self.assertEqual(self.client.post("/api/v1/auth/login", json=corpo).status_code, 401)
            self.assertEqual(self.client.post("/api/v1/auth/login", json=corpo).status_code, 429)
            # Janela expira: a mesma chave volta a ser aceita de forma idêntica.
            chave = "login:testclient"
            self.assertIn(chave, rate_limit._janelas)
            rate_limit._janelas[chave] = [time.monotonic() - rate_limit.JANELA_SEGUNDOS - 1]
            self.assertEqual(self.client.post("/api/v1/auth/login", json=corpo).status_code, 401)
            # Recarregada a janela, o bloqueio se repete exatamente no limite.
            self.client.post("/api/v1/auth/login", json=corpo)
            self.assertEqual(self.client.post("/api/v1/auth/login", json=corpo).status_code, 429)

    def test_09_login_e_registro_possuem_baldes_independentes(self):
        self.registrar("hd-balde-a@test.com")
        with mock.patch.object(rate_limit, "LIMITE_LOGIN", 2), mock.patch.object(rate_limit, "LIMITE_REGISTRO", 2):
            corpo_login = {"email": "hd-balde-a@test.com", "senha": "x"}
            self.assertEqual(self.client.post("/api/v1/auth/login", json=corpo_login).status_code, 401)
            self.assertEqual(self.client.post("/api/v1/auth/login", json=corpo_login).status_code, 401)
            self.assertEqual(self.client.post("/api/v1/auth/login", json=corpo_login).status_code, 429)
            # Login esgotado não consome o balde do registro.
            resposta_registro = self.client.post(
                "/api/v1/auth/register", json={"email": "hd-balde-b@test.com", "senha": SENHA}
            )
            self.assertEqual(resposta_registro.status_code, 201)
            resposta_registro = self.client.post(
                "/api/v1/auth/register", json={"email": "hd-balde-c@test.com", "senha": SENHA}
            )
            self.assertEqual(resposta_registro.status_code, 201)
            resposta_excesso = self.client.post(
                "/api/v1/auth/register", json={"email": "hd-balde-d@test.com", "senha": SENHA}
            )
        self.assertEqual(resposta_excesso.status_code, 429)

    # --- 14: nenhuma enumeração de contas via login ou rate limit ---

    def test_10_rate_limit_nao_revela_existencia_de_conta(self):
        self.registrar("hd-enum@test.com")
        respostas_429 = []
        with mock.patch.object(rate_limit, "LIMITE_LOGIN", 1):
            for email in ("hd-enum@test.com", "fantasma-hard@test.com"):
                rate_limit.limpar_estado()
                primeira = self.client.post("/api/v1/auth/login", json={"email": email, "senha": "errada"})
                self.assertEqual(primeira.status_code, 401)
                self.assertEqual(primeira.json()["detail"], MSG_INVALIDAS)
                segunda = self.client.post("/api/v1/auth/login", json={"email": email, "senha": "errada"})
                respostas_429.append((segunda.status_code, segunda.json()))
        self.assertEqual(respostas_429[0], respostas_429[1])
        self.assertEqual(respostas_429[0][0], 429)

    # --- 1: endpoint protegido continua exigindo autenticação ---

    def test_11_endpoint_protegido_exige_autenticacao(self):
        for metodo, caminho in (
            (self.client.get, "/api/v1/collections"),
            (self.client.post, "/api/v1/collections"),
            (self.client.get, "/api/v1/auth/me"),
            (self.client.get, "/api/v1/admin/pricing-rules"),
        ):
            self.assertEqual(metodo(caminho).status_code, 401, caminho)
        intruso = {"Authorization": "Bearer nao-e-um-jwt"}
        self.assertEqual(self.client.get("/api/v1/collections", headers=intruso).status_code, 401)

    # --- 2: RBAC continua funcionando ---

    def test_12_rbac_continua_bloqueando_perfis_indevidos(self):
        self.garantir_perfil("hd-rbac-c@test.com")
        self.garantir_perfil("hd-rbac-p@test.com", rota="provider")
        cliente = self.headers_de("hd-rbac-c@test.com")
        prestador = self.headers_de("hd-rbac-p@test.com")
        self.assertEqual(
            self.client.get("/api/v1/admin/pricing-rules", headers=cliente).status_code, 403
        )
        self.assertEqual(
            self.client.get("/api/v1/admin/pricing-rules", headers=prestador).status_code, 403
        )
        admin = self.admin_headers()
        self.assertEqual(self.client.get("/api/v1/admin/pricing-rules", headers=admin).status_code, 200)

    # --- 3: ownership continua funcionando ---

    def test_13_ownership_continua_isolando_coletas(self):
        self.garantir_perfil("hd-dono@test.com")
        self.garantir_perfil("hd-intruso@test.com")
        dono = self.headers_de("hd-dono@test.com")
        intruso = self.headers_de("hd-intruso@test.com")
        coleta_id = self.criar_coleta(dono)
        resposta = self.client.get(f"/api/v1/collections/{coleta_id}", headers=intruso)
        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(resposta.json()["detail"], NAO_ENCONTRADO)
        ids_do_intruso = [c["id"] for c in self.client.get("/api/v1/collections", headers=intruso).json()]
        self.assertNotIn(coleta_id, ids_do_intruso)

    # --- 9: identidade/ownership não podem ser manipulados pelo payload ---

    def test_14_manipulacao_de_identidade_no_payload_bloqueada(self):
        self.registrar("hd-identidade@test.com")
        cliente = self.headers_de("hd-identidade@test.com")
        corpo = self.payload_coleta()
        corpo["client_id"] = str(uuid_lib.uuid4())
        self.assertEqual(self.client.post("/api/v1/collections", json=corpo, headers=cliente).status_code, 422)
        perfil = {**DADOS_PERFIL, "cpf_cnpj": self.novo_cpf(), "user_id": str(uuid_lib.uuid4())}
        self.assertEqual(
            self.client.post("/api/v1/profile/client", json=perfil, headers=cliente).status_code, 422
        )
        publico_admin = {"email": "hd-admin-publico@test.com", "senha": SENHA, "role": "ADMINISTRADOR"}
        self.assertEqual(self.client.post("/api/v1/auth/register", json=publico_admin).status_code, 422)

    # --- 10: role informada no token não substitui a do banco ---

    def test_15_role_forjada_no_token_nao_concede_acesso(self):
        self.garantir_perfil("hd-forjado@test.com")
        cliente_id = self.usuario_id("hd-forjado@test.com")
        # Assinatura válida, porém role inflada no claim: o backend recarrega
        # a role do banco e nega.
        token_forjado = security.create_access_token(cliente_id, "ADMINISTRADOR")
        cabecalhos = {"Authorization": f"Bearer {token_forjado}"}
        resposta = self.client.get("/api/v1/admin/pricing-rules", headers=cabecalhos)
        self.assertEqual(resposta.status_code, 403)
        # sub inexistente com claim privilegiado também é rejeitado.
        fantasma = security.create_access_token(str(uuid_lib.uuid4()), "ADMINISTRADOR")
        resposta = self.client.get(
            "/api/v1/admin/pricing-rules", headers={"Authorization": f"Bearer {fantasma}"}
        )
        self.assertEqual(resposta.status_code, 401)
        # Assinatura de outra chave nunca passa.
        falso = jwt.encode({"sub": cliente_id, "role": "ADMINISTRADOR"}, "chave-errada", algorithm="HS256")
        resposta = self.client.get(
            "/api/v1/admin/pricing-rules", headers={"Authorization": f"Bearer {falso}"}
        )
        self.assertEqual(resposta.status_code, 401)

    # --- 11: valores financeiros seguem calculados exclusivamente no backend ---

    def test_16_valores_financeiros_continuam_calculados_no_backend(self):
        self.garantir_perfil("hd-fin-c@test.com")
        self.garantir_perfil("hd-fin-p@test.com", rota="provider")
        cliente = self.headers_de("hd-fin-c@test.com")
        prestador = self.headers_de("hd-fin-p@test.com")
        coleta_id = self.criar_coleta(cliente)
        self.levar_ate_carregada(cliente, prestador, coleta_id, "F1")
        # Injeção de valor/snapshot/status no corpo é rejeitada (extra="forbid").
        injecao = self.client.post(
            f"/api/v1/collections/{coleta_id}/finalizar",
            json={"snapshot_valor_cliente": 0.01, "status": "FINALIZADA"},
            headers=prestador,
        )
        self.assertEqual(injecao.status_code, 422)
        with sessionmaker(bind=self.engine)() as db:
            self.assertEqual(db.get(Collection, coleta_id).status, "CARREGADA")
            self.assertIsNone(db.get(Collection, coleta_id).snapshot_valor_cliente)
        # Fechamento legítimo: backend calcula com as price_rules vigentes.
        self.criar_regras(self.admin_headers())
        resposta = self.client.post(f"/api/v1/collections/{coleta_id}/finalizar", json={}, headers=prestador)
        self.assertEqual(resposta.status_code, 200, resposta.text)
        corpo = resposta.json()
        # 2 pneus registrados × regras (CLIENTE 4.00 / PRESTADOR 2.50).
        self.assertEqual(corpo["quantidade_coletada"], 2)
        self.assertEqual(corpo["snapshot_valor_cliente"], 8.0)
        self.assertEqual(corpo["snapshot_valor_prestador"], 5.0)

    # --- 12: idempotência continua funcionando ---

    def test_17_idempotencia_continua_funcionando(self):
        self.garantir_perfil("hd-idem@test.com")
        cliente = self.headers_de("hd-idem@test.com")
        chave = str(uuid_lib.uuid4())
        cabecalhos = {**cliente, "X-Idempotency-Key": chave}
        primeira = self.client.post("/api/v1/collections", json=self.payload_coleta(), headers=cabecalhos)
        self.assertEqual(primeira.status_code, 201, primeira.text)
        replay = self.client.post("/api/v1/collections", json=self.payload_coleta(), headers=cabecalhos)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json(), primeira.json())
        divergente = self.client.post(
            "/api/v1/collections",
            json=self.payload_coleta(itens=[{"marca": "M", "dimensao": "D", "quantidade_declarada": 11}]),
            headers=cabecalhos,
        )
        self.assertEqual(divergente.status_code, 409)

    # --- 13: nenhuma regressão nas regras de coleta / máquina de estados ---

    def test_18_fluxo_de_coleta_sem_regressao(self):
        self.garantir_perfil("hd-fluxo@test.com")
        cliente = self.headers_de("hd-fluxo@test.com")
        coleta_id = self.criar_coleta(cliente)
        listagem = self.client.get("/api/v1/collections", headers=cliente).json()
        self.assertIn(coleta_id, [c["id"] for c in listagem])
        self.assertEqual(listagem[0]["status"], "SOLICITADA")
        cancelamento = self.client.post(f"/api/v1/collections/{coleta_id}/cancelar", headers=cliente)
        self.assertEqual(cancelamento.status_code, 200)
        self.assertEqual(cancelamento.json()["status"], "CANCELADA")
        repetido = self.client.post(f"/api/v1/collections/{coleta_id}/cancelar", headers=cliente)
        self.assertEqual(repetido.status_code, 409)
        salto = self.client.post(
            f"/api/v1/collections/{coleta_id}/status",
            json={"novo_status": "EM_CONFERENCIA"},
            headers=cliente,
        )
        self.assertIn(salto.status_code, (403, 409))

    # --- 8: entradas excessivas/inválidas são rejeitadas ---

    def test_19_entradas_excessivas_e_invalidas_rejeitadas(self):
        self.garantir_perfil("hd-limites-c@test.com")
        self.registrar("hd-limites-p@test.com", role="PRESTADOR")
        cliente = self.headers_de("hd-limites-c@test.com")
        prestador = self.headers_de("hd-limites-p@test.com")

        excesso_itens = self.payload_coleta(
            itens=[
                {"marca": "M", "dimensao": "D", "quantidade_declarada": 1} for _ in range(201)
            ]
        )
        self.assertEqual(
            self.client.post("/api/v1/collections", json=excesso_itens, headers=cliente).status_code, 422
        )
        endereco_gigante = self.payload_coleta(endereco={"rua": "x" * 5000})
        self.assertEqual(
            self.client.post("/api/v1/collections", json=endereco_gigante, headers=cliente).status_code, 422
        )
        quantidade_absurda = self.payload_coleta(
            itens=[{"marca": "M", "dimensao": "D", "quantidade_declarada": 2_000_000}]
        )
        self.assertEqual(
            self.client.post("/api/v1/collections", json=quantidade_absurda, headers=cliente).status_code, 422
        )
        lote_excessivo = {"pneus": [self.pneu_payload(f"XL{i:05d}") for i in range(2001)]}
        self.assertEqual(
            self.client.post(
                f"/api/v1/collections/{uuid_lib.uuid4()}/conferencia/pneus",
                json=lote_excessivo,
                headers=prestador,
            ).status_code,
            422,
        )
        pneu_injetado = {
            **self.pneu_payload("XL00001"),
            "idade_calculada_anos": 0.0,
            "alerta_idade_obsoleto": False,
        }
        self.assertEqual(
            self.client.post(
                f"/api/v1/collections/{uuid_lib.uuid4()}/conferencia/pneus",
                json={"pneus": [pneu_injetado]},
                headers=prestador,
            ).status_code,
            422,
        )

    # --- 14: nenhum vazamento de informação sensível ---

    def test_20_sem_vazamento_de_informacao_sensivel(self):
        self.registrar("hd-vazamento@test.com")
        inexistente = self.client.post(
            "/api/v1/auth/login", json={"email": "ninguem-hard@test.com", "senha": "errada"}
        )
        senha_errada = self.client.post(
            "/api/v1/auth/login", json={"email": "hd-vazamento@test.com", "senha": "errada"}
        )
        self.assertEqual(inexistente.status_code, senha_errada.status_code)
        self.assertEqual(inexistente.json(), senha_errada.json())
        # Erro de banco não expõe URL/traceback.
        engine_quebrado = create_engine("sqlite:///./diretorio_inexistente_hd/banco.db")
        with mock.patch.object(db_session, "SessionLocal", sessionmaker(bind=engine_quebrado)):
            resposta = self.client.get("/health/db")
        engine_quebrado.dispose()
        self.assertEqual(resposta.status_code, 503)
        self.assertNotIn("DATABASE_URL", resposta.text)
        self.assertNotIn("Traceback", resposta.text)


if __name__ == "__main__":
    unittest.main()


