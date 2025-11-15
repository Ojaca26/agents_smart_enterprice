import streamlit as st
from sqlalchemy import create_engine
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_google_genai import ChatGoogleGenerativeAI

# -------------------------------------------------------
# PROMPT MAESTRO
# -------------------------------------------------------
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

REGLAS:
1. Determina la intención del usuario.
2. Elige la tabla o combinación correcta.
3. Valida que los campos existan realmente.
4. Si la pregunta es general (ej. “mejor cliente”), deduce cómo responder.
5. No inventes columnas.
6. Produce:
   A) el SQL
   B) una respuesta clara en español.
"""

st.set_page_config(page_title="IANA SQL Universal", page_icon="🤖")
st.title("🤖 IANA – Agente SQL Universal (Todas las tablas)")

# -------------------------------------------------------
# 1. Conexión a MariaDB
# -------------------------------------------------------
engine = create_engine(
    f"mysql+pymysql://{st.secrets['DB_USER']}:{st.secrets['DB_PASS']}@{st.secrets['DB_HOST']}/{st.secrets['DB_NAME']}"
)

db = SQLDatabase(engine)

# -------------------------------------------------------
# 2. Modelo LLM
# -------------------------------------------------------
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    system_message=PROMPT
)

# -------------------------------------------------------
# 3. Crear agente SQL
# -------------------------------------------------------
agent = create_sql_agent(
    llm=llm,
    db=db,
    verbose=True,
    handle_parsing_errors=True
)

# -------------------------------------------------------
# 4. Input de usuario
# -------------------------------------------------------
consulta = st.text_input("Haz tu pregunta:", "")

if consulta:
    st.write("⏳ Analizando…")
    try:
        respuesta = agent.invoke(consulta)
        st.success("✔ Hecho")

        st.subheader("📘 Respuesta")
        st.write(respuesta["output"])

    except Exception as e:
        st.error(str(e))
