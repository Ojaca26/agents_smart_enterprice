# app.py (FINAL)
import streamlit as st
from graph_sql import run_graph

st.set_page_config(page_title="IANA SQL Multi-Agente", layout="centered")

st.title("🧠 IANA SQL – Agente multi-tabla (LangGraph)")

st.markdown(
    """
Formula preguntas del tipo:

- *"Dame los ingresos totales por año"*
- *"Costo promedio por empresa en 2024"*
- *"Tiempo promedio de espera por ubicación"*
"""
)

question = st.text_area("Escribe tu pregunta de negocio", height=100)

if st.button("Preguntar", type="primary") and question.strip():
    with st.spinner("Analizando con agentes IA..."):
        state = run_graph(question.strip())

    st.subheader("Ruta detectada")
    st.write(state.get("route", "desconocida"))

    st.subheader("SQL generado")
    st.code(state.get("sql_query", ""), language="sql")

    result = state.get("result", {})
    error = state.get("error", "")

    # Manejo de la Respuesta Final
    if isinstance(result, dict) and result.get("type") == "error":
        st.error(result.get("message", "Ocurrió un error en el flujo de agentes."))
    
    elif isinstance(result, dict) and result.get("type") in ("ok", "chat"):
        st.subheader("✅ Respuesta del Analista")
        # Mostramos la respuesta generada en Markdown, que ya incluye el resumen y la tabla
        st.markdown(result.get("answer", ""))
    
    else:
        # Fallback para errores no categorizados
        if error:
            st.error(f"Error desconocido: {error}")
        else:
            st.info("No se obtuvo resultado interpretable.")
