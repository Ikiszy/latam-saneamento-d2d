import os
import re
import time
from typing import Optional
from datetime import datetime
import pdfplumber
import gspread
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.sync_api import sync_playwright

app = FastAPI(title="Motor de Scraping SITRAM - Backend")

# ----------------------------------------------------------------------
# MODELO DE DADOS DE ENTRADA (PAYLOAD DO GOOGLE APPS SCRIPT)
# ----------------------------------------------------------------------
class RequisicaoAF(BaseModel):
    chave_mdfe: str
    awb: str

# ----------------------------------------------------------------------
# FUNÇÕES DE APOIO (BANCO DE DADOS E LEITURA DE PDF)
# ----------------------------------------------------------------------
def conectar_google_sheets():
    try:
        gc = gspread.service_account(filename="credentials.json")
        return gc.open("SITRAM_DATABASE")
    except Exception as e:
        print(f"Erro na conexão com Google Sheets: {e}")
        return None

def extrair_dados_pdf_af(caminho_pdf):
    dados = {
        "num_af": "N/A",
        "situacao_af": "N/A",
        "status_imposto": "N/A",
        "debito_ct": "N/A",
        "liberado": "NÃO"
    }
    
    with pdfplumber.open(caminho_pdf) as pdf:
        texto = ""
        for pagina in pdf.pages:
            texto += (pagina.extract_text() or "") + "\n"
        
        texto_upper = texto.upper()
        
        # 1. Extração do Número da Ação Fiscal
        match_af = re.search(r"AÇÃO FISCAL DE TRÂNSITO\s*-\s*(\d+)", texto_upper)
        if match_af:
            dados["num_af"] = match_af.group(1)
            
        # 2. Extração da Situação Geral da AF
        match_sit = re.search(r"SITUAÇÃO:\s*(.*)", texto_upper)
        if match_sit:
            dados["situacao_af"] = match_sit.group(1).split("\n")[0].strip()
            
        # 3. Identificação de Débito CT na tabela
        if re.search(r"DÉBITO CT\s+SIM", texto_upper) or re.search(r"\bSIM\b.*\b(SEM COBRANÇA|PAGA)\b", texto_upper):
            dados["debito_ct"] = "SIM"
        elif re.search(r"DÉBITO CT\s+NÃO", texto_upper) or "NÃO" in texto_upper:
            dados["debito_ct"] = "NÃO"

        # 4. Captura do Status do Imposto
        if "PAGA OU PARCELADA" in texto_upper or "PAGA" in texto_upper:
            dados["status_imposto"] = "PAGA"
        elif "SEM COBRANÇA" in texto_upper:
            dados["status_imposto"] = "SEM COBRANÇA"
        elif "A PAGAR" in texto_upper:
            dados["status_imposto"] = "A PAGAR"

        # 5. REGRAS DE NEGÓCIO PARA LIBERAÇÃO
        # Regra 1: Débito CT = SIM bloqueia a carga (DIFAL Frete) independente do status
        if dados["debito_ct"] == "SIM":
            dados["liberado"] = "NÃO"
            dados["status_imposto"] += " (RETIDA - DÉBITO CT)"
            
        # Regra 2: Débito CT = NÃO + Status PAGA ou SEM COBRANÇA = Liberado
        elif dados["debito_ct"] == "NÃO" and dados["status_imposto"] in ["PAGA", "SEM COBRANÇA"]:
            dados["liberado"] = "SIM"
            
        # Fallback de segurança com base na indicação visual direta do PDF
        elif "LIBERADA\tSIM" in texto_upper or "LIBERADA SIM" in texto_upper:
            if dados["debito_ct"] != "SIM":
                dados["liberado"] = "SIM"

    return dados

# ----------------------------------------------------------------------
# ENDPOINT PRINCIPAL: CONSULTA DE AÇÃO FISCAL
# ----------------------------------------------------------------------
@app.post("/consultar-acao-fiscal")
def api_consultar_acao_fiscal(req: RequisicaoAF):
    chave_mdfe = req.chave_mdfe.strip()
    awb_in = req.awb.strip()

    if not chave_mdfe or not awb_in:
        raise HTTPException(status_code=400, detail="Chave MDF-e e AWB são obrigatórias.")

    # 1. VERIFICAÇÃO NO GOOGLE SHEETS (HISTÓRICO)
    sh = conectar_google_sheets()
    if sh:
        try:
            aba_af = sh.worksheet("AÇÕES_FISCAIS")
            registros = aba_af.get_all_records()
            existente = next((r for r in registros if str(r.get("CHAVE_MDFE")) == chave_mdfe), None)

            if existente and str(existente.get("LIBERADO")).upper() == "SIM":
                return {
                    "origem": "banco_de_dados",
                    "chave_mdfe": chave_mdfe,
                    "awb": existente.get("AWB"),
                    "num_af": existente.get("NUM_AF"),
                    "status_imposto": existente.get("STATUS_IMPOSTO"),
                    "liberado": "SIM",
                    "mensagem": "Consulta recuperada do histórico (Já Liberado)."
                }
        except Exception as err_sheet:
            print(f"Erro ao verificar aba do Sheets: {err_sheet}")

    # 2. EXECUÇÃO DO SCRAPING (PLAYWRIGHT)
    awb_limpa = awb_in if awb_in.startswith("957") else f"957{awb_in}"
    download_dir = os.path.join(os.getcwd(), "downloads")
    os.makedirs(download_dir, exist_ok=True)

    resultado = {
        "origem": "sitram_live",
        "chave_mdfe": chave_mdfe,
        "awb": awb_limpa,
        "num_af": "N/A",
        "status_imposto": "Erro na Consulta",
        "liberado": "NÃO",
        "mensagem": "Sucesso"
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()

            page.goto("https://portal-sitram.sefaz.ce.gov.br/sitram-internet/#/", timeout=30000)
            page.wait_for_load_state("domcontentloaded")

            page.get_by_text("Consultas", exact=True).click()
            time.sleep(0.5)
            page.get_by_role("link", name="Ação Fiscal").first.click()
            page.get_by_label("PDF").check()

            # Preenchimento sequencial obrigatório
            campo_mdfe = page.get_by_placeholder("Insira aqui uma chave de acesso (MDF-e)").or_(page.locator("input").first)
            campo_mdfe.fill(chave_mdfe)
            campo_mdfe.dispatch_event("change")
            time.sleep(1)

            if page.locator("mat-select, select").count() > 0:
                page.locator("mat-select, select").first.click()
                page.get_by_text("AWB", exact=True).click()
                
                campo_awb = page.get_by_placeholder("Insira aqui").or_(page.locator("input").nth(1))
                campo_awb.fill(awb_limpa)

            with page.expect_download(timeout=25000) as download_info:
                page.get_by_role("button", name="Pesquisar").click()

            download = download_info.value
            pdf_path = os.path.join(download_dir, f"AF_{awb_limpa}.pdf")
            download.save_as(pdf_path)

            dados_pdf = extrair_dados_pdf_af(pdf_path)
            resultado.update(dados_pdf)
            browser.close()

            if os.path.exists(pdf_path):
                os.remove(pdf_path)

            # 3. ATUALIZAÇÃO NO GOOGLE SHEETS
            if sh:
                agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                aba_af = sh.worksheet("AÇÕES_FISCAIS")
                cell = None
                try:
                    cell = aba_af.find(chave_mdfe)
                except Exception:
                    pass

                if cell:
                    aba_af.update_cell(cell.row, 3, resultado["num_af"])
                    aba_af.update_cell(cell.row, 4, resultado["status_imposto"])
                    aba_af.update_cell(cell.row, 5, resultado["liberado"])
                    aba_af.update_cell(cell.row, 6, agora)
                else:
                    aba_af.append_row([
                        chave_mdfe, awb_limpa, resultado["num_af"],
                        resultado["status_imposto"], resultado["liberado"], agora
                    ])

    except Exception as e:
        resultado["mensagem"] = f"Erro na raspagem: {str(e)}"

    return resultado
