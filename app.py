import streamlit as st
from sqlalchemy import create_engine, text
from langchain_google_genai import ChatGoogleGenerativeAI

# ============================================================
# CONFIG
# ============================================================
st.set_page_config(page_title="IANA SQL – Gemini", page_icon="🤖")
st.title("🤖 IANA SQL Universal – Gemini (100% Estable + SQL Real)")
st.caption("Agente SQL estable usando Gemini 1.5/2.5 sin errores de herramientas.")

# ============================================================
# CONEXIÓN A MARIADB
# ============================================================
engine = create_engine(
    f"mysql+pymysql://{st.secrets['db_credentials']['DB_USER']}:"
    f"{st.secrets['db_credentials']['DB_PASS']}@"
    f"{st.secrets['db_credentials']['DB_HOST']}/"
    f"{st.secrets['db_credentials']['DB_NAME']}"
)

# ============================================================
# MODELO GEMINI
# ============================================================
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",   # o gemini-2.5-pro cuando esté estable
    temperature=0
)

# ============================================================
# PROMPT PARA GENERAR SQL
# ============================================================
PROMPT_SQL = """
Eres un generador experto de SQL.
Tu tarea es CONVERTIR la consulta del usuario en una QUERY SQL válida
usando ÚNICAMENTE estas tablas:

- replica_VIEW_Fact_Ingresos
- replica_VIEW_Fact_Costos
- replica_VIEW_Fact_Solicitudes
- replica_VIEW_Dim_Empresa
- replica_VIEW_Dim_Concepto
- replica_VIEW_Dim_Usuario
- replica_VIEW_Dim_Ubicacion

REGLAS:
1. Genera SOLO SQL, nada de texto adicional.
2. No expliques, no hables, no escribas nada más.
3. No inventes columnas ni tablas.
4. Usa JOIN correctos entre FACT y DIM.
"""


# ============================================================
# PROMPT PARA ANÁLISIS DE RESULTADO
# ============================================================
PROMPT_ANALISIS = """
Eres un analista de datos experto.
Explica el resultado de la consulta SQL de forma clara, resumida y profesional,
en español, sin inventar datos.
"""


# ============================================================
# UI: INPUT DEL USUARIO
# ============================================================
consulta = st.text_input("Haz tu pregunta:", "")

if consulta:

    # ---------------------------------------------
    # 1️⃣ GENERAR SQL usando Gemini
    # ---------------------------------------------
    st.write("⏳ Generando SQL…")

    resp_sql = llm.invoke(
        PROMPT_SQL + "\nConsulta del usuario: " + consulta
    )

    sql_query = resp_sql.content.strip()

    st.subheader("📌 SQL Generada")
    st.code(sql_query, language="sql")

    # ---------------------------------------------
    # 2️⃣ EJECUTAR SQL SOBRE MARIADB
    # ---------------------------------------------
    st.write("⏳ Ejecutando SQL…")

    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql_query))
            rows = [dict(r) for r in result.fetchall()]
    except Exception as e:
        rows = []
        st.error(f"❌ Error ejecutando SQL: {e}")

    st.subheader("📊 Resultado SQL")
    st.write(rows)

    # ---------------------------------------------
    # 3️⃣ ANÁLISIS DEL RESULTADO
    # ---------------------------------------------
    st.write("⏳ Analizando…")

    resp_analisis = llm.invoke(
        PROMPT_ANALISIS + "\nResultado:\n" + str(rows)
    )

    st.subheader("📘 Interpretación")
    st.write(resp_analisis.content)
