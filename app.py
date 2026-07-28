import base64
import os
import pandas as pd
import requests
import streamlit as st
from sitram import consultar_chaves_sitram

CACHE_FILE = "resultados_cache.csv"

# 1. Configuração da página (com informações de About para melhorar o SEO)
st.set_page_config(
    page_title="LATAM Cargo | Saneamento D2D",
    page_icon="✈️",
    layout="wide",
    menu_items={
        "About": "Módulo de Automação de Consulta SITRAM / SEFAZ-CE — LATAM Cargo"
    },
)


# Converter imagem para base64
def get_image_base64(path):
    if os.path.exists(path):
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    return ""


logo_b64 = get_image_base64("latam_logo.png")

if "resultados_finais" not in st.session_state:
    st.session_state["resultados_finais"] = None

# 2. Estilização CSS (Centralizado, Logo Maior, Espaçamento Justo)
st.markdown(
    """
    <style>
        /* Força fundo escuro geral e texto claro */
        html, body, [data-testid="stAppViewContainer"], .stApp, [data-testid="stHeader"] {
            background-color: #0B101D !important;
            color: #F8FAFC !important;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
        }

        p, span, div, label, h1, h2, h3, h4, h5, h6, .stMarkdown {
            color: #F8FAFC !important;
        }

        /* BANNER CENTRALIZADO COMPACTO */
        .latam-banner-center {
            background: linear-gradient(135deg, #18002E 0%, #250046 100%);
            padding: 22px 20px 18px 20px;
            border-radius: 14px;
            text-align: center;
            box-shadow: 0 8px 22px rgba(0, 0, 0, 0.35);
            margin-bottom: 25px;
            border: 1px solid rgba(255, 255, 255, 0.08);
        }

        .latam-banner-center img {
            max-width: 260px !important;
            width: 100% !important;
            height: auto;
            margin-bottom: 6px;
            display: inline-block;
        }

        .latam-banner-center h1 {
            color: #FFFFFF !important;
            font-size: 26px !important;
            font-weight: 700 !important;
            margin: 2px 0 2px 0 !important;
            letter-spacing: -0.4px;
            line-height: 1.2;
        }

        .latam-banner-center p {
            color: #94A3B8 !important;
            font-size: 14px !important;
            margin: 0 !important;
        }

        /* Inputs e Textareas */
        .stTextArea textarea, .stTextInput input {
            background-color: #131B2E !important;
            color: #F8FAFC !important;
            -webkit-text-fill-color: #F8FAFC !important;
            font-size: 14px !important;
            border: 1px solid #2A364F !important;
            border-radius: 10px !important;
        }

        .stTextArea textarea {
            font-family: monospace !important;
        }

        /* Selectbox */
        div[data-baseweb="select"] > div {
            background-color: #131B2E !important;
            color: #F8FAFC !important;
            border: 1px solid #2A364F !important;
            border-radius: 10px !important;
        }

        div[data-baseweb="select"] span {
            color: #F8FAFC !important;
        }

        /* Botões */
        div.stButton > button, div.stDownloadButton > button, div[data-testid="stFormSubmitButton"] > button {
            background: linear-gradient(135deg, #E2001A 0%, #B80015 100%) !important;
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
            font-weight: 600 !important;
            font-size: 15px !important;
            border-radius: 10px !important;
            border: none !important;
            width: 100% !important;
            box-shadow: 0 4px 14px rgba(226, 0, 26, 0.35) !important;
            transition: all 0.2s ease-in-out !important;
        }
        
        div.stButton > button:hover, div.stDownloadButton > button:hover, div[data-testid="stFormSubmitButton"] > button:hover {
            background: linear-gradient(135deg, #FF1A35 0%, #D10018 100%) !important;
            color: #FFFFFF !important;
            transform: translateY(-1px);
        }

        /* Cards Containers */
        .latam-card {
            background-color: #131B2E !important;
            border: 1px solid #1E293B !important;
            border-radius: 12px;
            padding: 22px;
            margin-bottom: 20px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
        }

        .latam-quote {
            font-style: italic;
            color: #94A3B8 !important;
            font-size: 14px;
            line-height: 1.6;
            border-left: 3px solid #E2001A;
            padding-left: 14px;
        }

        /* DataFrame FIX */
        [data-testid="stDataFrame"] {
            background-color: #131B2E !important;
            border-radius: 10px;
            border: 1px solid #2A364F;
        }

        @media (prefers-color-scheme: light) {
            [data-testid="stDataFrame"] canvas {
                filter: invert(0.92) hue-rotate(180deg) !important;
            }
        }

        /* Alertas */
        .stAlert {
            background-color: #131B2E !important;
            color: #F8FAFC !important;
            border: 1px solid #1E293B !important;
            border-radius: 10px !important;
        }
        
        .stAlert p {
            color: #F8FAFC !important;
        }
    </style>
""",
    unsafe_allow_html=True,
)

# 3. HEADER COM TAG <main> E ATRIBUTO ALT NA IMAGEM (Corrigido para Acessibilidade)
logo_html = (
    f'<img src="data:image/png;base64,{logo_b64}" alt="Logo LATAM Cargo"><br>'
    if logo_b64
    else ""
)

st.markdown(
    f"""
    <main class="latam-banner-center">
        {logo_html}
        <h1>Assistente de Saneamento D2D</h1>
        <p>Módulo de Automação de Consulta SITRAM / SEFAZ-CE — LATAM Cargo</p>
    </main>
""",
    unsafe_allow_html=True,
)

# 4. CONTEÚDO PRINCIPAL (2 COLUNAS)
col_esquerda, col_direita = st.columns(2, gap="large")

with col_esquerda:
    st.markdown('<div class="latam-card">', unsafe_allow_html=True)
    st.header("1. Entrada de Dados")

    modo = st.radio(
        "Como você deseja importar as chaves?",
        ["Digitar / Colar Chaves", "Carregar Arquivo (TXT / Excel)"],
        horizontal=True,
    )

    chaves_lista = []

    if modo == "Digitar / Colar Chaves":
        texto_chaves = st.text_area(
            "Cole abaixo as chaves de acesso (uma por linha):",
            height=220,
            placeholder="3525041733098000127550030000000001\n3525041733098000127550030000000002",
        )
        if texto_chaves:
            chaves_lista = [
                c.strip() for c in texto_chaves.split("\n") if c.strip()
            ]
    else:
        arquivo = st.file_uploader(
            "Selecione um arquivo de texto (.txt) ou planilha (.xlsx):",
            type=["txt", "xlsx", "csv"],
        )
        if arquivo:
            if arquivo.name.endswith(".txt"):
                chaves_lista = [
                    linha.decode("utf-8").strip()
                    for linha in arquivo.readlines()
                    if linha.decode("utf-8").strip()
                ]
            else:
                df_upload = pd.read_excel(arquivo, dtype=str)
                chaves_lista = df_upload.iloc[:, 0].astype(str).tolist()

    st.write(f"**Total de chaves identificadas:** `{len(chaves_lista)}`")
    btn_iniciar = st.button("INICIAR CONSULTA SITRAM")
    st.markdown("</div>", unsafe_allow_html=True)

with col_direita:
    st.markdown('<div class="latam-card">', unsafe_allow_html=True)
    st.header("2. Painel de Acompanhamento")

    if btn_iniciar:
        if not chaves_lista:
            st.warning("Insira ao menos uma chave de acesso para iniciar.")
        else:
            bar_progresso = st.progress(0)
            status_texto = st.empty()
            tabela_placeholder = st.empty()

            resultados_em_tempo_real = []

            def atualizar_interface(atual, total, item):
                percent = int((atual / total) * 100)
                bar_progresso.progress(percent)
                status_texto.text(
                    f"Processando: {atual} de {total} | Chave: {item['acao_fiscal']}"
                )
                resultados_em_tempo_real.append(item)

                df_temp = pd.DataFrame(resultados_em_tempo_real).astype(str)
                df_temp.columns = [
                    "Chave / Ação Fiscal",
                    "Nota Fiscal",
                    "Situação Imposto",
                    "Status Final",
                ]
                tabela_placeholder.dataframe(df_temp, use_container_width=True)

            with st.spinner("Consultando dados na SEFAZ..."):
                resultados = consultar_chaves_sitram(
                    chaves_lista, callback_progresso=atualizar_interface
                )

            status_texto.empty()
            st.success("Consulta finalizada com sucesso!")
            st.session_state["resultados_finais"] = resultados

    # Lógica de exibição e resgate do backup
    df_exibir = None

    if st.session_state["resultados_finais"] is not None:
        df_exibir = pd.DataFrame(st.session_state["resultados_finais"]).astype(str)
        df_exibir.columns = [
            "Chave / Ação Fiscal",
            "Nota Fiscal",
            "Situação Imposto",
            "Status Final",
        ]
    elif os.path.exists(CACHE_FILE) and not btn_iniciar:
        try:
            df_exibir = pd.read_csv(CACHE_FILE, sep=";", dtype=str)
            df_exibir = df_exibir.astype(str)
        except Exception:
            df_exibir = None

    if df_exibir is not None:
        if not btn_iniciar:
            st.info("📌 Exibindo os resultados recuperados da sua última consulta:")

        st.dataframe(df_exibir, use_container_width=True)

        csv_data = df_exibir.to_csv(index=False, sep=";", encoding="utf-8-sig")

        st.download_button(
            label="📥 Baixar Planilha para Google Sheets (.csv)",
            data=csv_data,
            file_name="Relatorio_Saneamento_LATAM.csv",
            mime="text/csv",
        )
    elif not btn_iniciar:
        st.info(
            "Aguardando início. Insira as chaves ao lado e clique em **INICIAR CONSULTA SITRAM**."
        )

        st.markdown(
            """
            <div class="latam-quote">
                "Levar os sonhos ao seu destino com segurança, eficiência e agilidade — otimizando processos fiscais para impulsionar a operação LATAM Cargo."
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)

# --- 5. SEÇÃO DE FEEDBACK (FORMSPREE) ---
st.markdown("<br>", unsafe_allow_html=True)

st.markdown('<div class="latam-card">', unsafe_allow_html=True)
st.header("💬 Central de Erros, Dúvidas ou Sugestões")
st.write(
    "Viu algum erro nos resultados ou tem uma ideia para melhorar o sistema? Mande abaixo!"
)

FORMSPREE_ID = "mrenybwd"
FORMSPREE_URL = f"https://formspree.io/f/mrenybwd"

with st.form(key="form_feedback_formspree", clear_on_submit=True):
    nome_usuario = st.text_input(
        "Seu nome (opcional):", placeholder="Ex: João Silva"
    )
    tipo_mensagem = st.selectbox(
        "O que você deseja reportar?",
        ["Erro / Bug no resultado", "Sugestão de melhoria", "Outro"],
    )
    mensagem = st.text_area(
        "Descreva o erro ou sugestão em detalhes:",
        placeholder="Escreva aqui...",
    )

    btn_enviar_feedback = st.form_submit_button("Enviar Feedback 🚀")

if btn_enviar_feedback:
    if not mensagem.strip():
        st.warning("Por favor, digite uma mensagem antes de enviar.")
    else:
        dados_envio = {
            "nome": nome_usuario or "Anônimo",
            "tipo": tipo_mensagem,
            "mensagem": mensagem,
        }

        try:
            resposta = requests.post(FORMSPREE_URL, data=dados_envio)
            if resposta.status_code == 200:
                st.success(
                    "Obrigado! Seu feedback foi enviado direto para o desenvolvedor."
                )
            else:
                st.error(
                    "Não foi possível enviar o feedback. Verifique se inseriu o ID correto do Formspree."
                )
        except Exception as e:
            st.error(f"Erro ao conectar com o servidor: {e}")

st.markdown("</div>", unsafe_allow_html=True)
