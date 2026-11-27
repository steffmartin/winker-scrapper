"""Exportação da página de relatório pela mesma mídia de impressão do WebView2."""
import os
import tempfile
from pathlib import Path

import webview


_CAPTURAR_RELATORIO = '''(() => {
    const copia = document.documentElement.cloneNode(true);
    copia.querySelectorAll('script').forEach(script => script.remove());
    let base = copia.querySelector('base');
    if (!base) { base = document.createElement('base'); copia.querySelector('head').prepend(base); }
    base.setAttribute('href', document.baseURI);
    return '<!DOCTYPE html>' + copia.outerHTML;
})()'''


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
    html = janela.evaluate_js(_CAPTURAR_RELATORIO)
    if not isinstance(html, str) or not html:
        raise RuntimeError('Não foi possível preparar o relatório para impressão.')
    # NavigateToString do WebView2 tem limite de tamanho; um arquivo temporário
    # também permite exportar relatórios com muitos lançamentos.
    with tempfile.TemporaryDirectory(prefix='winker-relatorio-') as pasta:
        arquivo = os.path.join(pasta, 'relatorio.html')
        with open(arquivo, 'w', encoding='utf-8') as destino:
            destino.write(html)
        auxiliar = webview.create_window('Impressão de relatório', url=Path(arquivo).as_uri(), hidden=True)
        try:
            if not auxiliar.events.loaded.wait(60):
                raise RuntimeError('Não foi possível carregar o relatório para impressão.')
            _gerar_pdf(auxiliar, caminho)
        finally:
            auxiliar.destroy()
    return {'status': 'success', 'path': caminho}
