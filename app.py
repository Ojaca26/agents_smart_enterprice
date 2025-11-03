import streamlit as st
from graph_builder import build_langgraph, export_graph_mermaid
from langchain_core.messages import HumanMessage
from langgraph.graph import Graph
import time

# ========================================
# CONFIGURACIÓN DE LA PÁGINA
# ========================================
st.set_page_config(page_title="🧠 IANA DataCenter OML", layout="wide")

st.title("💼 IANA DataCenter - Inteligencia Empresarial OML")
st.markdown("Asistente gerencial autónomo conectado al modelo estrella de tu base OML.")

# ========================================
# SIDEBAR - INFO DE AGENTES
# ========================================
st.sidebar.header("🧩 Agentes del Sistema")
st.sidebar.markdown("""
**1️⃣ SQLAgent:** Conecta y consulta 7 vistas del modelo estrella.  
**2️⃣ AnalystAgent:** Calcula KPIs, rentabilidad, tiempos y metas.  
**3️⃣ AuditAgent:** Detecta alertas o desviaciones.  
**4️⃣ OrchestratorAgent:** Entiende la intención y coordina el flujo.  
**5️⃣ MemoryAgent:** Guarda el contexto y la conversación.
""")

# Botón para mostrar diagrama Mermaid
if st.sidebar.button("📈 Ver flujo LangGraph"):
    graph = build_langgraph()
    mermaid = export_graph_mermaid(graph)
    st.sidebar.markdown("### 🔍 Diagrama LangGraph")
    st.components.v1.html(f"<pre>{mermaid}</pre>", height=400)

# ========================================
# CHAT PRINCIPAL
# ========================================
user_input = st.chat_input("Escribe tu pregunta sobre el negocio...")

if "graph" not in st.session_state:
    st.session_state.graph = build_langgraph()
    st.session_state.context = []

if user_input:
    st.chat_message("user").write(user_input)
    graph = st.session_state.graph
    orchestrator = graph.get_node("orchestrator")
    response = orchestrator.invoke(HumanMessage(content=user_input))
    st.chat_message("assistant").write(response)
