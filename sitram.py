import os
import re
import subprocess
import time
import pandas as pd
from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

CACHE_FILE = "resultados_cache.csv"
TIMEOUT = 15000  # Tempo limite em ms (15s)

# Garante a instalação do Chromium no Playwright
try:
    subprocess.run(["playwright", "install", "chromium"], check=True)
except Exception as e:
    print(f"Aviso de instalação do Playwright: {e}")


def recarregar_e_preparar(page):
    """
    Força o recarregamento total da página (F5) e navega até o formulário limpo.
    Garante que a tela fique 100% zerada para a próxima consulta.
    """
    try:
        page.reload(wait_until="domcontentloaded", timeout=TIMEOUT)
        time.sleep(1.0)

        # Se não estiver no formulário, clica em Consultas -> Nota Fiscal
        if not page.locator("input, textarea").first.is_visible():
            menu_consultas = page.get_by_text("Consultas", exact=True)
            if menu_consultas.is_visible():
                menu_consultas.click()
                time.sleep(0.5)

            opt_nota = page.get_by_role("link", name="Nota Fiscal").first
            if opt_nota.is_visible():
                opt_nota.click()

        page.wait_for_selector("input, textarea", timeout=TIMEOUT)
        time.sleep(0.5)
    except Exception as e:
        print(f"Aviso ao recarregar página: {e}")


def consultar_chaves_sitram(lista_dados, callback_progresso=None):
    """
    Navega pelo menu do SITRAM e pesquisa as chaves informadas.
    Compatível com Streamlit Cloud (headless=True + flags de sandbox).
    """
    resultados = []

    # Remove o cache antigo do início da sessão se existir
    if os.path.exists(CACHE_FILE):
        try:
            os.remove(CACHE_FILE)
        except Exception:
            pass

    with sync_playwright() as p:
        # Lançamento do navegador configurado para rodar em nuvem (Linux/Streamlit Cloud)
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--single-process",
            ],
        )
        page = browser.new_page()

        try:
            # 1. Acessa a página principal
            page.goto(
                "https://portal-sitram.sefaz.ce.gov.br/sitram-internet/#/",
                timeout=TIMEOUT,
            )
            page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT)

            # 2. Navegação inicial
            menu_consultas = page.get_by_text("Consultas", exact=True)
            menu_consultas.click()

            opt_nota = page.get_by_role("link", name="Nota Fiscal").first
            opt_nota.click()

            page.wait_for_selector("input, textarea", timeout=TIMEOUT)

        except Exception as e:
            print(f"Erro na navegação inicial do menu: {e}")

        total_itens = len(lista_dados)

        for indice, item in enumerate(lista_dados, start=1):
            if isinstance(item, dict):
                awb_val = str(item.get("awb", "N/A")).strip()
                chave_val = str(item.get("chave", "")).strip()
            else:
                awb_val = "N/A"
                chave_val = str(item).strip()

            if not chave_val:
                continue

            resultado_item = {
                "awb": awb_val if awb_val else "N/A",
                "acao_fiscal": chave_val,
                "nota": "N/A",
                "imposto": "Não Encontrado",
                "situacao": "SOBRANTE / NÃO ENCONTRADA",
            }

            try:
                campo = page.get_by_role("textbox").first

                if not campo.is_visible():
                    recarregar_e_preparar(page)
                    campo = page.get_by_role("textbox").first

                # Limpa e preenche a chave
                campo.click()
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                time.sleep(0.2)
                campo.fill(chave_val)
                time.sleep(0.3)

                btn_pesquisar = page.get_by_role("button", name="Pesquisar").first
                btn_pesquisar.click()

                # --- VERIFICA MODAL DE ALERTA / POPUP ---
                time.sleep(1.0)
                modal_detectado = False
                try:
                    btn_ok = page.locator("button:has-text('OK')").first
                    if btn_ok.is_visible(timeout=1000):
                        btn_ok.click()
                        modal_detectado = True
                        time.sleep(0.5)
                except Exception:
                    pass

                # --- VERIFICA SE A TABELA APARECEU ---
                seletor_celula = "td:nth-child(4) > .st-cell-content"
                encontrou_tabela = False

                if not modal_detectado:
                    try:
                        page.wait_for_selector(seletor_celula, timeout=3000)
                        encontrou_tabela = True
                    except PlaywrightTimeoutError:
                        encontrou_tabela = False

                if modal_detectado or not encontrou_tabela:
                    resultado_item["nota"] = "N/A"
                    resultado_item["imposto"] = "Não Encontrada / Sobrante"
                    resultado_item["situacao"] = "SOBRANTE / NÃO ENCONTRADA"
                    resultados.append(resultado_item)

                    # Salva progresso parcial no cache em disco
                    try:
                        df_parcial = pd.DataFrame(resultados).astype(str)
                        df_parcial.columns = [
                            "AWB", "Chave / Ação Fiscal", "Nota Fiscal", "Situação Imposto", "Status Final"
                        ]
                        df_parcial.to_csv(CACHE_FILE, index=False, sep=";", encoding="utf-8-sig")
                    except Exception:
                        pass

                    if callback_progresso:
                        callback_progresso(atual=indice, total=total_itens, item=resultado_item)

                    recarregar_e_preparar(page)
                    continue

                # --- EXTRAI DADOS DA TABELA ---
                status_texto = page.locator(seletor_celula).first.inner_text()

                match_nota = re.search(r"Nota\s*fiscal:\s*(.*)", status_texto, re.IGNORECASE)
                match_imposto = re.search(r"Imposto:\s*(.*)", status_texto, re.IGNORECASE)

                if match_nota:
                    nota_val = match_nota.group(1).split("Imposto:")[0].split("\n")[0].strip()
                    resultado_item["nota"] = nota_val if nota_val else "N/A"

                if match_imposto:
                    imposto_val = match_imposto.group(1).split("\n")[0].strip()
                    resultado_item["imposto"] = imposto_val if imposto_val else "Não Informado"
                else:
                    linhas = [l.strip() for l in status_texto.split("\n") if l.strip()]
                    resultado_item["imposto"] = " / ".join(linhas) if linhas else "Não Informado"

                texto_completo = status_texto.upper()
                tem_cobranca_ativa = any(
                    termo in texto_completo for termo in ["A PAGAR", "A RECOLHER", "PENDENTE"]
                )

                est_liberado = any(
                    termo in texto_completo
                    for termo in ["PAGO", "PAGA", "SEM COBRANCA", "SEM COBRANÇA", "ISENTO", "ISENTA"]
                )

                if est_liberado and not tem_cobranca_ativa:
                    resultado_item["situacao"] = "LIBERADA"
                else:
                    resultado_item["situacao"] = "PENDENTE"

            except Exception as ex:
                resultado_item["imposto"] = "Erro na busca"
                resultado_item["situacao"] = "ERRO"
                recarregar_e_preparar(page)

            resultados.append(resultado_item)

            # Grava no cache
            try:
                df_parcial = pd.DataFrame(resultados).astype(str)
                df_parcial.columns = [
                    "AWB", "Chave / Ação Fiscal", "Nota Fiscal", "Situação Imposto", "Status Final"
                ]
                df_parcial.to_csv(CACHE_FILE, index=False, sep=";", encoding="utf-8-sig")
            except Exception:
                pass

            if callback_progresso:
                callback_progresso(atual=indice, total=total_itens, item=resultado_item)

            time.sleep(0.5)

        browser.close()

    return resultados
