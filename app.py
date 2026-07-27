import base64
import os
import pandas as pd
import requests
import streamlit as st
from sitram import consultar_chaves_sitram

CACHE_FILE = "resultados_cache.csv"

# 1. Configuração da página
st.set_page_config(
    page_title="LATAM Cargo | Saneamento D2D",
    page_icon="✈️",
    layout="wide",
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

# 2. Estilização CSS Totalmente Blindada (Força Dark Mode em Tudo)
st.markdown(
    """
    <style>
        /* Força o tema escuro em toda a árvore do HTML */
        :root {
            color-scheme: dark !important;
        }

        html, body, [data-testid="stAppViewContainer"], .stApp, [data-testid="stHeader"] {
            background-color: #0B101D !important;
            color: #F8FAFC !important;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
        }

        /* Textos e Labels */
        p, span, div, label, h1, h2, h3, h4, h5, h6, .stMarkdown {
            color: #F8FAFC !important;
        }

        /* Banner Topo Moderno */
        .latam-banner {
            background: linear-gradient(135deg, #18002E 0%, #250046 100%);
            padding: 30px 24px;
            border-radius: 14px;
            text-align: center;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4);
            margin-bottom: 30px;
            border: 1px solid rgba(255, 255, 255, 0.08);
        }

        .latam-banner img {
            max-width: 320px !important;
            width: 100% !important;
            height: auto;
            margin-bottom: 12px;
        }

        .latam-banner h1 {
            color: #FFFFFF !important;
            font-size: 28px !important;
            font-weight: 700 !important;
            margin: 8px 0 4px 0 !important;
            letter-spacing: -0.5px;
        }

        .latam-banner p {
            color: #94A3B8 !important;
            font-size: 15px !important;
            margin: 0 !important;
        }

        /* Inputs, Textareas e Selectboxes */
        .stTextArea textarea, .stTextInput input, div[data-baseweb="select"] > div {
            background-color: #131B2E !important;
            color: #F8FAFC !important;
            -webkit-text-fill-color: #F8FAFC !important;
            font-size: 14px !important;
            font-weight: 500 !important;
            border: 1px solid #2A364F !important;
            border-radius: 10px !important;
        }

        .stTextArea textarea {
            font-family: monospace !important;
        }

        /* Cor dos Menus Dropdown (Selectbox) no Modo Claro */
        div[data-baseweb="popover"], div[data-baseweb="menu"], ul[role="listbox"], li[role="option"] {
            background-color: #131B2E !important;
            color: #F8FAFC !important;
        }

        /* Botão Principal e Botão de Download */
        div.stButton > button, div.stDownloadButton > button {
            background: linear-gradient(135deg, #E2001A 0%, #B80015 100%) !important;
            color: #FFFFFF !important;
            font-weight: 600 !important;
            font-size: 15px !important;
            height: 3em !important;
            border-radius: 10px !important;
            border: none !important;
            width: 100% !important;
            margin-top: 14px;
            box-shadow: 0 4px 14px rgba(226, 0, 26, 0.35);
            transition: all 0.2s ease-in-out;
        }
        
        div.stButton > button:hover, div.stDownloadButton > button:hover {
            background: linear-gradient(135deg, #FF1A35 0%, #D10018 100%) !important;
            color: #FFFFFF !important;
            transform: translateY(-1px);
        }

        /* Containers e Cards */
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

        /* TABELA CUSTOMIZADA E 100% ESCURA (Substitui o Dataframe nativo) */
        .table-container {
            max-height: 400px;
            overflow-y: auto;
            border-radius: 10px;
            border: 1px solid #1E293B;
            margin-bottom: 15px;
        }

        table.custom-table {
            width: 100%;
            border-collapse: collapse;
            background-color: #131B2E;
            color: #F8FAFC;
            font-size: 13px;
            text-align: left;
        }

        table.custom-table th {
            background-color: #182238;
            color: #E2001A;
            padding: 12px;
            position: sticky;
            top: 0;
            border-bottom: 2px solid #2A364F;
            font-weight: bold;
            text-transform: uppercase;
        }

        table.custom-table td {
            padding: 10px 12px;
            border-bottom: 1px solid #1E293B;
            word-break: break-all;
        }

        table.custom-table tr:hover {
            background-color: #1C2840;
        }

        /* Alertas do Streamlit */
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


# Função para desenhar a tabela escura sem depender do componente nativo do Streamlit
def exibir_tabela_escura(df):
    html = '<div class="table-container"><table class="custom-table"><thead><tr>'
    for col in df.columns:
        html += f"<th>{col}</th>"
    html += "</tr></thead><tbody>"

    for _, row in df.iterrows():
        html += "<tr>"
        for val in row:
            html += f"<td>{val}</td>"
        html += "</tr>"

    html += "</tbody></table></div>"
    return html


# 3. BANNER PRINCIPAL
logo_html = (
    f'<img src="data:image/png;base64,{logo_b64}"><br>' if logo_b64 else ""
)

st.markdown(
    f"""
    <div class="latam-banner">
        {logo_html}
        <h1>Assistente de Saneamento D2D</h1>
        <p>Módulo de Automação de Consulta SITRAM / SEFAZ-CE — LATAM Cargo</p>
    </div>
""",
    unsafe_allow_html=True,
)

# 4. CONTEÚDO PRINCIPAL (2 COLUNAS)
col_esquerda, col_direita = st.columns(2, gap="large")

with col_esquerda:
    st.markdown('<div class="latam-card">', unsafe_allow_html=True)
    st.subheader("1. Entrada de Dados")

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
    st.subheader("2. Painel de Acompanhamento")

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
                tabela_placeholder.markdown(
                    exibir_tabela_escura(df_temp), unsafe_allow_html=True
                )

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

        # Renderiza a tabela em HTML com visual escuro permanente
        st.markdown(exibir_tabela_escura(df_exibir), unsafe_allow_html=True)

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
st.subheader("💬 Central de Erros, Dúvidas ou Sugestões")
st.write(
    "Viu algum erro nos resultados ou tem uma ideia para melhorar o sistema? Mande abaixo!"
)

FORMSPREE_ID = "mrenybwd"  # <--- LEMBRE-SE DE COLOCAR SEU ID DO FORMSPREE AQUI
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
