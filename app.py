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
    st.markdown("# 🤖 IANA DataCenter\n### Red de Agentes Inteligentes Empresariales")

# (Aquí puedes poner tu descripción de IANA...)

# ==========================================================
# 🧠 CONSTRUCCIÓN DE LA RED DE AGENTES (Una sola vez)
# ==========================================================
# Usamos cache_resource para no reconstruir el grafo en cada re-run
@st.cache_resource
def get_graph():
    return build_langgraph()

graph = get_graph()

# ==========================================================
# 🎛️ SIDEBAR (Sin cambios)
# ==========================================================
st.sidebar.header("🧩 Agentes Inteligentes de IANA")
# (Tu sidebar markdown aquí...)
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

# (La función transcribir_audio_bytes va aquí, sin cambios)
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
    
    # 1. Añadir mensaje del usuario al historial
    # Nota: el historial de st.session_state ahora solo se usa para MOSTRAR
    # El estado real del chat vive dentro del grafo (AgentState)
    if "messages" not in st.session_state:
        st.session_state.messages = []
        
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Reconstruir el historial para el grafo
    # El grafo necesita objetos HumanMessage/AIMessage
    graph_history = []
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            graph_history.append(HumanMessage(content=msg["content"]))
        else:
            graph_history.append(AIMessage(content=msg["content"]))

    # Definir la entrada para el grafo
    graph_input = {
        "messages": [HumanMessage(content=prompt)] # Solo pasamos el último mensaje
        # Si quisieras memoria, pasarías todo 'graph_history'
    }

    # 2. Abrir el contenedor del asistente y el expander
    with st.chat_message("assistant"):
        final_response = ""
        
        with st.expander("⚙️ Ver Proceso de IANA", expanded=True):
            # Usamos un placeholder para ir añadiendo los logs del stream
            log_placeholder = st.empty()
            log_messages = []
            
            try:
                # --- ¡AQUÍ OCURRE LA MAGIA! ---
                # Usamos graph.stream()
                events = graph.stream(graph_input, stream_mode="values")
                
                for event in events:
                    # event es el 'AgentState' completo en cada paso
                    # Vamos a mostrar qué nodo se acaba de ejecutar
                    
                    # (Esta es una forma simple de detectar el último nodo ejecutado)
                    # Una forma más robusta es usar `stream_mode="updates"`
                    # Pero esta es más fácil de entender:
                    
                    if "next_agent" in event and not any("Orchestrator" in m for m in log_messages):
                         log_messages.append(f"🤖 **Orchestrator Agent:** Decidió ruta -> {event['next_agent']}")
                         log_placeholder.markdown("\n\n".join(log_messages))

                    if event.get("sql_data") and not any("SQL Agent" in m for m in log_messages):
                        log_messages.append("🧩 **SQL Agent:** Datos extraídos de la base de datos.")
                        log_placeholder.markdown("\n\n".join(log_messages))

                    # El evento final tendrá el último mensaje
                    if event["messages"][-1].role == "ai":
                        final_response = event["messages"][-1].content
                        
            except Exception as e:
                st.error(f"❌ Ha ocurrido un error en la red de agentes: {e}")
                final_response = "Lo siento, tuve un problema al procesar tu solicitud."

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
    with col1:
        voice_text = speech_to_text(language=lang, start_prompt="🎙️ Hablar", stop_prompt="🛑 Grabando...", use_container_width=True, just_once=True, key="stt")
    with col2:
        prompt_text = st.chat_input("... o escribe tu pregunta aquí")

prompt_a_procesar = None
if voice_text:
    prompt_a_procesar = voice_text
elif prompt_text:
    prompt_a_procesar = prompt_text

if prompt_a_procesar:
    procesar_pregunta(prompt_a_procesar)
