import os
import pandas as pd

def carregar_chaves_acesso(arquivo_upload_ou_caminho):
    """
    Lê uma coluna 'chave' de um arquivo Excel (.xlsx) ou CSV.
    """
    if str(arquivo_upload_ou_caminho).endswith('.csv'):
        df = pd.read_csv(arquivo_upload_ou_caminho, dtype=str)
    else:
        df = pd.read_excel(arquivo_upload_ou_caminho, dtype=str)
    
    # Limpa nomes de colunas (remove espaços extras)
    df.columns = df.columns.astype(str).str.strip().str.lower()
    
    coluna_chave = [col for col in df.columns if 'chave' in col]
    if not coluna_chave:
        raise ValueError("Não foi encontrada nenhuma coluna contendo 'chave' no arquivo.")
    
    chaves = df[coluna_chave[0]].dropna().astype(str).str.strip().tolist()
    return chaves

def gerar_relatorio_excel(resultados, caminho_saida):
    """
    Gera um arquivo Excel formatado com os resultados obtidos do SITRAM.
    """
    df_resultado = pd.DataFrame(resultados)
    
    with pd.ExcelWriter(caminho_saida, engine='openpyxl') as writer:
        df_resultado.to_excel(writer, index=False, sheet_name='Resultados_SITRAM')
    
    return caminho_saida
