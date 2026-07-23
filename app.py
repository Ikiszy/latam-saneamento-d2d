import base64
import os
import pandas as pd
import requests
import streamlit as st
from sitram import consultar_chaves_sitram

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

# 2. Estilização CSS Corporativa LATAM
st.markdown(
    """
    <style>
        /* Fundo Geral - Azul Marinho LATAM */
        .stApp {
            background-color: #0D192B !important;
            color: #FFFFFF !important;
        }

        /* Banner Indigo/Roxo no Topo */
        .latam-banner {
            background: linear-gradient(135deg, #1B0034 0%, #2A0052 100%);
            padding: 35px 20px;
            border-radius: 16px;
            text-align: center;
            box-shadow: 0 8px 24px rgba(0,0,0,0.3);
            margin-bottom: 25px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .latam-banner img {
            max-width: 380px !important;
            width: 100% !important;
            height: auto;
            margin-bottom: 15px;
        }

        .latam-banner h1 {
            color: #FFFFFF !important;
            font-size: 38px !important;
            font-weight: 800 !important;
            margin: 5px 0 !important;
        }

        .latam-banner p {
            color: #D1D5DB !important;
            font-size: 18px !important;
            margin: 0 !important;
        }

        /* Títulos e Labels */
        .stMarkdown h2, .stMarkdown h3 {
            color: #FFFFFF !important;
            font-size: 22px !important;
            font-weight: 700 !important;
        }

        label, .stRadio label, .stTextArea label, .stFileUploader label, .stTextInput label, .stSelectbox label {
            color: #FFFFFF !important;
            font-size: 15px !important;
            font-weight: 600 !important;
        }

        /* Campo de Digitação e Inputs */
        .stTextArea textarea, .stTextInput input {
            background-color: #162235 !important;
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
            font-size: 15px !important;
            font-weight: 600 !important;
            border: 2px solid #334155 !important;
            border-radius: 8px !important;
        }

        .stTextArea textarea {
            font-family: monospace !important;
        }

        .stTextArea textarea:focus, .stTextInput input:focus {
            border-color: #E2001A !important;
            box-shadow: 0 0 0 1px #E2001A !important;
        }

        /* Botão Vermelho LATAM */
        div.stButton > button {
            background-color: #E2001A !important;
            color: #FFFFFF !important;
            font-weight: bold !important;
            font-size: 18px !important;
            height: 3.2em !important;
            border-radius: 8px !important;
            border: none !important;
            width: 100% !important;
            margin-top: 10px;
            box-shadow: 0 4px 12px rgba(226, 0, 26, 0.3);
        }
        
        div.stButton > button:hover {
            background-color: #C10016 !important;
        }

        /* Cards Informativos */
        .latam-card {
            background-color: #162235;
            border: 1px solid #23354E;
            border-radius: 12px;
            padding: 20px;
            margin-top: 15px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }

        .latam-card-title {
            color: #E2001A;
            font-size: 16px;
            font-weight: bold;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.8px;
        }

        .latam-quote {
            font-style: italic;
            color: #CBD5E1;
            font-size: 15px;
            line-height: 1.5;
            border-left: 3px solid #E2001A;
            padding-left: 12px;
            margin-top: 10px;
        }

        /* Reestilização do Alert */
        .stAlert {
            background-color: #162235 !important;
            color: #FFFFFF !important;
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
        }
    </style>
""",
    unsafe_allow_html=True,
)

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
            height=250,
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
                df_upload = pd.read_excel(arquivo)
                chaves_lista = df_upload.iloc[:, 0].astype(str).tolist()

    st.write(f"**Total de chaves identificadas:** `{len(chaves_lista)}`")
    btn_iniciar = st.button("INICIAR CONSULTA SITRAM")

with col_direita:
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

                df_temp = pd.DataFrame(resultados_em_tempo_real)
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

            # Converte os resultados em CSV para abrir fácil no Google Sheets
            df_final = pd.DataFrame(resultados)
            df_final.columns = [
                "Chave / Ação Fiscal",
                "Nota Fiscal",
                "Situação Imposto",
                "Status Final",
            ]
            
            csv_data = df_final.to_csv(index=False, sep=";", encoding="utf-8-sig")

            st.download_button(
                label="📥 Baixar Planilha para Google Sheets (.csv)",
                data=csv_data,
                file_name="Relatorio_Saneamento_LATAM.csv",
                mime="text/csv",
            )
    else:
        st.info(
            "Aguardando início. Insira as chaves ao lado e clique em **INICIAR CONSULTA SITRAM**."
        )

        # Card 1: Propósito LATAM
        st.markdown(
            """
            <div class="latam-card">
                <div class="latam-card-title">✈️ Nosso Propósito</div>
                <div class="latam-quote">
                    "Levar os sonhos ao seu destino com segurança, eficiência e agilidade — otimizando processos fiscais para impulsionar a operação LATAM Cargo."
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Card 2: Dicas de Operação
        st.markdown(
            """
            <div class="latam-card">
                <div class="latam-card-title">💡 Dicas de Processamento D2D</div>
                <ul style="color: #CBD5E1; font-size: 14px; margin-bottom: 0; padding-left: 20px;">
                    <li>Você pode colar até centenas de chaves de uma só vez.</li>
                    <li>Arquivos <b>.TXT</b> devem conter 1 chave por linha.</li>
                    <li>Planilhas <b>.XLSX</b> devem ter as chaves na primeira coluna.</li>
                    <li>Ao finalizar, o arquivo <b>.CSV</b> gerado pode ser aberto direto no Google Sheets.</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

# --- 5. SEÇÃO DE FEEDBACK (FORMSPREE) ---
st.markdown("<br><hr>", unsafe_allow_html=True)
st.subheader("💬 Central de Erros, Dúvidas ou Sugestões")
st.write("Viu algum erro nos resultados ou tem uma ideia para melhorar o sistema? Mande abaixo!")

FORMSPREE_ID = "mrenybwd"  # <--- COLOQUE O SEU ID DO FORMSPREE AQUI
FORMSPREE_URL = f"https://formspree.io/f/mrenybwd"

with st.form(key="form_feedback_formspree", clear_on_submit=True):
    nome_usuario = st.text_input("Seu nome (opcional):", placeholder="Ex: João Silva")
    tipo_mensagem = st.selectbox("O que você deseja reportar?", ["Erro / Bug no resultado", "Sugestão de melhoria", "Outro"])
    mensagem = st.text_area("Descreva o erro ou sugestão em detalhes:", placeholder="Escreva aqui...")
    
    btn_enviar_feedback = st.form_submit_button("Enviar Feedback 🚀")

if btn_enviar_feedback:
    if not mensagem.strip():
        st.warning("Por favor, digite uma mensagem antes de enviar.")
    else:
        dados_envio = {
            "nome": nome_usuario or "Anônimo",
            "tipo": tipo_mensagem,
            "mensagem": mensagem
        }
        
        try:
            resposta = requests.post(FORMSPREE_URL, data=dados_envio)
            if resposta.status_code == 200:
                st.success("Obrigado! Seu feedback foi enviado direto para o desenvolvedor.")
            else:
                st.error("Não foi possível enviar o feedback. Verifique se inseriu o ID correto do Formspree.")
        except Exception as e:
            st.error(f"Erro ao conectar com o servidor: {e}")
