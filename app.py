import streamlit as st
from langgraph.graph import Graph, StateGraph
from langgraph.prebuilt import ToolNode
from langchain_google_genai import ChatGoogleGenerativeAI
from sqlalchemy import create_engine, text
import pandas as pd
import tempfile
import base64

# ======================================================
# 🔐 CREDENCIALES SEGURAS DESDE STREAMLIT SECRETS
# ======================================================
creds = st.secrets["db_credentials"]
uri = f"mysql+pymysql://{creds['user']}:{creds['password']}@{creds['host']}/{creds['database']}"
api_key = st.secrets["gemini_api_key"]

# ======================================================
# ⚙️ CONFIGURACIÓN DEL MODELO GEMINI PRO
# ======================================================
llm = ChatGoogleGenerativeAI(model="gemini-pro-latest", google_api_key=api_key)

# ======================================================
# 🧩 CONEXIÓN A BASE DE DATOS
# ======================================================
def run_query(sql):
    """Ejecuta consultas SQL seguras."""
    engine = create_engine(uri)
    with engine.connect() as conn:
        result = pd.read_sql(text(sql), conn)
    return result

# ======================================================
# 🤖 CLASE BASE DE AGENTES
# ======================================================
class Agent:
    def __init__(self, name):
        self.name = name

    def respond(self, query, context=None):
        return f"[{self.name}] recibió: {query}"

# ------------------------------------------------------
# AGENTES DEL DATA CENTER
# ------------------------------------------------------
class SQLAgent(Agent):
    def respond(self, query, context=None):
        try:
            df = run_query(query)
            return df.to_markdown()
        except Exception as e:
            return f"❌ Error SQL: {e}"

class AnalystAgent(Agent):
    def respond(self, query, context=None):
        prompt = f"Eres un analista experto. Responde con claridad: {query}"
        return llm.invoke(prompt).content

class AuditorAgent(Agent):
    def respond(self, query, context=None):
        prompt = f"Eres un auditor de operaciones. Evalúa desempeño según reglas y metas: {query}"
        return llm.invoke(prompt).content

class DashAgent(Agent):
    def respond(self, query, context=None):
        prompt = f"Actúa como un dashboard narrativo. Resume métricas y KPIs: {query}"
        return llm.invoke(prompt).content

# ------------------------------------------------------
# AGENTE ORQUESTADOR (MANAGER)
# ------------------------------------------------------
class ManagerAgent(Agent):
    def __init__(self):
        super().__init__("ManagerAgent")
        self.sql = SQLAgent("SQLAgent")
        self.analyst = AnalystAgent("AnalystAgent")
        self.auditor = AuditorAgent("AuditorAgent")
        self.dash = DashAgent("DashAgent")

    def respond(self, query):
        """Decide qué agente manejará la solicitud."""
        query_lower = query.lower()
        if any(k in query_lower for k in ["ingreso", "costo", "solicitud", "empresa", "ubicación"]):
            return self.sql.respond(query)
        elif "tendencia" in query_lower or "rentabilidad" in query_lower:
            return self.analyst.respond(query)
        elif "meta" in query_lower or "cumplimiento" in query_lower:
            return self.auditor.respond(query)
        elif "resumen" in query_lower or "kpi" in query_lower:
            return self.dash.respond(query)
        else:
            # Si no está claro, lo consulta al LLM para decidir
            prompt = f"Eres el ManagerAgent, decide a qué agente enviar esto: {query}"
            decision = llm.invoke(prompt).content
            return f"🤖 Orquestador decidió: {decision}"

# ======================================================
# 🌐 INTERFAZ STREAMLIT
# ======================================================
st.set_page_config(page_title="Centro de Inteligencia Empresarial", page_icon="🤖", layout="wide")

# SIDEBAR
st.sidebar.title("🧠 Centro de Agentes Inteligentes")
st.sidebar.markdown("---")
st.sidebar.subheader("Resumen de Agentes")
st.sidebar.markdown("""
**🧮 SQLAgent:** Consulta 7 vistas del modelo estrella (ingresos, costos, solicitudes...).  
**📊 AnalystAgent:** Calcula rentabilidad, márgenes, tendencias.  
**🧾 AuditorAgent:** Evalúa metas y cumplimiento operativo.  
**📈 DashAgent:** Resume KPIs y genera reportes ejecutivos.  
**🤖 ManagerAgent:** Orquesta todo el flujo y mantiene el contexto.  
**🧩 DataCenterAgent:** Fuente de datos en MySQL real.  
""")

st.sidebar.info("💡 Consejo: Puedes preguntar '¿Cuál fue la rentabilidad promedio del mes pasado por cliente?'")

# ======================================================
# 📈 DIAGRAMA MERMAID
# ======================================================
diagram = """
```mermaid
graph TD
    A[🧑 Cliente (Chat)] --> B[🤖 ManagerAgent]
    B --> C[🧮 SQLAgent]
    B --> D[📊 AnalystAgent]
    B --> E[🧾 AuditorAgent]
    B --> F[📈 DashAgent]
    C --> G[(🧩 DataCenter MySQL)]
    F --> B