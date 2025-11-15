import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_google_genai import ChatGoogleGenerativeAI

# ========================================================
# 🚀 PROMPT MAESTRO – IANA SQL UNIVERSAL
# ========================================================
PROMPT = """
Eres un Agente SQL experto encargado de responder cualquier pregunta del usuario
usando ÚNICAMENTE las tablas disponibles en la base de datos.

TABLAS DISPONIBLES (usas solo estas):
- replica_VIEW_Fact_Ingresos
- replica_VIEW_Fact_Costos
- replica_VIEW_Fact_Solicitudes
- replica_VIEW_Dim_Empresa
- replica_VIEW_Dim_Concepto
- replica_VIEW_Dim_Usuario
- replica_VIEW_Dim_Ubicacion

REGLAS OBLIGATORIAS:
1. Tu PRIMERA acción SIEMPRE debe ser generar una QUERY SQL válida.
2. AUN SI NO EXISTEN DATOS, IGUAL debes generar SQL.
3. Está prohibido responder "No sé" o "I don't know".
4. Valida que los nombres de columnas existan realmente.
5. Usa JOINs correctos entre FACT y DIM.
6. Devuelve SIEMPRE:
   SQL_QUERY: (la consulta exacta)
   RESULT: (la interpretación en español)
7. Si la pregunta es ambigua, asume la interpretación más lógica.
8. Si la pregunta no requiere SQL, aún así genera SQL que apoye tu respuesta.
"""

# ========================================================
# 🎨 CONFIG STREAMLIT
# ========================================================
st.set_page_config(
    page_title="IANA SQL Universal",
    page_icon="🤖",
    layout="centered"
)

st.title("🤖 IANA – Agente SQL Universal (Todas las tablas)")
st.write("Consultas inteligentes sobre MariaDB con Gemini 2.5 Flash.")

# ========================================================
# 🔌 1. CONEXIÓN A MARIADB (USANDO TUS secrets.toml)
# ========================================================
try:
    engine = create_engine(
        f"mysql+pymysql://{st.secrets['db_credentials']['DB_USER']}:"
        f"{st.secrets['db_credentials']['DB_PASS']}@"
        f"{st.secrets['db_credentials']['DB_HOST']}/"
        f"{st.secrets['db_credentials']['DB_NAME']}"
    )
except KeyError as e:
    st.error("❌ Error leyendo secrets.toml — revisa las claves.")
    st.stop()

db = SQLDatabase(engine)

# ========================================================
# 🤖 2. CONFIGURACIÓN DEL MODELO GEMINI
# ========================================================
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    system_message=PROMPT
)

# ========================================================
# 🧠 3. AGENTE SQL FORZADO A GENERAR QUERIES
# ========================================================
agent = create_sql_agent(
    llm=llm,
    db=db,
    verbose=True,
    top_k=5,
    use_query_checker=True,
    handle_parsing_errors=True
)

# ========================================================
# 📝 4. INPUT DEL USUARIO
# ========================================================
consulta = st.text_input("Haz tu pregunta:", "")

if consulta.strip() != "":
    st.write("⏳ Analizando…")

    try:
        # Ejecutar agente
        result = agent.invoke(consulta)
        st.success("✔ Hecho")

        # ========================================================
        # 📌 EXTRAER LA QUERY GENERADA
        # ========================================================
        st.subheader("📌 SQL Generada")

        sql_query = None
        steps = result.get("intermediate_steps", [])

        for step in steps:
            if isinstance(step, tuple):
                action = step[0]
                if hasattr(action, "tool_input"):
                    sql_query = action.tool_input

        if sql_query:
            st.code(sql_query, language="sql")
        else:
            st.warning("⚠ No se pudo extraer la query generada (el modelo no produjo SQL).")

        # ========================================================
        # 📘 RESPUESTA FINAL
        # ========================================================
        st.subheader("📘 Respuesta")
        st.write(result.get("output", "⚠ Sin respuesta."))

    except Exception as e:
        st.error(f"❌ Error ejecutando el agente: {e}")

