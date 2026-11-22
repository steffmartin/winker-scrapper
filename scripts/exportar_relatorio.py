"""Exportação da página de relatório pela mesma mídia de impressão do WebView2."""
import os

import webview


def _gerar_pdf(janela, caminho):
    from System import Func, Object
    from Microsoft.Web.WebView2.Core import CoreWebView2PrintOrientation

    controle = janela.native.webview
    def iniciar():
        core = getattr(controle, 'CoreWebView2', None)
        if core is None:
            raise RuntimeError('A exportação em PDF requer o mecanismo WebView2.')
        configuracao = core.Environment.CreatePrintSettings()
        configuracao.Orientation = CoreWebView2PrintOrientation.Landscape
        return core.PrintToPdfAsync(caminho, configuracao)
    # A API do WebView2 deve ser iniciada na thread da interface. A espera fica
    # na thread da chamada pywebview, permitindo a conclusão assíncrona.
    tarefa = controle.Invoke(Func[Object](iniciar))
    if not tarefa.GetAwaiter().GetResult():
        raise RuntimeError('Não foi possível gerar o PDF.')


def salvar_pdf(janela, nome):
    if janela is None:
        raise RuntimeError('A janela do aplicativo não está disponível.')
    nome = os.path.basename(str(nome or 'Relatório').replace('\\', '/')).strip() or 'Relatório'
    if not nome.lower().endswith('.pdf'):
        nome += '.pdf'
    escolha = janela.create_file_dialog(webview.SAVE_DIALOG, save_filename=nome, file_types=('PDF (*.pdf)',))
    if not escolha:
        return {'status': 'cancelled'}
    caminho = escolha if isinstance(escolha, str) else escolha[0]
    if not caminho.lower().endswith('.pdf'):
        caminho += '.pdf'
    _gerar_pdf(janela, caminho)
    return {'status': 'success', 'path': caminho}
