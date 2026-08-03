import os
import re
import subprocess
import time
import config
import pandas as pd
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

CACHE_FILE = "resultados_cache.csv"

# Garante que os navegadores do Playwright estejam instalados
try:
    subprocess.run(["playwright", "install", "chromium"], check=True)
except Exception as e:
    print(f"Aviso de instalação do Playwright: {e}")


def consultar_chaves_sitram(lista_dados, callback_progresso=None):
    """
    Navega pelo menu do SITRAM e pesquisa as chaves informadas.
    Consulta feita unicamente pela Chave de Acesso na SEFAZ.
    """
    resultados = []

    if os.path.exists(CACHE_FILE):
        try:
            os.remove(CACHE_FILE)
        except Exception:
            pass

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=config.HEADLESS, slow_mo=config.SLOW_MO
        )
        page = browser.new_page()

        try:
            # 1. Acessa a página principal
            page.goto(
                "https://portal-sitram.sefaz.ce.gov.br/sitram-internet/#/",
                timeout=config.TIMEOUT,
            )
            page.wait_for_load_state("domcontentloaded", timeout=config.TIMEOUT)

            # 2. Navegação do menu
            menu_consultas = page.get_by_text("Consultas", exact=True)
            menu_consultas.click()

            opt_nota = page.get_by_role("link", name="Nota Fiscal").first
            opt_nota.click()

            page.wait_for_selector("input, textarea", timeout=config.TIMEOUT)

        except Exception as e:
            print(f"Erro na navegação inicial do menu: {e}")

        total_itens = len(lista_dados)

        for indice, item in enumerate(lista_dados, start=1):
            if isinstance(item, dict):
                awb_val = item.get("awb", "N/A").strip()
                chave_val = item.get("chave", "").strip()
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
                # Limpa e digita a chave
                campo = page.get_by_role("textbox")
                campo.click()
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                campo.fill(chave_val)

                btn_pesquisar = page.get_by_role("button", name="Pesquisar")
                btn_pesquisar.click()

                # --- PASSO 1: TRATAR MODAL / POPUP DE ALERTA ---
                time.sleep(1.0)
                try:
                    btn_ok = page.locator("button:has-text('OK')").first
                    if btn_ok.is_visible(timeout=1500):
                        btn_ok.click()
                        time.sleep(0.5)
                except Exception:
                    pass

                # --- PASSO 2: AGUARDAR TABELA COM TIMEOUT CURTO (3s) ---
                seletor_celula = "td:nth-child(4) > .st-cell-content"
                
                try:
                    page.wait_for_selector(seletor_celula, timeout=3500)
                    encontrou_tabela = True
                except PlaywrightTimeoutError:
                    encontrou_tabela = False

                # Se a tabela não apareceu, trata como Chave Não Encontrada / Sobrante e PULA para a próxima
                if not encontrou_tabela:
                    resultado_item["imposto"] = "Não Encontrada / Sobrante"
                    resultado_item["situacao"] = "SOBRANTE / NÃO ENCONTRADA"
                    resultados.append(resultado_item)

                    # Salva progresso parcial
                    try:
                        df_parcial = pd.DataFrame(resultados)
                        df_parcial.columns = [
                            "AWB", "Chave / Ação Fiscal", "Nota Fiscal", "Situação Imposto", "Status Final"
                        ]
                        df_parcial.to_csv(CACHE_FILE, index=False, sep=";", encoding="utf-8-sig")
                    except Exception:
                        pass

                    if callback_progresso:
                        callback_progresso(atual=indice, total=total_itens, item=resultado_item)

                    # Recarrega/reseta a consulta para garantir que o campo fique limpo
                    continue

                # --- PASSO 3: LER DADOS CASO A TABELA TENHA SIDO ENCONTRADA ---
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
                resultado_item["imposto"] = f"Erro na busca"
                resultado_item["situacao"] = "ERRO"

            resultados.append(resultado_item)

            # Grava no cache
            try:
                df_parcial = pd.DataFrame(resultados)
                df_parcial.columns = [
                    "AWB", "Chave / Ação Fiscal", "Nota Fiscal", "Situação Imposto", "Status Final"
                ]
                df_parcial.to_csv(CACHE_FILE, index=False, sep=";", encoding="utf-8-sig")
            except Exception:
                pass

            if callback_progresso:
                callback_progresso(atual=indice, total=total_itens, item=resultado_item)

            time.sleep(1.0)

        browser.close()

    return resultados
