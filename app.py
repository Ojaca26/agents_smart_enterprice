# ==========================================================
# 🧠 IANA DATACENTER - Asistente Empresarial Inteligente
# Autor: DataInsights Colombia
# Descripción:
#   Este script construye una interfaz Streamlit conectada
#   a LangGraph y Gemini, con agentes autónomos (SQL, Analista,
#   Auditor y Orquestador) sobre una base de datos MySQL modelo estrella.
# ==========================================================

import streamlit as st
from sqlalchemy import create_engine
from langchain_core.messages import HumanMessage
from graph_builder import build_langgraph, export_graph_mermaid
import time

# ==========================================================
# 🧩 CONFIGURACIÓN DE LA PÁGINA
# ==========================================================
st.set_page_config(page_title="🧠 IANA DataCenter - OML", layout="wide")

st.title("💼 IANA DataCenter - Inteligencia Empresarial OML")
st.markdown("""
Este asistente **autónomo** analiza tus datos empresariales reales 
conectados al modelo estrella OML (Fact_Ingresos, Fact_Costos, Dim_Empresa, etc.).
Usa **Gemini Pro** para interpretar, auditar y explicar resultados en lenguaje natural.
""")

# ==========================================================
# 🔐 CONEXIÓN A BASE DE DATOS
# ==========================================================
@st.cache_resource
def get_connection():
    """Crea y mantiene la conexión a MySQL."""
    creds = st.secrets["db_credentials"]
    uri = f"mysql+pymysql://{creds['user']}:{creds['password']}@{creds['host']}/{creds['database']}"
    engine = create_engine(uri, pool_pre_ping=True)
    return engine.connect()

# Intentar conectar
try:
    conn = get_connection()
    st.sidebar.success("✅ Conectado a la base de datos OML")
except Exception as e:
    st.sidebar.error(f"⚠️ Error al conectar a la BD: {e}")

# ==========================================================
# 🧱 CONSTRUCCIÓN DEL GRAFO DE AGENTES
# ==========================================================
from agents import sql_agent, analyst_agent, audit_agent, orchestrator_agent

# Construir grafo principal
if "graph" not in st.session_state:
    st.session_state.graph = build_langgraph()
    st.session_state.context = []

# ==========================================================
# 🎛️ SIDEBAR - Información de Agentes y Controles
# ==========================================================
st.sidebar.header("🧩 Agentes del Sistema")

st.sidebar.markdown("""
**1️⃣ SQLAgent:**  
Consulta 7 vistas del modelo estrella (`VIEW_Fact_Ingresos`, `VIEW_Fact_Costos`, `VIEW_Fact_Solicitudes`, etc.).

**2️⃣ AnalystAgent:**  
Calcula KPIs, márgenes, cumplimiento y tendencias.

**3️⃣ AuditAgent:**  
Detecta desviaciones o alertas en tiempos o costos.

**4️⃣ OrchestratorAgent:**  
Gerente virtual. Analiza la intención del usuario y orquesta a los demás agentes.

**5️⃣ MemoryAgent:**  
Mantiene el contexto y la conversación activa.
""")

# Botón para mostrar el diagrama LangGraph
st.sidebar.markdown("---")
if st.sidebar.button("📈 Ver flujo LangGraph"):
    with st.spinner("Generando diagrama LangGraph..."):
        graph = st.session_state.graph
        mermaid = export_graph_mermaid(graph)
        st.sidebar.markdown("### 🔍 Diagrama LangGraph")
        st.components.v1.html(f"<pre>{mermaid}</pre>", height=420)

st.sidebar.markdown("---")
st.sidebar.caption("© 2025 DataInsights Colombia - Ecosistema IANA 🤖")

# ==========================================================
# 💬 INTERFAZ DE CHAT PRINCIPAL
# ==========================================================
st.subheader("💬 Chat Empresarial con IANA DataCenter")

# Input de usuario
user_input = st.chat_input("Escribe tu pregunta sobre el negocio...")

if user_input:
    # Mostrar mensaje del usuario
    st.chat_message("user").write(user_input)

    # Recuperar grafo y orquestador
    graph = st.session_state.graph
    orchestrator = orchestrator_agent()

    with st.spinner("Analizando intención..."):
        # Enviar mensaje al agente orquestador
        orchestrator_response = orchestrator(HumanMessage(content=user_input))
        st.chat_message("assistant").write(orchestrator_response.content)
        time.sleep(0.5)

    # Decidir qué agente ejecutar (modo simple)
    texto = user_input.lower()
    if any(x in texto for x in ["facturación", "ingresos", "ventas", "costos", "solicitud", "tiempo"]):
        sql = sql_agent()
        with st.spinner("🔎 Consultando base de datos..."):
            sql_response = sql.run(user_input)
        st.chat_message("assistant").write(sql_response)

    elif any(x in texto for x in ["margen", "rentabilidad", "cumplimiento", "análisis", "tendencia"]):
        analista = analyst_agent()
        with st.spinner("📊 Analizando indicadores..."):
            analista_response = analista(user_input)
        st.chat_message("assistant").write(analista_response.content)

    elif any(x in texto for x in ["error", "alerta", "riesgo", "desviación", "problema"]):
        auditor = audit_agent()
        with st.spinner("🔍 Revisando posibles alertas..."):
            audit_response = auditor(user_input)
        st.chat_message("assistant").write(audit_response.content)

    else:
        st.chat_message("assistant").write("🤖 No estoy seguro, pero puedo ayudarte a revisar el negocio completo si me indicas un área (Facturación, Costos, Rentabilidad, etc.).")

# ==========================================================
# 🧭 NOTA FINAL DE USO
# ==========================================================
st.markdown("""
---
**💡 Tip:**  
Puedes hacer preguntas como:
- *“¿Cuál fue el margen bruto de octubre?”*  
- *“Muéstrame los costos por empresa y su cumplimiento.”*  
- *“Detecta desviaciones en los tiempos de ejecución.”*  
""")
