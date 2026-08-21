# backend/tests/test_dot_repetition.py
import unittest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.db.models import (
    Base, User, Profile, Client, Provider, Collection, Tire
)

class TestDotRepetition(unittest.TestCase):
    def setUp(self):
        # Cria banco em memória SQLite com suporte a Foreign Keys
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

        # Cria dados base: User, Profile, Client, Collection
        user = User(email="cliente@test.com", password_hash="$argon2id$mock", role="CLIENTE")
        self.session.add(user)
        self.session.flush()

        profile = Profile(user_id=user.id, nome_razao_social="Cliente Teste LTDA", cpf_cnpj="12345678000199", telefone="11999999999")
        self.session.add(profile)
        self.session.flush()

        client = Client(profile_id=profile.id)
        self.session.add(client)
        self.session.flush()

        self.collection = Collection(
            codigo_identificador="COL-2026-00001",
            client_id=client.id,
            status="EM_CONFERENCIA",
            endereco_origem_json={"rua": "Rua Teste", "numero": "100", "cidade": "São Paulo"},
            data_agendada=datetime.now(timezone.utc)
        )
        self.session.add(self.collection)
        self.session.commit()

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(self.engine)

    def test_dot_repetition_500_tires(self):
        """
        REGRA ESPECIAL DE TESTE DO DOT (OBRIGATÓRIO):
        Valida que 500 pneus com o exato mesmo DOT ('2526') podem ser inseridos
        com sucesso e que cada pneu possui seu UUIDv4 próprio e único.
        """
        dot_lote = "2526" # Semana 25 de 2026
        qtd_pneus = 500
        uuids_criados = set()

        pneus_batch = []
        for i in range(qtd_pneus):
            pneu = Tire(
                collection_id=self.collection.id,
                numero_fogo=f"FOGO-{i+1:04d}",
                dot=dot_lote,
                semana_fabricacao=25,
                ano_fabricacao=26,
                idade_calculada_anos=0.5,
                alerta_idade_obsoleto=False,
                marca="Pirelli",
                medida="295/80R22.5"
            )
            pneus_batch.append(pneu)

        self.session.add_all(pneus_batch)
        self.session.commit()

        # Consulta todos os pneus inseridos na coleta
        pneus_db = self.session.query(Tire).filter(Tire.collection_id == self.collection.id).all()

        # Validações estritas
        self.assertEqual(len(pneus_db), qtd_pneus, "Todos os 500 pneus devem ser persistidos.")

        for pneu in pneus_db:
            self.assertEqual(pneu.dot, dot_lote, "O DOT de todos os pneus deve ser 2526.")
            self.assertIsNotNone(pneu.id, "Cada pneu deve possuir uma PK UUID válida.")
            uuids_criados.add(pneu.id)

        self.assertEqual(len(uuids_criados), qtd_pneus, "Cada um dos 500 pneus DEVE possuir um UUIDv4 único diferente.")

if __name__ == "__main__":
    unittest.main()
