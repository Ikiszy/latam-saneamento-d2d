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


def consultar_chaves_sitram(lista_chaves, callback_progresso=None):
    """Navega pelo menu do SITRAM e pesquisa as chaves informadas."""
    resultados = []

    # Se já existir um arquivo temporário de uma busca anterior, limpa ele ao iniciar uma nova
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
            # 1. Acessa a página principal do SITRAM
            page.goto(
                "https://portal-sitram.sefaz.ce.gov.br/sitram-internet/#/",
                timeout=config.TIMEOUT,
            )
            page.wait_for_load_state("domcontentloaded", timeout=config.TIMEOUT)

            # 2. Clica no menu lateral 'Consultas'
            menu_consultas = page.get_by_text("Consultas", exact=True)
            menu_consultas.click()

            # 3. Clica no link 'Nota Fiscal'
            opt_nota = page.get_by_role("link", name="Nota Fiscal").first
            opt_nota.click()

            page.wait_for_selector("input, textarea", timeout=config.TIMEOUT)

        except Exception as e:
            print(f"Erro na navegação inicial do menu: {e}")

        total_chaves = len(lista_chaves)

        for indice, chave in enumerate(lista_chaves, start=1):
            chave = chave.strip()
            if not chave:
                continue

            resultado_item = {
                "acao_fiscal": chave,
                "nota": "",
                "imposto": "Não Encontrado",
                "situacao": "PENDENTE",
            }

            try:
                campo = page.get_by_role("textbox")
                campo.click()
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                campo.fill(chave)

                btn_pesquisar = page.get_by_role("button", name="Pesquisar")
                btn_pesquisar.click()

                seletor_celula = "td:nth-child(4) > .st-cell-content"
                page.wait_for_selector(seletor_celula, timeout=config.TIMEOUT)

                time.sleep(1.5)

                # FIX: .first evita o erro de strict mode quando o SITRAM retorna múltiplos elementos/linhas
                status_texto = page.locator(seletor_celula).first.inner_text()

                match_nota = re.search(
                    r"Nota\s*fiscal:\s*(.*)", status_texto, re.IGNORECASE
                )
                match_imposto = re.search(
                    r"Imposto:\s*(.*)", status_texto, re.IGNORECASE
                )

                if match_nota:
                    nota_val = (
                        match_nota.group(1)
                        .split("Imposto:")[0]
                        .split("\n")[0]
                        .strip()
                    )
                    resultado_item["nota"] = nota_val if nota_val else "N/A"
                else:
                    resultado_item["nota"] = "N/A"

                if match_imposto:
                    imposto_val = match_imposto.group(1).split("\n")[0].strip()
                    resultado_item["imposto"] = (
                        imposto_val if imposto_val else "Não Informado"
                    )
                else:
                    linhas = [
                        l.strip() for l in status_texto.split("\n") if l.strip()
                    ]
                    resultado_item["imposto"] = (
                        " / ".join(linhas) if linhas else "Não Informado"
                    )

                texto_completo = status_texto.upper()
                tem_cobranca_ativa = any(
                    termo in texto_completo
                    for termo in ["A PAGAR", "A RECOLHER", "PENDENTE"]
                )

                # Regras de liberação: PAGO, SEM COBRANÇA ou ISENTO
                est_liberado = any(
                    termo in texto_completo
                    for termo in [
                        "PAGO",
                        "PAGA",
                        "SEM COBRANCA",
                        "SEM COBRANÇA",
                        "ISENTO",
                        "ISENTA",
                    ]
                )

                if est_liberado and not tem_cobranca_ativa:
                    resultado_item["situacao"] = "LIBERADA"
                else:
                    resultado_item["situacao"] = "PENDENTE"

            except PlaywrightTimeoutError:
                resultado_item["imposto"] = "Timeout na busca"
                resultado_item["situacao"] = "ERRO"
            except Exception as ex:
                resultado_item["imposto"] = f"Erro: {str(ex)}"
                resultado_item["situacao"] = "ERRO"

            resultados.append(resultado_item)

            # SALVAMENTO EM TEMPO REAL: Escreve no disco item por item
            try:
                df_parcial = pd.DataFrame(resultados)
                df_parcial.columns = [
                    "Chave / Ação Fiscal",
                    "Nota Fiscal",
                    "Situação Imposto",
                    "Status Final",
                ]
                df_parcial.to_csv(
                    CACHE_FILE, index=False, sep=";", encoding="utf-8-sig"
                )
            except Exception:
                pass

            if callback_progresso:
                callback_progresso(
                    atual=indice, total=total_chaves, item=resultado_item
                )

            time.sleep(6.0)

        browser.close()

    return resultados
