"""Contratos de download usados pelo fluxo de extração."""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from extract_winker import (close_last_modal, download_anexos, download_file_from_button, download_http_file,
                            extract_list_from_modal, set_ion_datetime, wait_for_list_close, wait_for_new_list_and_items)


class DownloadHttpTest(unittest.TestCase):
    def test_anexos_preservam_total_encontrado_mesmo_quando_um_download_falha(self):
        localizador, contexto = MagicMock(), MagicMock()
        botoes = localizador.locator.return_value
        botoes.count.return_value = 2
        primeiro, segundo = MagicMock(), MagicMock()
        primeiro.inner_text.return_value = 'Arquivo (nota.pdf)'
        segundo.inner_text.return_value = 'Arquivo (recibo.pdf)'
        botoes.nth.side_effect = [primeiro, segundo]
        with tempfile.TemporaryDirectory() as pasta, patch('extract_winker.project_root', pasta), \
             patch('extract_winker.download_file_from_button', side_effect=[('/temporario/nota.pdf', 'nota.pdf'), RuntimeError('falha')]):
            arquivos, encontrados = download_anexos(localizador, contexto)
        self.assertEqual(encontrados, 2)
        self.assertEqual(arquivos, [{'temp_path': '/temporario/nota.pdf', 'nome_original': 'nota.pdf'}])

    def test_detecta_extensao_higieniza_nome_e_salva_conteudo(self):
        casos = [
            ("https://site/arquivo.PDF?token=1", "application/octet-stream", b"dados", "arquivo.pdf"),
            ("https://site/arquivo", "image/jpeg", b"imagem", "arquivo.jpg"),
            ("https://site/arquivo", "image/png", b"imagem", "arquivo.png"),
            ("https://site/arquivo", "image/gif", b"imagem", "arquivo.gif"),
            ("https://site/arquivo", "application/octet-stream", b"%PDF-1.4", "arquivo.pdf"),
            ("https://site/arquivo", "application/octet-stream", b"outros", "arquivo.pdf"),
        ]
        for url, tipo, corpo, esperado in casos:
            with self.subTest(url=url, tipo=tipo), tempfile.TemporaryDirectory() as pasta:
                resposta = MagicMock(status=200, headers={"content-type": tipo})
                resposta.body.return_value = corpo
                contexto = MagicMock()
                contexto.request.get.return_value = resposta
                caminho, nome = download_http_file(contexto, url, pasta, filename_prefix="tmp_")
                self.assertEqual(nome, esperado)
                self.assertEqual(os.path.basename(caminho), "tmp_" + esperado)
                with open(caminho, "rb") as arquivo:
                    self.assertEqual(arquivo.read(), corpo)
                contexto.request.get.assert_called_once_with(url)

    def test_nome_informado_e_limpo_e_erro_http_nao_grava_arquivo(self):
        contexto = MagicMock()
        resposta = contexto.request.get.return_value
        resposta.status = 200
        resposta.headers = {"content-type": "image/png"}
        resposta.body.return_value = b"imagem"
        with tempfile.TemporaryDirectory() as pasta:
            _, nome = download_http_file(contexto, "https://site/download", pasta, default_filename='nota:01?.png')
            self.assertEqual(nome, 'nota01.png')
            resposta.status = 403
            with self.assertRaisesRegex(Exception, 'HTTP 403'):
                download_http_file(contexto, "https://site/download", pasta)
            self.assertEqual(os.listdir(pasta), ['nota01.png'])

    def test_download_direto_remove_os_listeners(self):
        pagina = MagicMock()
        botao = MagicMock(page=pagina)
        eventos = {}
        pagina.on.side_effect = lambda nome, callback: eventos.update({nome: callback})
        download = MagicMock(suggested_filename="original.pdf")
        botao.click.side_effect = lambda: eventos['download'](download)
        with tempfile.TemporaryDirectory() as pasta:
            caminho, nome = download_file_from_button(MagicMock(), botao, pasta, 'tmp_', 'conta.pdf')
            self.assertEqual((caminho, nome), (os.path.join(pasta, 'tmp_conta.pdf'), 'conta.pdf'))
            download.save_as.assert_called_once_with(caminho)
        self.assertEqual(pagina.remove_listener.call_count, 2)
        pagina.remove_listener.assert_any_call('download', eventos['download'])
        pagina.remove_listener.assert_any_call('popup', eventos['popup'])

    def test_falha_ao_clicar_tambem_remove_listeners(self):
        pagina = MagicMock()
        botao = MagicMock(page=pagina)
        botao.click.side_effect = RuntimeError('falhou')
        with tempfile.TemporaryDirectory() as pasta:
            with self.assertRaisesRegex(RuntimeError, 'falhou'):
                download_file_from_button(MagicMock(), botao, pasta)
        self.assertEqual(pagina.remove_listener.call_count, 2)

    def test_sem_evento_de_download_expira_e_remove_listeners(self):
        pagina = MagicMock()
        botao = MagicMock(page=pagina)
        with tempfile.TemporaryDirectory() as pasta, patch('extract_winker.time.time', side_effect=[0, 16]):
            with self.assertRaisesRegex(Exception, 'Não foi possível obter'):
                download_file_from_button(MagicMock(), botao, pasta)
        self.assertEqual(pagina.remove_listener.call_count, 2)

    def test_confirma_dialogo_antes_de_salvar_download(self):
        pagina = MagicMock()
        botao = MagicMock(page=pagina)
        eventos = {}
        pagina.on.side_effect = lambda nome, callback: eventos.update({nome: callback})
        download = MagicMock(suggested_filename='arquivo.pdf')
        confirmacao = MagicMock()
        confirmacao.is_visible.return_value = True
        confirmacao.click.side_effect = lambda: eventos['download'](download)
        with tempfile.TemporaryDirectory() as pasta:
            caminho, nome = download_file_from_button(MagicMock(), botao, pasta, confirm_locator=confirmacao)
            self.assertEqual((caminho, nome), (os.path.join(pasta, 'arquivo.pdf'), 'arquivo.pdf'))
        confirmacao.click.assert_called_once_with()

    def test_popup_viewer_extrai_url_do_documento_e_fecha_janela(self):
        pagina = MagicMock()
        botao = MagicMock(page=pagina)
        eventos = {}
        pagina.on.side_effect = lambda nome, callback: eventos.update({nome: callback})
        popup = MagicMock(url='https://site/viewer.html?file=https%3A%2F%2Fsite%2Fnota.pdf')
        botao.click.side_effect = lambda: eventos['popup'](popup)
        with tempfile.TemporaryDirectory() as pasta, patch('extract_winker.download_http_file', return_value=('arquivo', 'nota.pdf')) as baixar:
            self.assertEqual(download_file_from_button(MagicMock(), botao, pasta), ('arquivo', 'nota.pdf'))
        self.assertEqual(baixar.call_args.args[1], 'https://site/nota.pdf')
        popup.close.assert_called_once_with()
        self.assertEqual(pagina.remove_listener.call_count, 2)


class NavegacaoModalTest(unittest.TestCase):
    def test_seletor_navega_mes_e_ano_e_confirma(self):
        iframe = MagicMock()
        elemento = MagicMock()
        elementos = MagicMock()
        elementos.all.return_value = [elemento]
        mes, ano, picker, alerta = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        mes.is_visible.return_value = ano.is_visible.return_value = True
        mes.locator.return_value.is_visible.return_value = ano.locator.return_value.is_visible.return_value = True
        mes.locator.return_value.inner_text.return_value = '01'
        ano.locator.return_value.inner_text.return_value = '2025'
        alerta.is_visible.return_value = True
        seletores = {'ion-datetime': elementos, 'ion-picker-cmp': picker,
                     'ion-picker-cmp .picker-opts-right': mes, 'ion-picker-cmp .picker-opts-left': ano,
                     "button.alert-button:has-text('Confirmar')": alerta}
        iframe.locator.side_effect = lambda seletor: seletores[seletor]
        with patch('extract_winker.time.sleep'):
            self.assertTrue(set_ion_datetime(iframe, 0, '03', '2024'))
        self.assertEqual([c.kwargs['name'] for c in mes.get_by_role.call_args_list], ['02', '03'])
        self.assertEqual([c.kwargs['name'] for c in ano.get_by_role.call_args_list], ['2024'])
        iframe.get_by_role.assert_called_with('button', name='Confirmar')
        alerta.click.assert_called_once_with()
        self.assertFalse(set_ion_datetime(iframe, 2, '03', '2024'))

    def test_lista_extrai_nomes_valores_e_anexos(self):
        iframe = MagicMock()
        lista = iframe.locator.return_value.last
        lista.count.return_value = 1
        itens = lista.locator.return_value
        itens.count.return_value = 2
        primeiro, segundo = MagicMock(), MagicMock()
        itens.nth.side_effect = [primeiro, segundo]
        label = primeiro.locator.return_value
        label.count.return_value = 1
        titulo = MagicMock()
        titulo.count.return_value = 1
        titulo.first.inner_text.return_value = 'Taxa ordinária'
        detalhe = MagicMock()
        detalhe.count.return_value = 1
        detalhe.first.inner_text.return_value = 'Apto 101'
        label.locator.side_effect = lambda seletor: {'h2': titulo, 'p': detalhe}[seletor]
        valor = MagicMock()
        valor.count.return_value = 1
        valor.inner_text.return_value = 'R$   100,00'
        primeiro.locator.side_effect = lambda seletor: label if seletor == 'ion-label' else MagicMock(first=valor)
        segundo.locator.return_value.count.return_value = 0
        contexto = MagicMock()
        with patch('extract_winker.download_anexos', return_value=([{'nome_original': 'nota.pdf'}], 1)) as download:
            resultado = extract_list_from_modal(iframe, contexto)
        self.assertEqual(resultado, [{'nome': 'Taxa ordinária (Apto 101)', 'valor': 'R$ 100,00', 'index': 0,
                                    'anexos': [{'nome_original': 'nota.pdf'}], 'anexos_count': 1}])
        download.assert_called_once_with(primeiro, contexto)

    def test_abertura_fechamento_e_timeout_de_lista(self):
        iframe = MagicMock()
        listas = iframe.locator.return_value
        listas.count.return_value = 2
        listas.last.locator.return_value.count.return_value = 1
        self.assertTrue(wait_for_new_list_and_items(iframe, 1))
        listas.last.locator.return_value.count.return_value = 0
        self.assertTrue(wait_for_new_list_and_items(iframe, 1, expected_non_zero=False))
        self.assertFalse(wait_for_new_list_and_items(iframe, 1, timeout_ms=0))
        self.assertTrue(wait_for_list_close(iframe, 3))
        self.assertFalse(wait_for_list_close(iframe, 2, timeout_ms=0))
        with patch('extract_winker.wait_for_list_close') as aguardar:
            close_last_modal(iframe)
        iframe.get_by_role.return_value.last.click.assert_called_once_with()
        aguardar.assert_called_once_with(iframe, 2)
