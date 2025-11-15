import streamlit as st
from sqlalchemy import create_engine
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_google_genai import ChatGoogleGenerativeAI

PROMPT = """
Eres un Agente SQL experto encargado de responder cualquier pregunta del usuario
usando ÚNICAMENTE las tablas disponibles en la base de datos.

Tablas disponibles:
- replica_VIEW_Dim_Concepto
- replica_VIEW_Dim_Empresa
- replica_VIEW_Dim_Ubicacion
- replica_VIEW_Dim_Usuario
- replica_VIEW_Fact_Costos
- replica_VIEW_Fact_Ingresos
- replica_VIEW_Fact_Solicitudes

REGLAS IMPORTANTES:
1. Determina la intención del usuario.
2. Elige la tabla o combinación correcta.
3. Valida que los campos realmente existan.
4. NO respondas “I don’t know”.
5. Si no puedes responder sin ver datos, GENERA la query más probable.
6. Tu salida SIEMPRE debe incluir:
   - SQL_QUERY: la consulta que vas a ejecutar
   - ANSWER: la interpretación en español
"""

st.set_page_config(page_title="IANA SQL Universal", page_icon="🤖")
st.title("🤖 IANA – Agente SQL Universal (Todas las tablas)")

# -------------------------------------------------------
# 1. Conexión
# -------------------------------------------------------
engine = create_engine(
    f"mysql+pymysql://{st.secrets['DB_USER']}:{st.secrets['DB_PASS']}@{st.secrets['DB_HOST']}/{st.secrets['DB_NAME']}"
)

db = SQLDatabase(engine)

# -------------------------------------------------------
# 2. Modelo
# -------------------------------------------------------
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    system_message=PROMPT
)

# -------------------------------------------------------
# 3. Agente SQL
# -------------------------------------------------------
agent = create_sql_agent(
    llm=llm,
    db=db,
    verbose=True,
    handle_parsing_errors=True
)

# -------------------------------------------------------
# 4. UI
# -------------------------------------------------------
consulta = st.text_input("Haz tu pregunta:", "")

if consulta:
    st.write("⏳ Analizando…")

    try:
        result = agent.invoke(consulta)
        st.success("✔ Hecho")

        # ------------------------------
        # Mostrar QUERY generada (SIEMPRE)
        # ------------------------------
        st.subheader("📌 SQL Generada")

        sql_query = None

        # El SQL usualmente viene en intermediate_steps
        if "intermediate_steps" in result:
            for step in result["intermediate_steps"]:
                if isinstance(step, dict) and "tool_input" in step:
                    sql_query = step["tool_input"]

        if sql_query:
            st.code(sql_query, language="sql")
        else:
            st.warning("⚠ No se pudo extraer la query generada. (El modelo no la produjo)")

        # ------------------------------
        # Mostrar respuesta final
        # ------------------------------
        st.subheader("📘 Respuesta")
        st.write(result["output"])

    except Exception as e:
        st.error(str(e))
