import streamlit as st
from sqlalchemy import create_engine, text
from langchain_community.utilities import SQLDatabase
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import Tool
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate

# ============================================================
# 1. PROMPT MAESTRO — LIMPIO (SIN chat_history, SIN scratchpad)
# ============================================================
PROMPT = """
Eres un Agente SQL profesional encargado de responder cualquier pregunta del usuario
usando ÚNICAMENTE las siguientes tablas de MariaDB:

- replica_VIEW_Fact_Ingresos
- replica_VIEW_Fact_Costos
- replica_VIEW_Fact_Solicitudes
- replica_VIEW_Dim_Empresa
- replica_VIEW_Dim_Concepto
- replica_VIEW_Dim_Usuario
- replica_VIEW_Dim_Ubicacion

REGLAS OBLIGATORIAS:
1. Tu PRIMERA acción siempre debe ser generar una QUERY SQL válida.
2. NO puedes responder sin antes generar SQL.
3. Incluso si no existen datos, IGUAL debes generar SQL.
4. No puedes inventar columnas ni tablas.
5. Usa JOIN correctos entre FACT y DIM.
6. Tu respuesta final debe traer:
   - SQL_GENERADA
   - INTERPRETACIÓN EN ESPAÑOL
7. Prohibido decir "No sé" o "I don’t know".
"""

# ============================================================
# 2. UI DE STREAMLIT
# ============================================================
st.set_page_config(page_title="IANA SQL – Gemini 1.5 PRO", page_icon="🤖")
st.title("🤖 IANA SQL Universal – Gemini 1.5 PRO (100% Real SQL)")
st.caption("Consultas SQL reales usando Gemini en modo Tool-Calling estable.")

# ============================================================
# 3. CONEXIÓN A MARIADB
# ============================================================
engine = create_engine(
    f"mysql+pymysql://{st.secrets['db_credentials']['DB_USER']}:"
    f"{st.secrets['db_credentials']['DB_PASS']}@"
    f"{st.secrets['db_credentials']['DB_HOST']}/"
    f"{st.secrets['db_credentials']['DB_NAME']}"
)

db = SQLDatabase(engine)

# ============================================================
# 4. DEFINIR LA HERRAMIENTA SQL
# ============================================================
def run_query(sql: str):
    """Ejecuta una query SQL sobre MariaDB."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = result.fetchall()
            return str(rows)
    except Exception as e:
        return f"Error ejecutando SQL: {e}"

sql_tool = Tool(
    name="sql_executor",
    description="Ejecuta SQL sobre MariaDB.",
    func=run_query
)

# ============================================================
# 5. MODELO GEMINI 1.5 PRO (EL ÚNICO QUE FUNCIONA CON TOOLS)
# ============================================================
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-pro",
    temperature=0,
    max_output_tokens=2048
)

prompt = ChatPromptTemplate.from_messages([
    ("system", PROMPT),
    ("human", "{input}")
])

# Agente compatible con tool-calling
agent = create_openai_tools_agent(
    llm=llm,
    tools=[sql_tool],
    prompt=prompt
)

executor = AgentExecutor(
    agent=agent,
    tools=[sql_tool],
    verbose=True
)

# ============================================================
# 6. INPUT DEL USUARIO
# ============================================================
consulta = st.text_input("Haz tu pregunta:", "")

if consulta:
    st.write("⏳ Analizando...")

    try:
        result = executor.invoke({"input": consulta})
        st.success("✔ Hecho")

        # -------------------------------------------
        # EXTRAER SQL
        # -------------------------------------------
        st.subheader("📌 SQL Generada")

        sql_generada = None
        for step in result.get("intermediate_steps", []):
            action, output = step
            if hasattr(action, "tool_input"):
                sql_generada = action.tool_input

        if sql_generada:
            st.code(sql_generada, language="sql")
        else:
            st.warning("⚠ No se pudo extraer la SQL generada.")

        # -------------------------------------------
        # RESPUESTA FINAL
        # -------------------------------------------
        st.subheader("📘 Respuesta")
        st.write(result.get("output", "No hubo respuesta."))

    except Exception as e:
        st.error(f"❌ Error ejecutando agente: {e}")
