import streamlit as st
from sqlalchemy import create_engine, text
from langchain_community.utilities import SQLDatabase
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import Tool
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import ChatPromptTemplate

# ============================================================
# 1. PROMPT (SENCILLO + COMPATIBLE CON REACT AGENT)
# ============================================================
PROMPT = """
Eres un agente profesional de SQL.
Tu tarea es responder la pregunta del usuario utilizando ÚNICAMENTE estas tablas:

- replica_VIEW_Fact_Ingresos
- replica_VIEW_Fact_Costos
- replica_VIEW_Fact_Solicitudes
- replica_VIEW_Dim_Empresa
- replica_VIEW_Dim_Concepto
- replica_VIEW_Dim_Usuario
- replica_VIEW_Dim_Ubicacion

REGLAS:
1. Tu primer paso SIEMPRE debe ser generar SQL.
2. La SQL NO puede inventar columnas ni tablas.
3. Usa JOIN correctos entre FACT y DIM.
4. Si no hay datos, igual debes generar SQL.
5. Después de ejecutar la SQL, interpreta los resultados en español.
"""

# ============================================================
# 2. STREAMLIT CONFIG
# ============================================================
st.set_page_config(page_title="IANA SQL – Gemini 1.5 PRO", page_icon="🤖")
st.title("🤖 IANA SQL Universal – Gemini 1.5 PRO (React Agent)")
st.caption("Agente SQL totalmente compatible con Gemini 1.5 PRO")

# ============================================================
# 3. CONEXIÓN MARIADB
# ============================================================
engine = create_engine(
    f"mysql+pymysql://{st.secrets['db_credentials']['DB_USER']}:"
    f"{st.secrets['db_credentials']['DB_PASS']}@"
    f"{st.secrets['db_credentials']['DB_HOST']}/"
    f"{st.secrets['db_credentials']['DB_NAME']}"
)

db = SQLDatabase(engine)

# ============================================================
# 4. HERRAMIENTA SQL
# ============================================================
def run_query(sql: str):
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = result.fetchall()
            return str(rows)
    except Exception as e:
        return f"Error ejecutando SQL: {e}"

sql_tool = Tool(
    name="sql_executor",
    func=run_query,
    description="Ejecuta SQL sobre MariaDB."
)

# ============================================================
# 5. CONFIGURAR GEMINI 1.5 PRO
# ============================================================
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-pro",
    temperature=0
)

# ============================================================
# 6. AGENTE REACT COMPATIBLE CON GEMINI
# ============================================================
prompt = ChatPromptTemplate.from_messages([
    ("system", PROMPT),
    ("human", "{input}")
])

agent = create_react_agent(
    llm=llm,
    tools=[sql_tool],
    prompt=prompt
)

executor = AgentExecutor(agent=agent, tools=[sql_tool], verbose=True)

# ============================================================
# 7. UI
# ============================================================
consulta = st.text_input("Haz tu pregunta:", "")

if consulta:
    st.write("⏳ Analizando...")

    try:
        result = executor.invoke({"input": consulta})
        st.success("✔ Hecho")

        # EXTRAER SQL
        st.subheader("📌 SQL Generada")
        sql_generada = None

        for step in result.get("intermediate_steps", []):
            action, output = step
            if hasattr(action, "tool_input"):
                sql_generada = action.tool_input

        if sql_generada:
            st.code(sql_generada, language="sql")
        else:
            st.warning("⚠ No se pudo extraer SQL.")

        # RESPUESTA
        st.subheader("📘 Respuesta")
        st.write(result["output"])

    except Exception as e:
        st.error(f"❌ Error ejecutando agente: {e}")

