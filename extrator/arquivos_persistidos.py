"""Atualização transacional de arquivos extraídos do mês."""

import os
import shutil
import tempfile


def _atualizar_arquivos_mes(project_root, mes_dir, anexos_preservados, anexos_para_mover):
    # Somente anexos elegíveis são copiados para o diretório temporário do sistema.
    with tempfile.TemporaryDirectory(prefix="winker_revisao_") as temp_preservados:
        staged = []
        for caminho in dict.fromkeys(anexos_preservados):
            origem = os.path.abspath(os.path.join(project_root, caminho))
            copia = os.path.join(temp_preservados, str(len(staged)))
            shutil.copy2(origem, copia)
            staged.append((copia, origem))
        for mov in anexos_para_mover:
            if not os.path.isfile(mov['temp_path']):
                raise FileNotFoundError(mov['temp_path'])
        try:
            if os.path.exists(mes_dir):
                shutil.rmtree(mes_dir)
            for copia, destino in staged:
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                shutil.copy2(copia, destino)
            for mov in anexos_para_mover:
                os.makedirs(os.path.dirname(mov['caminho_final']), exist_ok=True)
                shutil.copy2(mov['temp_path'], mov['caminho_final'])
        except Exception:
            # Preserva os arquivos de revisão mesmo se houver erro ao recriar a pasta.
            for copia, destino in staged:
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                shutil.copy2(copia, destino)
            raise
