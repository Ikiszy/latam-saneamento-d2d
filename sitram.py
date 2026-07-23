import os
import re
import time
import subprocess
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import config

# Garante que os navegadores do Playwright estejam instalados na nuvem
try:
    subprocess.run(["playwright", "install", "chromium"], check=True)
except Exception as e:
    print(f"Aviso de instalação do Playwright: {e}")


def consultar_chaves_sitram(lista_chaves, callback_progresso=None):
    """Navega pelo menu do SITRAM e pesquisa as chaves informadas de forma otimizada."""
    resultados = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=config.HEADLESS, slow_mo=config.SLOW_MO)
        page = browser.new_page()

        try:
            # 1. Acessa a página principal do SITRAM
            page.goto("https://portal-sitram.sefaz.ce.gov.br/sitram-internet/#/", timeout=config.TIMEOUT)
            page.wait_for_load_state("domcontentloaded", timeout=config.TIMEOUT)

            # 2. Clica no menu lateral 'Consultas'
            menu_consultas = page.get_by_text("Consultas", exact=True)
            menu_consultas.click()

            # 3. Clica no link 'Nota Fiscal'
            opt_nota = page.get_by_role("link", name="Nota Fiscal").first
            opt_nota.click()

            # Aguarda o campo de busca estar disponível
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
                "situacao": "PENDENTE"
            }

            try:
                # Preenche a chave
                campo = page.get_by_role("textbox")
                campo.click()
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                campo.fill(chave)

                # Clica em Pesquisar
                btn_pesquisar = page.get_by_role("button", name="Pesquisar")
                btn_pesquisar.click()

                # Aguarda dinamicamente o resultado aparecer na tela
                seletor_celula = "td:nth-child(4) > .st-cell-content"
                page.wait_for_selector(seletor_celula, timeout=config.TIMEOUT)

                status_texto = page.locator(seletor_celula).inner_text()
                
                # Extrai a Nota Fiscal e Imposto
                match_nota = re.search(r"Nota\s*fiscal:\s*(.*)", status_texto, re.IGNORECASE)
                match_imposto = re.search(r"Imposto:\s*(.*)", status_texto, re.IGNORECASE)

                if match_nota:
                    nota_val = match_nota.group(1).split("Imposto:")[0].split("\n")[0].strip()
                    resultado_item["nota"] = nota_val if nota_val else "N/A"
                else:
                    resultado_item["nota"] = "N/A"

                if match_imposto:
                    imposto_val = match_imposto.group(1).split("\n")[0].strip()
                    resultado_item["imposto"] = imposto_val if imposto_val else "Não Informado"
                else:
                    linhas = [l.strip() for l in status_texto.split("\n") if l.strip()]
                    resultado_item["imposto"] = " / ".join(linhas) if linhas else "Não Informado"

                # REGRA DE STATUS AJUSTADA
                texto_completo = status_texto.upper()

                # Verifica se há cobrança pendente explícita
                tem_cobranca_ativa = any(termo in texto_completo for termo in ["A PAGAR", "A RECOLHER", "PENDENTE"])

                # Se consta PAGO ou PAGA e não há cobrança ativa -> LIBERADA
                if ("PAGO" in texto_completo or "PAGA" in texto_completo) and not tem_cobranca_ativa:
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

            if callback_progresso:
                callback_progresso(atual=indice, total=total_chaves, item=resultado_item)

            time.sleep(0.3)

        browser.close()

    return resultados
