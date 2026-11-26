"""Testes de revisão com banco descartável, sem acesso ao banco da aplicação."""
import os
import tempfile
import unittest

import models
from run_dashboard import Api


class RevisaoBancoIsoladoTest(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.banco = os.path.join(self.pasta.name, 'revisao.db')
        models.init_models(self.banco)
        models.Condominio.create(id='teste', nome='Condomínio de teste')
        self.mes = models.Meses.create(condominio_id='teste', competencia='2025-01', exibicao='JAN/2025',
                                       consistente=0, revisado_usuario=0)
        self.api = Api(db_path=self.banco)

    def tearDown(self):
        if not models.db.is_closed():
            models.db.close()
        self.pasta.cleanup()

    def test_mes_pendente_deixa_lista_apos_revisao(self):
        antes = self.api.get_registros_nao_revisados('meses')
        self.assertEqual(antes['status'], 'success')
        self.assertEqual([r['id'] for r in antes['data']], [self.mes.id])
        atualizacao = self.api.update_registro_revisado('meses', {'id': self.mes.id, 'revisado_usuario': 1})
        self.assertEqual(atualizacao['status'], 'success')
        self.assertEqual(self.api.get_registros_nao_revisados('meses')['data'], [])
        revisados = self.api.get_registros_nao_revisados('meses', True)
        self.assertEqual([r['id'] for r in revisados['data']], [self.mes.id])

    def test_inicializacao_sem_banco_ou_sem_condominio_retorna_erro(self):
        ausente = Api(db_path=os.path.join(self.pasta.name, 'ausente.db'))
        self.assertEqual(ausente.init_error, 'Banco de dados não encontrado.')
        outro = os.path.join(self.pasta.name, 'vazio.db')
        models.db.close()
        models.init_models(outro)
        vazio = Api(db_path=outro)
        self.assertEqual(vazio.init_error, 'Nenhum condomínio definido ou encontrado no banco.')

    def test_inicializacao_usa_preferencia_ou_primeiro_condominio(self):
        self.assertEqual(self.api.condo_id, 'teste')
        models.Condominio.create(id='outro', nome='Outro')
        preferencia = models.PreferenciasUsuario.select().first()
        preferencia.condominio_id = 'outro'
        preferencia.save()
        outra_api = Api(db_path=self.banco)
        self.assertEqual(outra_api.condo_id, 'outro')


if __name__ == '__main__':
    unittest.main()
