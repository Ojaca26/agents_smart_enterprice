# ==========================================================
# 🤖 IANA DataCenter - Red de Agentes Inteligentes Empresariales
# Autor: DataInsights Colombia
# Descripción:
#   Demostrador del concepto IANA: ecosistema de agentes AI autónomos
#   para empresas, con analítica, auditoría y orquestación.
# ==========================================================

import streamlit as st
from langchain_core.messages import HumanMessage
from graph_builder import build_langgraph
from agents import AgentState # Importamos el estado
from typing import Optional
import io
import time

# Importar librerías de voz
try:
    from streamlit_mic_recorder import speech_to_text
    import speech_recognition as sr
except ImportError:
    st.error("Faltan librerías de voz. Ejecuta: pip install streamlit-mic-recorder SpeechRecognition")
    st.stop()

# ==========================================================
# 🧩 CONFIGURACIÓN DE LA PÁGINA
# ==========================================================
st.set_page_config(page_title="IANA - Red de Agentes Inteligentes", page_icon="logo.png", layout="wide")
col1, col2 = st.columns([1, 8])
with col1:
    st.image("logo.png", width=100)
with col2:
    st.markdown("""
    # 🤖 IANA DataCenter
    ### Red de Agentes Inteligentes Empresariales
    """)

st.markdown("""
IANA es una red de **agentes autónomos** desarrollada por **DataInsights Colombia**, 
diseñada para **analizar datos reales, detectar oportunidades y asistir en decisiones ejecutivas** con lenguaje natural y pensamiento analítico.
""")


# ==========================================================
# 🔐 CONEXIÓN A BASE DE DATOS (Opcional, para el sidebar)
# ==========================================================
# @st.cache_resource
# def get_connection_status():
#     """Revisa el estado de la conexión a la base de datos."""
#     try:
#         creds = st.secrets["db_credentials"]
#         uri = f"mysql+pymysql://{creds['user']}:{creds['password']}@{creds['host']}/{creds['database']}"
#         engine = create_engine(uri, pool_pre_ping=True)
#         conn = engine.connect()
#         conn.close()
#         return True
#     except Exception:
#         return False

# if get_connection_status():
#     st.sidebar.success("✅ Conectado a la base de datos DataInsights")
# else:
#     st.sidebar.warning("⚠️ Modo demostración (sin conexión real a base de datos)")


# ==========================================================
# 🧠 CONSTRUCCIÓN DE LA RED DE AGENTES (Una sola vez)
# ==========================================================
@st.cache_resource
def get_graph():
    """Construye y cachea el grafo LangGraph compilado."""
    return build_langgraph()

graph = get_graph()

# ==========================================================
# 🎛️ SIDEBAR
# ==========================================================
st.sidebar.header("🧩 Agentes Inteligentes de IANA")
st.sidebar.markdown("""
**💼 OrchestratorAgent** Gerente virtual. Analiza la intención y enruta al agente correcto.

**📊 AnalystAgent** Interpreta métricas, márgenes, tendencias y genera insights.

**🧩 SQLAgent** Consulta los datos estructurados en las fuentes empresariales.

**🔍 AuditAgent** Detecta anomalías, alertas o desviaciones en los indicadores.

**💬 ConversationalAgent** Maneja saludos y conversación general.
""")
st.sidebar.markdown("---")
st.sidebar.caption("© 2025 DataInsights Colombia — Ecosistema IANA 🤖")


# ==========================================================
# 🎤 LÓGICA DE VOZ (de autollantas.py)
# ==========================================================
@st.cache_resource
def get_recognizer():
    r = sr.Recognizer()
    r.energy_threshold = 300
    r.dynamic_energy_threshold = True
    return r

def transcribir_audio_bytes(data_bytes: bytes, language: str) -> Optional[str]:
    try:
        r = get_recognizer()
        with sr.AudioFile(io.BytesIO(data_bytes)) as source:
            audio = r.record(source)
        texto = r.recognize_google(audio, language=language)
        return texto.strip() if texto else None
    except Exception:
        return None

# ==========================================================
# 💬 LÓGICA DE CHAT CON GRAPH.STREAM()
# ==========================================================

def procesar_pregunta(prompt: str):
    """
    Función principal que procesa la pregunta usando graph.stream()
    y muestra el progreso en el expander.
    """
    
    # 1. Añadir mensaje del usuario al historial de Streamlit
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Reconstruir el historial para el grafo
    graph_history = []
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            graph_history.append(HumanMessage(content=msg["content"]))
        else:
            graph_history.append(AIMessage(content=msg["content"]))

    # Definir la entrada para el grafo
    graph_input = {
        "messages": graph_history # Pasamos todo el historial
    }

    # 2. Abrir el contenedor del asistente y el expander
    with st.chat_message("assistant"):
        final_response = ""
        
        with st.expander("⚙️ Ver Proceso de IANA", expanded=True):
            # Usamos un placeholder para ir añadiendo los logs del stream
            # Usar st.info, st.success, etc. aquí dentro funciona bien
            
            try:
                # --- ¡AQUÍ OCURRE LA MAGIA! ---
                # Usamos graph.stream() para obtener los eventos
                # Usamos 'updates' para obtener solo el CAMBIO en cada paso
                events = graph.stream(graph_input, stream_mode="updates")
                
                for event in events:
                    # 'event' es un dict que dice qué nodo se ejecutó
                    # y cuál es su salida.
                    node_name, node_output = next(iter(event.items()))
                    
                    if node_name == "orchestrator" and node_output.get("next_agent"):
                        st.success(f"🤖 **Orquestador:** Ruta decidida -> `{node_output['next_agent']}`")
                    elif node_name == "sql_data_getter":
                        st.info("🧩 **SQL Agent:** Datos extraídos.")
                    elif node_name == "sql_final_agent" and node_output.get("messages"):
                        st.success("🧩 **SQL Agent:** Consulta finalizada.")
                        final_response = node_output["messages"][-1].content
                    elif node_name == "analyst_agent" and node_output.get("messages"):
                        st.success("📊 **Analista:** Análisis completado.")
                        final_response = node_output["messages"][-1].content
                    elif node_name == "audit_agent" and node_output.get("messages"):
                        st.success("🔍 **Auditor:** Auditoría completada.")
                        final_response = node_output["messages"][-1].content
                    elif node_name == "conversational_agent" and node_output.get("messages"):
                        st.success("💬 **Conversacional:** Respuesta generada.")
                        final_response = node_output["messages"][-1].content
                
                if not final_response:
                    # Esto pasa si el grafo termina sin una respuesta (ej. un error)
                    final_response = "Lo siento, no pude procesar esa solicitud."
                    st.error("Error en el flujo del grafo.")

            except Exception as e:
                st.error(f"❌ Ha ocurrido un error en la red de agentes: {e}")
                final_response = f"Lo siento, tuve un problema al procesar tu solicitud: {e}"

        # 3. Mostrar la respuesta final fuera del expander
        st.markdown(final_response)
        
        # 4. Guardar respuesta final en el historial de Streamlit
        st.session_state.messages.append({"role": "assistant", "content": final_response})

# --- Inicialización del historial de chat de Streamlit ---
if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "assistant", 
        "content": "¡Hola! Soy IANA. ¿Qué deseas analizar hoy?"
    }]

# --- Mostrar historial de chat ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ==========================================================
# 💬 INTERFAZ DE ENTRADA (Voz y Texto de autollantas.py)
# ==========================================================
st.subheader("💬 Habla con IANA o escribe tu pregunta")
lang = st.secrets.get("stt_language", "es-CO") # Lenguaje para la voz

input_container = st.container()
with input_container:
    col1, col2 = st.columns([1, 4])
    
    # Columna 1: Botón de Voz
    with col1:
        voice_text = speech_to_text(
            language=lang,
            start_prompt="🎙️ Hablar",
            stop_prompt="🛑 Grabando...",
            use_container_width=True,
            just_once=True,
            key="stt"
        )
    
    # Columna 2: Entrada de Texto
    with col2:
        prompt_text = st.chat_input("... o escribe tu pregunta aquí")

# --- Lógica para procesar la entrada (sea voz o texto) ---
prompt_a_procesar = None
if voice_text:
    prompt_a_procesar = voice_text
elif prompt_text:
    prompt_a_procesar = prompt_text

# Si tenemos una entrada (de voz o texto), la procesamos
if prompt_a_procesar:
    procesar_pregunta(prompt_a_procesar)
