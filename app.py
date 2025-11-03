# ==========================================================
# 🤖 IANA DataCenter - Red de Agentes Inteligentes Empresariales
# Autor: DataInsights Colombia
# Descripción:
#   Demostrador del concepto IANA: ecosistema de agentes AI autónomos
#   para empresas, con analítica, auditoría y orquestación.
# ==========================================================

import streamlit as st
from sqlalchemy import create_engine
from langchain_core.messages import HumanMessage
from graph_builder import build_langgraph, export_graph_mermaid
import time

# ==========================================================
# 🧩 CONFIGURACIÓN DE LA PÁGINA
# ==========================================================
st.set_page_config(page_title="🤖 IANA - Red de Agentes Inteligentes", layout="wide")

# --- Logo y encabezado principal ---
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
diseñada para **analizar datos reales, detectar oportunidades y asistir en decisiones ejecutivas** 
con lenguaje natural y pensamiento analítico.

Cada agente tiene un rol específico —como analista, auditor o gerente virtual— y 
trabajan en conjunto bajo un **modelo orquestado** que refleja la estructura de una empresa moderna.
""")

# ==========================================================
# 🔐 CONEXIÓN A BASE DE DATOS (Simulada / Real)
# ==========================================================
@st.cache_resource
def get_connection():
    """Crea y mantiene la conexión a la base de datos (si aplica)."""
    creds = st.secrets["db_credentials"]
    uri = f"mysql+pymysql://{creds['user']}:{creds['password']}@{creds['host']}/{creds['database']}"
    engine = create_engine(uri, pool_pre_ping=True)
    return engine.connect()

try:
    conn = get_connection()
    st.sidebar.success("✅ Conectado a la base de datos DataInsights")
except Exception:
    st.sidebar.warning("⚠️ Modo demostración (sin conexión real a base de datos)")

# ==========================================================
# 🧠 CONSTRUCCIÓN DE LA RED DE AGENTES
# ==========================================================
from agents import sql_agent, analyst_agent, audit_agent, orchestrator_agent

if "graph" not in st.session_state:
    st.session_state.graph = build_langgraph()
    st.session_state.context = []

# ==========================================================
# 🎛️ SIDEBAR - Información General
# ==========================================================
st.sidebar.header("🧩 Agentes Inteligentes de IANA")

st.sidebar.markdown("""
**💼 OrchestratorAgent**  
Gerente virtual. Analiza la intención del usuario y orquesta a los demás agentes.

**📊 AnalystAgent**  
Interpreta métricas, márgenes, tendencias y genera insights ejecutivos.

**🧩 SQLAgent**  
Consulta los datos estructurados en las fuentes empresariales o Data Warehouse.

**🔍 AuditAgent**  
Detecta anomalías, alertas o desviaciones en los indicadores.

**🧠 MemoryAgent**  
Mantiene el contexto y la conversación activa.
""")

st.sidebar.markdown("---")
if st.sidebar.button("📈 Ver flujo LangGraph"):
    with st.spinner("Generando visualización de la red de agentes..."):
        graph = st.session_state.graph
        export_graph_mermaid(graph)
    st.sidebar.subheader("📊 Diagrama LangGraph")

st.sidebar.markdown("---")
st.sidebar.caption("© 2025 DataInsights Colombia — Ecosistema IANA 🤖")

# ==========================================================
# 💬 INTERFAZ DE CHAT DEMOSTRATIVA
# ==========================================================
st.subheader("💬 Interfaz de Conversación con IANA")

user_input = st.chat_input("Escribe una pregunta o escenario de negocio...")

if user_input:
    st.chat_message("user").write(user_input)

    orchestrator = orchestrator_agent()

    with st.spinner("Analizando intención y orquestando agentes..."):
        orchestrator_response = orchestrator(HumanMessage(content=user_input))
        st.chat_message("assistant").write(orchestrator_response.content)
        time.sleep(0.5)

    texto = user_input.lower()

    if any(x in texto for x in ["ingreso", "factura", "venta", "costo", "pedido"]):
        sql = sql_agent()
        with st.spinner("🔎 Consultando datos..."):
            sql_response = sql.run(user_input)
        st.chat_message("assistant").write(sql_response)

    elif any(x in texto for x in ["margen", "rentabilidad", "cumplimiento", "tendencia"]):
        analista = analyst_agent()
        with st.spinner("📊 Analizando indicadores..."):
            analista_response = analista(user_input)
        st.chat_message("assistant").write(analista_response.content)

    elif any(x in texto for x in ["alerta", "riesgo", "desviación", "problema", "auditoría"]):
        auditor = audit_agent()
        with st.spinner("🔍 Auditando desempeño..."):
            audit_response = auditor(user_input)
        st.chat_message("assistant").write(audit_response.content)

    else:
        st.chat_message("assistant").write("🤖 Puedo ayudarte a revisar ventas, costos, márgenes o riesgos. ¿Qué deseas analizar?")

# ==========================================================
# 🧭 NOTA FINAL
# ==========================================================
st.markdown("""
---
**💡 Demostración Conceptual IANA:**  
Este entorno representa cómo múltiples agentes de IA trabajan juntos en la nube para asistir a equipos ejecutivos.  
El sistema puede conectarse a fuentes reales de datos, generar reportes, responder consultas o ejecutar auditorías inteligentes.
""")
