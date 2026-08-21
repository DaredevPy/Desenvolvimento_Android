# backend/tests/test_db_schema.py
import unittest
from datetime import datetime, date, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.db.models import (
    Base, User, Profile, Client, Provider, Collection,
    CollectionItemDeclared, CollectionItemChecked, Tire,
    FinancialTransaction, PriceRule, ProviderReputationEvent,
    ProviderRestriction, AuditLog
)

class TestDbSchema(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(self.engine)

    def test_relacionamentos_cliente_prestador_coleta(self):
        """Valida que relacionamentos entre cliente, prestador e coleta funcionam corretamente."""
        # 1. Cria usuário e perfil de cliente
        user_c = User(email="cliente_rel@test.com", password_hash="hash", role="CLIENTE")
        self.session.add(user_c)
        self.session.flush()

        prof_c = Profile(user_id=user_c.id, nome_razao_social="Cliente SA", cpf_cnpj="11111111000111", telefone="11911111111")
        self.session.add(prof_c)
        self.session.flush()

        client = Client(profile_id=prof_c.id)
        self.session.add(client)

        # 2. Cria usuário e perfil de prestador
        user_p = User(email="prestador_rel@test.com", password_hash="hash", role="PRESTADOR")
        self.session.add(user_p)
        self.session.flush()

        prof_p = Profile(user_id=user_p.id, nome_razao_social="Prestador Silva", cpf_cnpj="22222222000122", telefone="11922222222", chave_pix="pix@prestador.com")
        self.session.add(prof_p)
        self.session.flush()

        provider = Provider(profile_id=prof_p.id, reputacao_score=4.90)
        self.session.add(provider)
        self.session.commit()

        # 3. Cria Coleta
        col = Collection(
            codigo_identificador="COL-REL-001",
            client_id=client.id,
            provider_id=provider.id,
            status="ACEITA",
            endereco_origem_json={"cidade": "São Paulo"},
            data_agendada=datetime.now(timezone.utc)
        )
        self.session.add(col)
        self.session.commit()

        # Validações de ORM
        col_db = self.session.query(Collection).filter_by(id=col.id).first()
        self.assertIsNotNone(col_db)
        self.assertEqual(col_db.client.profile.nome_razao_social, "Cliente SA")
        self.assertEqual(col_db.provider.profile.nome_razao_social, "Prestador Silva")

    def test_financeiro_desacoplado_e_snapshot(self):
        """Valida que valores financeiros do cliente e prestador são desacoplados e possuem snapshot imutável."""
        user_admin = User(email="admin@test.com", password_hash="hash", role="ADMINISTRADOR")
        user_c = User(email="cli_fin@test.com", password_hash="hash", role="CLIENTE")
        user_p = User(email="prm_fin@test.com", password_hash="hash", role="PRESTADOR")
        self.session.add_all([user_admin, user_c, user_p])
        self.session.flush()

        prof_c = Profile(user_id=user_c.id, nome_razao_social="Cli", cpf_cnpj="33333333000133", telefone="11933333333")
        prof_p = Profile(user_id=user_p.id, nome_razao_social="Pre", cpf_cnpj="44444444000144", telefone="11944444444")
        self.session.add_all([prof_c, prof_p])
        self.session.flush()

        client = Client(profile_id=prof_c.id)
        provider = Provider(profile_id=prof_p.id)
        self.session.add_all([client, provider])
        self.session.flush()

        # Regra de Preço Vigente: Cliente R$ 4,00 / Prestador R$ 2,50
        rule_c = PriceRule(perfil_alvo="CLIENTE", faixa_inicio_quantidade=1, faixa_fim_quantidade=1000, valor_unitario=4.00, vigencia_inicio=date.today(), criado_por_admin_id=user_admin.id)
        rule_p = PriceRule(perfil_alvo="PRESTADOR", faixa_inicio_quantidade=1, faixa_fim_quantidade=1000, valor_unitario=2.50, vigencia_inicio=date.today(), criado_por_admin_id=user_admin.id)
        self.session.add_all([rule_c, rule_p])
        self.session.flush()

        # Coleta de 247 pneus finalizada
        qtd_pneus = 247
        val_cliente_calc = qtd_pneus * rule_c.valor_unitario # 988.00
        val_prestador_calc = qtd_pneus * rule_p.valor_unitario # 617.50

        col = Collection(
            codigo_identificador="COL-FIN-001",
            client_id=client.id,
            provider_id=provider.id,
            status="FINALIZADA",
            endereco_origem_json={"cidade": "Campinas"},
            data_agendada=datetime.now(timezone.utc),
            snapshot_valor_cliente=val_cliente_calc,
            snapshot_valor_prestador=val_prestador_calc
        )
        self.session.add(col)
        self.session.flush()

        # Transações financeiras separadas
        trans_c = FinancialTransaction(collection_id=col.id, tipo_entidade="CLIENTE", perfil_id=prof_c.id, valor_total=val_cliente_calc, data_vencimento=date.today())
        trans_p = FinancialTransaction(collection_id=col.id, tipo_entidade="PRESTADOR", perfil_id=prof_p.id, valor_total=val_prestador_calc, data_vencimento=date.today())
        self.session.add_all([trans_c, trans_p])
        self.session.commit()

        # Altera a regra no dia seguinte para R$ 3,00/prestador
        rule_p.valor_unitario = 3.00
        self.session.commit()

        # Valida que o snapshot da coleta antiga CONTINUA R$ 617.50 (247 x R$ 2.50) e R$ 988.00 (247 x R$ 4.00)
        col_db = self.session.query(Collection).filter_by(id=col.id).first()
        self.assertEqual(float(col_db.snapshot_valor_prestador), 617.50)
        self.assertEqual(float(col_db.snapshot_valor_cliente), 988.00)

    def test_audit_logs_e_restricoes(self):
        """Valida inserção de log de auditoria e restrição de prestador."""
        user_admin = User(email="admin_aud@test.com", password_hash="hash", role="ADMINISTRADOR")
        user_p = User(email="prm_aud@test.com", password_hash="hash", role="PRESTADOR")
        self.session.add_all([user_admin, user_p])
        self.session.flush()

        prof_p = Profile(user_id=user_p.id, nome_razao_social="Pre Aud", cpf_cnpj="55555555000155", telefone="11955555555")
        self.session.add(prof_p)
        self.session.flush()

        provider = Provider(profile_id=prof_p.id)
        self.session.add(provider)
        self.session.flush()

        # Registra Restrição
        rest = ProviderRestriction(
            provider_id=provider.id,
            admin_responsavel_id=user_admin.id,
            motivo="Divergência injustificada de 10 pneus na coleta COL-09",
            evidencias_json={"fotos": ["http://foto1.jpg"]}
        )
        self.session.add(rest)

        # Registra Audit Log
        audit = AuditLog(
            user_id=user_admin.id,
            acao="RESTRICTION_CREATE",
            entidade_afetada="provider_restrictions",
            entidade_id=rest.id,
            valor_novo_json={"status": "ATIVA", "motivo": rest.motivo},
            ip_origem="192.168.1.100"
        )
        self.session.add(audit)
        self.session.commit()

        audit_db = self.session.query(AuditLog).filter_by(id=audit.id).first()
        self.assertIsNotNone(audit_db)
        self.assertEqual(audit_db.acao, "RESTRICTION_CREATE")

if __name__ == "__main__":
    unittest.main()
