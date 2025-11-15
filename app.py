import streamlit as st
from sqlalchemy import create_engine, text
from langchain_google_genai import ChatGoogleGenerativeAI

# ============================================================
# CONFIG STREAMLIT
# ============================================================
st.set_page_config(page_title="IANA SQL – GEMINI", page_icon="🤖")
st.title("🤖 IANA SQL Universal – Gemini (Estable, Real y Preciso)")
st.caption("Agente SQL profesional con generación de SQL real + ejecución en MariaDB.")

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
# MODELO GEMINI (ESTABLE PARA PRODUCCIÓN)
# ============================================================
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",  # Estable y disponible para todas las claves
    temperature=0
)

# ============================================================
# TABLAS PERMITIDAS
# ============================================================
TABLAS = [
    "replica_VIEW_Fact_Ingresos",
    "replica_VIEW_Fact_Costos",
    "replica_VIEW_Fact_Solicitudes",
    "replica_VIEW_Dim_Empresa",
    "replica_VIEW_Dim_Concepto",
    "replica_VIEW_Dim_Usuario",
    "replica_VIEW_Dim_Ubicacion"
]

# ============================================================
# FUNCIÓN: obtener columnas reales desde MariaDB
# ============================================================
def obtener_columnas(nombre_tabla):
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"SHOW COLUMNS FROM {nombre_tabla};"))
            return [row[0] for row in result.fetchall()]
    except Exception as e:
        return [f"Error leyendo columnas: {e}"]

def obtener_esquema():
    esquema = "ESQUEMA REAL DE LA BASE DE DATOS:\n"
    for tabla in TABLAS:
        columnas = obtener_columnas(tabla)
        esquema += f"\nTabla {tabla}:\n"
        for col in columnas:
            esquema += f"  - {col}\n"
    return esquema

# ============================================================
# FUNCIÓN: limpiar SQL generada por Gemini
# ============================================================
def limpiar_sql(raw_sql: str):
    sql = raw_sql

    sql = sql.replace("```sql", "")
    sql = sql.replace("```", "")
    sql = sql.replace("SQL:", "")
    sql = sql.replace("sql", "")
    sql = sql.replace("Sql", "")
    sql = sql.replace("SQL", "")

    sql = sql.strip()

    # Cortar todo lo que aparezca antes de SELECT
    idx = sql.upper().find("SELECT")
    if idx != -1:
        sql = sql[idx:]

    return sql.strip()

# ============================================================
# PROMPTS
# ============================================================
PROMPT_SQL = """
Eres un generador experto de SQL.
Convierte la consulta del usuario en una QUERY SQL válida usando SOLO estas tablas:

- replica_VIEW_Fact_Ingresos
- replica_VIEW_Fact_Costos
- replica_VIEW_Fact_Solicitudes
- replica_VIEW_Dim_Empresa
- replica_VIEW_Dim_Concepto
- replica_VIEW_Dim_Usuario
- replica_VIEW_Dim_Ubicacion

REGLAS:
1. Genera SOLO SQL (sin explicaciones, sin texto adicional).
2. NO inventes columnas.
3. NO inventes tablas.
4. Usa únicamente las columnas mostradas en el ESQUEMA REAL.
5. Usa JOIN correctos.
"""

PROMPT_ANALISIS = """
Eres un analista profesional.
Explica el resultado SQL en español, de forma clara, útil y concisa.
No inventes datos.
"""

# ============================================================
# UI INPUT
# ============================================================
consulta = st.text_input("Haz tu pregunta de negocio:", "")

if consulta:

    # 1️⃣ Obtener esquema real
    esquema = obtener_esquema()

    # 2️⃣ Generar SQL
    st.write("⏳ Generando SQL…")
    prompt_completo = (
        PROMPT_SQL
        + "\n\n" + esquema
        + "\n\nConsulta del usuario: "
        + consulta
    )

    respuesta_sql = llm.invoke(prompt_completo)
    sql_generada_cruda = respuesta_sql.content.strip()

    # 3️⃣ Limpiar SQL
    sql_final = limpiar_sql(sql_generada_cruda)

    st.subheader("📌 SQL Generada")
    st.code(sql_final, language="sql")

    # 4️⃣ Ejecutar SQL
    st.write("⏳ Ejecutando SQL…")
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql_final))
            filas = [dict(r) for r in result.fetchall()]
    except Exception as e:
        st.error(f"❌ Error ejecutando SQL: {e}")
        filas = []

    st.subheader("📊 Resultado SQL")
    st.write(filas)

    # 5️⃣ Interpretación
    st.write("⏳ Analizando resultado…")

    analisis = llm.invoke(
        PROMPT_ANALISIS + "\n\nRESULTADO:\n" + str(filas)
    )

    st.subheader("📘 Interpretación del Resultado")
    st.write(analisis.content)
