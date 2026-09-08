import os
import re
import time
import pandas as pd
import streamlit as st
import gspread
import pdfplumber
from datetime import datetime
from playwright.sync_api import sync_playwright

# Configuração da página Streamlit
st.set_page_config(
    page_title="Gestor SITRAM - Ação Fiscal & NF-e",
    page_icon="📦",
    layout="wide"
)

# ----------------------------------------------------------------------
# 1. FUNÇÕES DO BANCO DE DADOS (GOOGLE SHEETS)
# ----------------------------------------------------------------------
@st.cache_resource
def conectar_google_sheets():
    """
    Conecta no Google Sheets usando o arquivo de credenciais 'credentials.json'.
    Certifique-se de que o arquivo 'credentials.json' está na pasta do projeto.
    """
    try:
        gc = gspread.service_account(filename="credentials.json")
        # Nome da sua planilha no Google Drive
        sh = gc.open("SITRAM_DATABASE")
        return sh
    except Exception as e:
        st.error(f"Erro ao conectar com Google Sheets: {e}")
        return None

def obter_ou_criar_aba(sh, nome_aba, cabecalho):
    try:
        aba = sh.worksheet(nome_aba)
    except Exception:
        aba = sh.add_worksheet(title=nome_aba, rows=1000, cols=10)
        aba.append_row(cabecalho)
    return aba

# ----------------------------------------------------------------------
# 2. FUNÇÃO DE EXTRAÇÃO DE DADOS DO PDF DA AÇÃO FISCAL
# ----------------------------------------------------------------------
def extrair_dados_pdf_af(caminho_pdf):
    dados = {
        "num_af": "N/A",
        "situacao_af": "N/A",
        "status_imposto": "N/A",
        "liberado": "NÃO"
    }
    
    with pdfplumber.open(caminho_pdf) as pdf:
        texto = ""
        for pagina in pdf.pages:
            texto += (pagina.extract_text() or "") + "\n"
        
        texto_upper = texto.upper()
        
        # Extrai Número da Ação Fiscal
        match_af = re.search(r"AÇÃO FISCAL DE TRÂNSITO\s*-\s*(\d+)", texto_upper)
        if match_af:
            dados["num_af"] = match_af.group(1)
            
        # Extrai Situação
        match_sit = re.search(r"SITUAÇÃO:\s*(.*)", texto_upper)
        if match_sit:
            dados["situacao_af"] = match_sit.group(1).split("\n")[0].strip()
            
        # Determina Status e Liberação
        if "PAGO" in texto_upper and "A PAGAR" not in texto_upper:
            dados["status_imposto"] = "PAGO"
            dados["liberado"] = "SIM"
        elif "A PAGAR" in texto_upper:
            dados["status_imposto"] = "A PAGAR"
            dados["liberado"] = "NÃO"
            
        if "LIBERADA: SIM" in texto_upper or "LIBERADA\nSIM" in texto_upper:
            dados["liberado"] = "SIM"

    return dados

# ----------------------------------------------------------------------
# 3. AUTOMAÇÃO NO SITRAM (PLAYWRIGHT)
# ----------------------------------------------------------------------
def consultar_acao_fiscal_sitram(chave_mdfe, awb_numero):
    """
    Acessa o SITRAM, preenche PRIMEIRO a Chave do MDF-e,
    aguarda a liberação dos campos, seleciona AWB e baixa o PDF.
    """
    awb_limpa = str(awb_numero).strip()
    if not awb_limpa.startswith("957") and len(awb_limpa) == 8:
        awb_limpa = f"957{awb_limpa}"

    download_dir = os.path.join(os.getcwd(), "downloads")
    os.makedirs(download_dir, exist_ok=True)

    resultado = {
        "chave_mdfe": chave_mdfe,
        "awb": awb_limpa,
        "num_af": "N/A",
        "status_imposto": "Erro / Não Encontrado",
        "liberado": "NÃO",
        "caminho_pdf": None
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        try:
            # 1. Acessa o SITRAM
            page.goto("https://portal-sitram.sefaz.ce.gov.br/sitram-internet/#/", timeout=30000)
            page.wait_for_load_state("domcontentloaded")

            # 2. Navega para Ação Fiscal
            page.get_by_text("Consultas", exact=True).click()
            time.sleep(0.5)
            page.get_by_role("link", name="Ação Fiscal").first.click()
            
            # 3. Garante opção PDF marcada
            page.get_by_label("PDF").check()

            # 4. PASSO CRUCIAL: Preenche PRIMEIRO a Chave do MDF-e
            campo_mdfe = page.get_by_placeholder("Insira aqui uma chave de acesso (MDF-e)").or_(page.locator("input").first)
            campo_mdfe.fill(chave_mdfe)
            campo_mdfe.dispatch_event("change")
            time.sleep(1) # Aguarda os campos secundários serem habilitados na tela

            # 5. Preenche os campos secundários de AWB caso existam
            if page.locator("mat-select, select").count() > 0:
                page.locator("mat-select, select").first.click()
                page.get_by_text("AWB", exact=True).click()
                
                campo_awb = page.get_by_placeholder("Insira aqui").or_(page.locator("input").nth(1))
                campo_awb.fill(awb_limpa)

            # 6. Pesquisa e faz o download do PDF
            with page.expect_download(timeout=25000) as download_info:
                page.get_by_role("button", name="Pesquisar").click()

            download = download_info.value
            pdf_path = os.path.join(download_dir, f"AF_{awb_limpa}.pdf")
            download.save_as(pdf_path)

            # 7. Lê os dados do PDF
            dados_pdf = extrair_dados_pdf_af(pdf_path)
            resultado.update(dados_pdf)
            resultado["caminho_pdf"] = pdf_path

        except Exception as e:
            st.warning(f"Aviso durante consulta MDF-e {chave_mdfe}: {e}")

        browser.close()

    return resultado

# ----------------------------------------------------------------------
# 4. INTERFACE GRÁFICA (STREAMLIT)
# ----------------------------------------------------------------------
st.title("📦 Gestor SITRAM - Banco de Dados & Consultas")

sh = conectar_google_sheets()

if sh:
    aba_af = obter_ou_criar_aba(
        sh, "AÇÕES_FISCAIS", 
        ["CHAVE_MDFE", "AWB", "NUM_AF", "STATUS_IMPOSTO", "LIBERADO", "DATA_ATUALIZACAO"]
    )
    aba_nf = obter_ou_criar_aba(
        sh, "NOTAS_FISCAIS", 
        ["CHAVE_NFE", "AWB", "STATUS_IMPOSTO", "LIBERADO", "DATA_ATUALIZACAO"]
    )

    tab1, tab2, tab3 = st.tabs(["🔍 Consulta Ação Fiscal (MDF-e + AWB)", "📄 Consulta Nota Fiscal (NF-e + AWB)", "📊 Banco de Dados"])

    # ------------------------------------------------------------------
    # TAB 1: CONSULTA POR AÇÃO FISCAL
    # ------------------------------------------------------------------
    with tab1:
        st.subheader("Entrada por Ação Fiscal")
        st.caption("A Chave do MDF-e é o parâmetro principal para desbloquear os campos no SITRAM.")

        with st.form("form_af"):
            col1, col2 = st.columns(2)
            with col1:
                chave_mdfe_in = st.text_input("Chave de Acesso (MDF-e) *", help="44 dígitos da Chave do MDF-e")
            with col2:
                awb_in = st.text_input("Número AWB *", help="Exemplo: 36568956")

            btn_processar_af = st.form_submit_button("Consultar e Salvar no Banco")

        if btn_processar_af:
            if not chave_mdfe_in or not awb_in:
                st.error("Preencha a Chave do MDF-e e a AWB!")
            else:
                # REGRAS DO BANCO DE DADOS: Checa se já está liberado
                registros = aba_af.get_all_records()
                existente = next((r for r in registros if str(r.get("CHAVE_MDFE")) == chave_mdfe_in.strip()), None)

                if existente and str(existente.get("LIBERADO")).upper() == "SIM":
                    st.success(f"✅ MDF-e/AWB já cadastrada e **LIBERADA** no Banco de Dados! (Ação Fiscal nº {existente.get('NUM_AF')})")
                    st.json(existente)
                else:
                    st.info("🔄 Registro pendente ou novo. Iniciando consulta no SITRAM...")
                    
                    with st.spinner("Acessando SITRAM e baixando Ação Fiscal..."):
                        res = consultar_acao_fiscal_sitram(chave_mdfe_in.strip(), awb_in.strip())

                    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # Atualiza ou Insere na Planilha
                    if existente:
                        # Encontra a linha no gspread
                        cell = aba_af.find(chave_mdfe_in.strip())
                        idx_linha = cell.row
                        aba_af.update_cell(idx_linha, 3, res["num_af"])
                        aba_af.update_cell(idx_linha, 4, res["status_imposto"])
                        aba_af.update_cell(idx_linha, 5, res["liberado"])
                        aba_af.update_cell(idx_linha, 6, agora)
                    else:
                        aba_af.append_row([
                            res["chave_mdfe"], res["awb"], res["num_af"],
                            res["status_imposto"], res["liberado"], agora
                        ])

                    st.success(f"Consulta finalizada! Status: **{res['status_imposto']}** | Liberado: **{res['liberado']}**")

    # ------------------------------------------------------------------
    # TAB 3: VISUALIZAR BANCO DE DADOS COMPLETO
    # ------------------------------------------------------------------
    with tab3:
        st.subheader("Registros no Banco de Dados (Google Sheets)")
        dados_af_df = pd.DataFrame(aba_af.get_all_records())
        if not dados_af_df.empty:
            st.dataframe(dados_af_df, use_container_width=True)
        else:
            st.info("Nenhum registro de Ação Fiscal no banco de dados.")
