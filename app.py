import base64
import io
import math
import os
import struct
import wave
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from sitram import CACHE_FILE, consultar_chaves_sitram

# 1. Configuração da página Streamlit
st.set_page_config(
    page_title="LATAM Cargo | Saneamento D2D",
    page_icon="✈️",
    layout="wide",
)


# Função para tocar o som de conclusão
def tocar_som_notificacao():
    sample_rate = 44100
    audio_data = []

    for i in range(int(sample_rate * 0.15)):
        t = float(i) / sample_rate
        envelope = math.exp(-3 * t / 0.15)
        value = int(
            32767 * 0.3 * envelope * math.sin(2 * math.pi * 659.25 * t)
        )
        audio_data.append(value)

    for i in range(int(sample_rate * 0.45)):
        t = float(i) / sample_rate
        envelope = math.exp(-4 * t / 0.45)
        value = int(32767 * 0.4 * envelope * math.sin(2 * math.pi * 880.0 * t))
        audio_data.append(value)

    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for sample in audio_data:
            wav_file.writeframes(struct.pack("<h", sample))

    b64_str = base64.b64encode(wav_io.getvalue()).decode("utf-8")

    sound_html = f"""
        <audio autoplay style="display:none;">
            <source src="data:audio/wav;base64,{b64_str}" type="audio/wav">
        </audio>
    """
    components.html(sound_html, height=0, width=0)


def get_image_base64(path: str) -> str:
    if os.path.exists(path):
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    return ""


logo_b64 = get_image_base64("latam_logo.png")

# 2. Estilização CSS Personalizada
st.markdown(
    """
    <style>
        .stApp {
            background-color: #0D192B !important;
            color: #FFFFFF !important;
        }

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

# 3. Cabeçalho / Banner
logo_html = f'<img src="data:image/png;base64,{logo_b64}"><br>' if logo_b64 else ""

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

# 4. Entrada de dados
col_esquerda, col_direita = st.columns(2, gap="large")

with col_esquerda:
    st.subheader("1. Entrada de Dados")

    modo = st.radio(
        "Como você deseja importar as chaves?",
        ["Digitar / Colar Dados", "Carregar Arquivo (TXT / Excel)"],
        horizontal=True,
    )

    dados_para_consulta = []

    if modo == "Digitar / Colar Dados":
        texto_chaves = st.text_area(
            "Cole abaixo (apenas Chaves OU formato 'AWB Chave', um por linha):",
            height=250,
            placeholder="32405235  3525041733098000127550030000000001\n32475605  3525041733098000127550030000000002",
        )
        if texto_chaves:
            for linha in texto_chaves.split("\n"):
                linha_limpa = linha.strip()
                if not linha_limpa:
                    continue

                partes = [
                    p.strip()
                    for p in linha_limpa.replace("\t", " ")
                    .replace("|", " ")
                    .split()
                    if p.strip()
                ]

                if len(partes) >= 2:
                    dados_para_consulta.append(
                        {"awb": partes[0], "chave": partes[1]}
                    )
                elif len(partes) == 1:
                    dados_para_consulta.append(
                        {"awb": "N/A", "chave": partes[0]}
                    )

    else:
        arquivo = st.file_uploader(
            "Selecione um arquivo de texto (.txt) ou planilha (.xlsx / .csv):",
            type=["txt", "xlsx", "csv"],
        )
        if arquivo:
            if arquivo.name.endswith(".txt"):
                linhas = [
                    l.decode("utf-8").strip()
                    for l in arquivo.readlines()
                    if l.decode("utf-8").strip()
                ]
                for l in linhas:
                    partes = [
                        p.strip()
                        for p in l.replace("\t", " ").replace("|", " ").split()
                        if p.strip()
                    ]
                    if len(partes) >= 2:
                        dados_para_consulta.append(
                            {"awb": partes[0], "chave": partes[1]}
                        )
                    elif len(partes) == 1:
                        dados_para_consulta.append(
                            {"awb": "N/A", "chave": partes[0]}
                        )
            else:
                df_upload = (
                    pd.read_csv(arquivo, dtype=str)
                    if arquivo.name.endswith(".csv")
                    else pd.read_excel(arquivo, dtype=str)
                )
                if df_upload.shape[1] >= 2:
                    for _, row in df_upload.iterrows():
                        dados_para_consulta.append(
                            {
                                "awb": str(row.iloc[0]).strip(),
                                "chave": str(row.iloc[1]).strip(),
                            }
                        )
                else:
                    for _, row in df_upload.iterrows():
                        dados_para_consulta.append(
                            {
                                "awb": "N/A",
                                "chave": str(row.iloc[0]).strip(),
                            }
                        )

    st.write(
        f"**Total de registros identificados:** `{len(dados_para_consulta)}`"
    )
    btn_iniciar = st.button("INICIAR CONSULTA SITRAM")

with col_direita:
    st.subheader("2. Painel de Acompanhamento")

    # Lê o cache forçando tipo texto (dtype=str) para evitar erro de OverflowError no PyArrow
    df_cache = None
    if os.path.exists(CACHE_FILE):
        try:
            df_cache = pd.read_csv(CACHE_FILE, sep=";", encoding="utf-8-sig", dtype=str)
        except Exception:
            pass

    if btn_iniciar:
        if not dados_para_consulta:
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
                    f"Processando: {atual} de {total} | Ação Fiscal: {item['acao_fiscal']}"
                )

                item_com_awb = {
                    "AWB / Minuta": str(item.get("awb", "N/A")),
                    "Chave / Ação Fiscal": str(item["acao_fiscal"]),
                    "Nota Fiscal": str(item["nota"]),
                    "Situação Imposto": str(item["imposto"]),
                    "Status Final": str(item["situacao"]),
                }

                resultados_em_tempo_real.append(item_com_awb)
                df_temp = pd.DataFrame(resultados_em_tempo_real).astype(str)
                tabela_placeholder.dataframe(
                    df_temp, use_container_width=True
                )

            with st.spinner("Consultando dados na SEFAZ..."):
                consultar_chaves_sitram(
                    dados_para_consulta, callback_progresso=atualizar_interface
                )

            status_texto.empty()
            tocar_som_notificacao()
            st.success("🔔 Consulta finalizada com sucesso!")

            # Carrega resultado final tratando colunas como string
            if os.path.exists(CACHE_FILE):
                df_final = pd.read_csv(
                    CACHE_FILE, sep=";", encoding="utf-8-sig", dtype=str
                )
                st.dataframe(df_final, use_container_width=True)
                csv_data = df_final.to_csv(
                    index=False, sep=";", encoding="utf-8-sig"
                )
                st.download_button(
                    label="📥 Baixar Planilha Final (.csv)",
                    data=csv_data,
                    file_name="Relatorio_Saneamento_LATAM.csv",
                    mime="text/csv",
                )

    elif df_cache is not None and not df_cache.empty:
        # Recuperação automática de itens já processados em caso de interrupção/erro
        st.warning(
            f"⚠️ **Atenção:** Consulta anterior foi interrompida ou concluída. Foram recuperados **{len(df_cache)}** registros!"
        )
        st.dataframe(df_cache, use_container_width=True)

        csv_cache = df_cache.to_csv(index=False, sep=";", encoding="utf-8-sig")
        st.download_button(
            label=f"📥 Baixar Registros Consultados ({len(df_cache)} itens) (.csv)",
            data=csv_cache,
            file_name="Relatorio_Parcial_Saneamento_LATAM.csv",
            mime="text/csv",
        )

    else:
        st.info(
            "Aguardando início. Insira as chaves ao lado e clique em **INICIAR CONSULTA SITRAM**."
        )

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

        st.markdown(
            """
            <div class="latam-card">
                <div class="latam-card-title">💡 Dicas de Processamento D2D</div>
                <ul style="color: #CBD5E1; font-size: 14px; margin-bottom: 0; padding-left: 20px;">
                    <li>Você pode colar <b>AWB + Chave</b> juntas (copiando 2 colunas da sua planilha).</li>
                    <li>O relatório final sai com a AWB já vinculada a cada resultado!</li>
                    <li>Caso a consulta seja interrompida, <b>os itens já processados não serão perdidos</b>!</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

# --- 5. Central de Feedback (Formspree) ---
st.markdown("<br><hr>", unsafe_allow_html=True)
st.subheader("💬 Central de Erros, Dúvidas ou Sugestões")
st.write(
    "Viu algum erro nos resultados ou tem uma ideia para melhorar o sistema? Mande abaixo!"
)

FORMSPREE_ID = "mrenybwd"
FORMSPREE_URL = f"https://formspree.io/f/mrenybwd"

with st.form(key="form_feedback_formspree", clear_on_submit=True):
    nome_usuario = st.text_input("Seu nome (opcional):", placeholder="Ex: João Silva")
    tipo_mensagem = st.selectbox(
        "O que você deseja reportar?",
        ["Erro / Bug no resultado", "Sugestão de melhoria", "Outro"],
    )
    mensagem = st.text_area(
        "Descreva o erro ou sugestão em detalhes:", placeholder="Escreva aqui..."
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
                    "Não foi possível enviar o feedback. Verifique se configurou o ID do Formspree."
                )
        except Exception as e:
            st.error(f"Erro ao conectar com o servidor: {e}")
