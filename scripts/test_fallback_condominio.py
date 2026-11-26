import unittest
from unittest.mock import MagicMock
from extract_winker import capturar_sessao_api, extrair_condominio_api

class TestFallbackApi(unittest.TestCase):
    def setUp(self):
        self.context = MagicMock()
        self.portals = [{'id_portal': 22, 'url': 'https://app.winker.com.br/outro'}, {'id_portal': 11, 'url': 'https://app.winker.com.br/alvo', 'name': 'Alvo'}]
        self.found = {'id_condominio': '11', 'codigo_seguranca': 'abc123', 'nome': 'Alvo'}
        self.about = {'users': {'manager': {'name': 'Ana', 'title': 'Síndica'}, 'boardMembers': [{'name': 'Bia', 'groups': [{'name': 'Conselheiro'}]}], 'providers': [{'name': 'Admin', 'phone': '11999999999', 'activities': [{'activitie': 'Administradora'}]}]}}
        self.context.request.get.side_effect = [self.response(self.portals), self.response(self.about)]
        self.context.request.post.return_value = self.response([self.found])

    @staticmethod
    def response(data):
        r = MagicMock(ok=True)
        r.json.return_value = data
        return r

    def test_portal_da_sessao_e_gestao(self):
        result = extrair_condominio_api(self.context, 'token', '11')
        self.assertEqual(result, ('abc123', 'Alvo', [{'nome': 'Ana', 'cargo': 'Síndica'}, {'nome': 'Bia', 'cargo': 'Conselheiro'}], 'Admin', ['11999999999']))
        self.assertEqual(self.context.request.post.call_args.kwargs['data']['codigoSeguranca'], 'alvo')

    def test_id_divergente_nao_e_aceito(self):
        self.found['id_condominio'] = '22'
        with self.assertRaises(ValueError):
            extrair_condominio_api(self.context, 'token', '11')
        self.assertEqual(self.context.request.get.call_count, 1)

    def test_url_ausente_nao_faz_busca(self):
        self.portals[1]['url'] = None
        with self.assertRaises(ValueError):
            extrair_condominio_api(self.context, 'token', '11')
        self.context.request.post.assert_not_called()

    def test_resultado_vazio_ou_ambiguo_e_rejeitado(self):
        for result in ([], [self.found, self.found]):
            with self.subTest(result=result):
                context = MagicMock()
                context.request.get.return_value = self.response(self.portals)
                context.request.post.return_value = self.response(result)
                with self.assertRaises(ValueError):
                    extrair_condominio_api(context, 'token', '11')

    def test_about_indisponivel_preserva_identificacao(self):
        about = self.response({})
        about.ok = False
        self.context.request.get.side_effect = [self.response(self.portals), about]
        resultado = extrair_condominio_api(self.context, 'token', '11')
        self.assertEqual(resultado, ('abc123', 'Alvo', [], None, None))

    def test_captura_aguarda_home_e_le_token_no_html(self):
        page = MagicMock()
        page.evaluate.side_effect = [None, None]
        page.content.side_effect = ['var PORTAL_DATA = {id_portal: 11};', "const TOKEN_API = 'jwt';"]
        self.assertEqual(capturar_sessao_api(page), ('11', 'jwt'))
        page.wait_for_load_state.assert_called_once_with('networkidle')

    def test_rejeita_sessao_invalida_sem_consultar_api(self):
        for token, portal in [('token', None), ('token', 'nao-numerico'), ('', '11')]:
            with self.subTest(token=token, portal=portal), self.assertRaises(ValueError):
                extrair_condominio_api(self.context, token, portal)
        self.context.request.get.assert_not_called()

    def test_portais_com_resposta_invalida_ou_identidade_ambigua(self):
        for payload in ({}, [], [self.portals[1], self.portals[1]]):
            with self.subTest(payload=payload):
                context = MagicMock()
                context.request.get.return_value = self.response(payload)
                with self.assertRaises(ValueError):
                    extrair_condominio_api(context, 'token', '11')
                context.request.post.assert_not_called()

    def test_rejeita_url_insegura_e_falhas_na_busca(self):
        for url in ('http://app.winker.com.br/alvo', 'https://outro.test/alvo',
                    'https://app.winker.com.br/alvo/outro'):
            with self.subTest(url=url):
                context = MagicMock()
                context.request.get.return_value = self.response([{'id_portal': 11, 'url': url}])
                with self.assertRaises(ValueError):
                    extrair_condominio_api(context, 'token', '11')
                context.request.post.assert_not_called()
        for resultado in ({'id_condominio': '11'}, {'id_condominio': '11', 'codigo_seguranca': '  '}):
            with self.subTest(resultado=resultado):
                context = MagicMock()
                context.request.get.return_value = self.response(self.portals)
                context.request.post.return_value = self.response(resultado)
                with self.assertRaises(ValueError):
                    extrair_condominio_api(context, 'token', '11')
