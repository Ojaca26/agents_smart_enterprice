import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser

from typing import TypedDict, Optional, Annotated
from langgraph.graph.message import add_messages
import re
import pandas as pd
from sqlalchemy import text

# ======================================================
#  I.  ESTADO DEL GRAFO
# ======================================================
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    next_agent: Optional[str]
    sql_data: Optional[str]


# ======================================================
#  II. FUNCIONES AUXILIARES
# ======================================================
def limpiar_sql(sql_texto: str) -> str:
    if not sql_texto:
        return ""
    limpio = re.sub(r'```sql|```', '', sql_texto, flags=re.I)
    limpio = re.sub(r'(?im)^\s*sql[\s:]+', '', limpio)
    m = re.search(r'(?is)(select\b.+)$', limpio)
    if m:
        limpio = m.group(1)
    return limpio.strip().rstrip(';')


def _asegurar_select_only(sql: str) -> str:
    sql_clean = sql.strip().rstrip(';')
    if not re.match(r'(?is)^\s*select\b', sql_clean):
        raise ValueError("Solo se permite ejecutar consultas SELECT.")
    sql_clean = re.sub(r'(?is)\blimit\s+\d+\s*$', '', sql_clean).strip()
    return sql_clean


# ======================================================
#  III. AGENTES INDIVIDUALES
# ======================================================
def sql_agent_node(state: AgentState):
    st.info("🧩 SQL Agent: Obteniendo datos para el análisis...")
    user_question = state["messages"][-1].content

    creds = st.secrets["db_credentials"]
    uri = f"mysql+pymysql://{creds['user']}:{creds['password']}@{creds['host']}/{creds['database']}"
    db = SQLDatabase.from_uri(uri)
    llm = ChatGoogleGenerativeAI(model="gemini-pro", temperature=0)
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    agent = create_sql_agent(llm=llm, toolkit=toolkit, verbose=False)

    try:
        result = agent.run(user_question)
        return {"sql_data": result}
    except Exception as e:
        return {"sql_data": f"Error al ejecutar SQL: {e}"}


def analyst_agent_node(state: AgentState):
    st.info("📊 Analyst Agent: Interpretando métricas...")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.3)
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""
         Eres un analista financiero experto.
         Con base en estos datos: {state['sql_data']}
         y la conversación previa, responde la última pregunta del usuario.
         """),
        MessagesPlaceholder(variable_name="messages")
    ])
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({"messages": state["messages"]})
    return {"messages": [AIMessage(content=response)]}


def audit_agent_node(state: AgentState):
    st.info("🔍 Audit Agent: Detectando anomalías...")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.2)
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""
         Actúa como auditor de operaciones.
         Analiza los siguientes datos: {state['sql_data']}
         y detecta:
         - Inconsistencias o valores anómalos
         - Desviaciones frente a metas
         - Riesgos o alertas importantes
         """),
        MessagesPlaceholder(variable_name="messages")
    ])
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({"messages": state["messages"]})
    return {"messages": [AIMessage(content=response)]}


def orchestrator_node(state: AgentState):
    st.info("🤖 Orchestrator Agent: Analizando intención...")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0)
    user_question = state["messages"][-1].content.lower()

    if any(x in user_question for x in ["margen", "rentabilidad", "cumplimiento", "tendencia"]):
        next_agent = "analyst_agent"
    elif any(x in user_question for x in ["alerta", "riesgo", "desviación", "problema", "auditoría"]):
        next_agent = "audit_agent"
    elif any(x in user_question for x in ["ingreso", "factura", "venta", "costo", "pedido", "cuánto", "lista", "total"]):
        next_agent = "sql_agent"
    else:
        next_agent = "conversational_agent"

    st.success(f"🗣️ Gerente Virtual (IA): Intención detectada → {next_agent}")
    return {"next_agent": next_agent}


def conversational_agent_node(state: AgentState):
    st.info("💬 Conversational Agent: Generando respuesta...")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.4)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Eres IANA, una asistente IA ejecutiva y amigable."),
        MessagesPlaceholder(variable_name="messages")
    ])
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({"messages": state["messages"]})
    return {"messages": [AIMessage(content=response)]}


# ======================================================
#  VI.  AGENTE SQL RÁPIDO (OPTIMIZADO)
# ======================================================
@st.cache_data(ttl=600)
def sql_final_agent_node(state: AgentState):
    st.info("🧩 SQL Agent (Rápido): Generando consulta...")
    user_question = state["messages"][-1].content

    # --- 1. Conexión y LLM ---
    creds = st.secrets["db_credentials"]
    uri = f"mysql+pymysql://{creds['user']}:{creds['password']}@{creds['host']}/{creds['database']}"
    db = SQLDatabase.from_uri(uri)
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.0)

    # --- 2. Obtener esquema liviano (corregido + trazas visibles) ---
    try:
        tablas = [
            "replica_VIEW_Fact_Ingresos",
            "replica_VIEW_Fact_Costos",
            "replica_VIEW_Fact_Solicitudes",
            "replica_VIEW_Dim_Empresa",
            "replica_VIEW_Dim_Concepto",
            "replica_VIEW_Dim_Usuario",
            "replica_VIEW_Dim_Ubicacion"
        ]

        schema_info = ""
        with db._engine.connect() as conn:
            for t in tablas:
                try:
                    columnas = conn.exec_driver_sql(f"SHOW COLUMNS FROM {t}").fetchmany(8)
                    col_names = [c[0] for c in columnas]
                    schema_info += f"{t}: {', '.join(col_names)}\n"
                except Exception as e:
                    schema_info += f"{t}: (Error al obtener columnas: {e})\n"

        st.success("✅ Esquema obtenido correctamente.")
        st.text_area("📘 Esquema de base de datos (resumen)", schema_info, height=180)

    except Exception as e:
        st.error(f"❌ Error al obtener esquema de BD: {e}")
        return {"messages": [AIMessage(content=f"Error al obtener esquema de BD: {e}")]}

    # --- 3. Construir el prompt del modelo ---
    prompt_con_instrucciones = f"""
    Genera una consulta SQL limpia (SOLO SELECT) para responder la pregunta.
    Usa el siguiente esquema de base de datos:

    --- ESQUEMA ---
    {schema_info}
    --- FIN DEL ESQUEMA ---

    Reglas:
    1. Usa YEAR() y MONTH() para fechas.
    2. Si se menciona "2025", filtra con YEAR(ID_Fecha)=2025.
    3. Usa los nombres de columnas tal cual aparecen en el esquema.
    4. No uses alias raros ni funciones desconocidas.

    Pregunta:
    {user_question}

    Devuelve SOLO el SQL (sin ```sql ni comentarios).
    """

    # --- 4. Generar el SQL con el LLM ---
    try:
        sql_query_bruta = llm.invoke(prompt_con_instrucciones).content
        st.info("🧠 SQL crudo generado por el modelo:")
        st.code(sql_query_bruta, language="sql")

        sql_query_limpia = limpiar_sql(sql_query_bruta)
        sql_query_limpia = _asegurar_select_only(sql_query_limpia)

        if not sql_query_limpia:
            st.error("❌ El SQL generado está vacío o no es válido.")
            return {"messages": [AIMessage(content="No se generó una consulta SQL válida.")]}

        st.success("✅ SQL limpio y validado:")
        st.code(sql_query_limpia, language="sql")

        # --- 5. Ejecutar SQL (con límite por seguridad) ---
        st.info("⏳ Ejecutando consulta directa...")
        with db._engine.connect() as conn:
            if "limit" not in sql_query_limpia.lower():
                sql_query_limpia += " LIMIT 3000"
            df = pd.read_sql(text(sql_query_limpia), conn)

        st.success(f"✅ ¡Consulta ejecutada correctamente! Filas devueltas: {len(df)}")

        if df.empty:
            result_string = "No se encontraron resultados para esa consulta."
        else:
            result_string = df.to_markdown(index=False)

        response = f"🧩 Consulta ejecutada con éxito:\n\n```sql\n{sql_query_limpia}\n```\n\n{result_string}"
        return {"messages": [AIMessage(content=response)]}

    except Exception as e:
        st.warning(f"⚠️ Error en ejecución directa: {e}. Activando modo experto...")
        try:
            llm_agent = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0)
            toolkit = SQLDatabaseToolkit(db=db, llm=llm_agent)
            agent = create_sql_agent(llm=llm_agent, toolkit=toolkit, verbose=False)
            result = agent.run(user_question)
            response = f"Usé el modo experto y esto encontré:\n\n```\n{result}\n```"
            return {"messages": [AIMessage(content=response)]}
        except Exception as e2:
            st.error(f"❌ Error en ambos métodos: {e2}")
            return {"messages": [AIMessage(content=f"❌ Error crítico: {e2}")]}

