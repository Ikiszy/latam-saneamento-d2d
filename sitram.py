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


def resetar_pagina_consulta(page):
    """Navega novamente para a tela de Nota Fiscal para resetar o formulário."""
    try:
        page.goto(
            "https://portal-sitram.sefaz.ce.gov.br/sitram-internet/#/consultas/nota-fiscal",
            timeout=config.TIMEOUT,
        )
        page.wait_for_selector("input, textarea", timeout=config.TIMEOUT)
        time.sleep(1.0)
    except Exception:
        pass


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

            # 2. Navegação inicial no menu
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
                # Localiza o campo de busca
                campo = page.get_by_role("textbox")
                
                # Se o campo não estiver visível (ex: tela travada), força o reset da página
                if not campo.is_visible():
                    resetar_pagina_consulta(page)
                    campo = page.get_by_role("textbox")

                campo.click()
                time.sleep(0.2)
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                campo.fill(chave_val)
                time.sleep(0.2)

                btn_pesquisar = page.get_by_role("button", name="Pesquisar")
                btn_pesquisar.click()

                # --- 1. VERIFICA SE DEU MODAL DE "NÃO ENCONTRADA" OU SOBRANTE ---
                time.sleep(1.2)
                modal_visivel = False
                try:
                    btn_ok = page.locator("button:has-text('OK')").first
                    if btn_ok.is_visible(timeout=1500):
                        btn_ok.click()
                        modal_visivel = True
                        time.sleep(0.5)
                except Exception:
                    pass

                # --- 2. VERIFICA SE A TABELA APARECEU ---
                seletor_celula = "td:nth-child(4) > .st-cell-content"
                encontrou_tabela = False

                if not modal_visivel:
                    try:
                        page.wait_for_selector(seletor_celula, timeout=4000)
                        encontrou_tabela = True
                    except PlaywrightTimeoutError:
                        encontrou_tabela = False

                # SE NÃO ENCONTROU A TABELA OU DEU MODAL: TRATA COMO SOBRANTE E RESETA A PÁGINA
                if modal_visivel or not encontrou_tabela:
                    resultado_item["nota"] = "N/A"
                    resultado_item["imposto"] = "Não Encontrada / Sobrante"
                    resultado_item["situacao"] = "SOBRANTE / NÃO ENCONTRADA"
                    resultados.append(resultado_item)

                    # Salva no cache parcial
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

                    # RESETA A PÁGINA PARA A PRÓXIMA CONSULTA NÃO FALHAR
                    resetar_pagina_consulta(page)
                    continue

                # --- 3. SE ENCONTROU A TABELA, EXTRAI OS DADOS ---
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
                # Em caso de exceção não esperada, reseta a tela para tentar salvar a próxima
                resetar_pagina_consulta(page)

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
