# app.py
import streamlit as st
from graph_sql import run_graph

st.set_page_config(page_title="IANA SQL Multi-Agente", layout="wide")

# Inicializar historial de chat
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "¡Hola! Soy IANA, tu asistente de BI de Ventus. ¿Qué deseas saber sobre nuestros ingresos, costos o solicitudes de servicio?"}]

# Título Principal y Bienvenida
st.title("🧠 IANA SQL – Agente multi-tabla (LangGraph)")
st.caption("Estructura de consultas:")
st.markdown(
    """
* *"Dame los ingresos totales por año"*
* *"Costo promedio por empresa en 2024"*
* *"Tiempo promedio de espera por ubicación"*
"""
)
st.divider()

# Mostrar mensajes históricos
for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar="🤖" if message["role"] == "assistant" else "👤"):
        st.markdown(message["content"])

# Contenedor para el chat y entrada de audio/texto
col1, col2 = st.columns([1, 8], gap="small")

with col1:
    # Simulación del botón de audio
    if st.button("🎤 Hablar", use_container_width=True, help="Función de voz/audio no implementada"):
        st.info("Función de voz/audio no implementada en este prototipo.")

with col2:
    # Entrada de chat principal
    question = st.chat_input("Escribe tu pregunta de negocio...")

# Procesa la nueva pregunta
if question:
    # 1. Mostrar la pregunta del usuario
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user", avatar="👤"):
        st.markdown(question)

    # 2. Generar la respuesta del Agente
    with st.spinner("Analizando con agentes IA..."):
        state = run_graph(question.strip())

    # 3. Mostrar la respuesta del Agente
    route = state.get("route", "desconocida")
    sql_query = state.get("sql_query", "")
    result = state.get("result", {})
    
    with st.chat_message("assistant", avatar="🤖"):
        
        # Mostrar Debug (Ruta y SQL)
        with st.expander("Detalles de la Consulta (Debug)", expanded=False):
            st.markdown(f"**Ruta Detectada:** `{route}`")
            st.subheader("SQL generado")
            st.code(sql_query, language="sql")

        # Manejo de la Respuesta Final
        if isinstance(result, dict) and result.get("type") == "error":
            answer = result.get("message", "Ocurrió un error en el flujo de agentes.")
            st.error(answer)
        
        elif isinstance(result, dict) and result.get("type") in ("ok", "chat"):
            answer = result.get("answer", "No se pudo generar una respuesta.")
            st.markdown(answer)
        
        else:
            answer = "No se obtuvo resultado interpretable."
            st.info(answer)
        
        # 4. Guardar la respuesta en el historial
        st.session_state.messages.append({"role": "assistant", "content": answer})
