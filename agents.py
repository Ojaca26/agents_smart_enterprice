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
from sqlalchemy import text
import pandas as pd
import re
import time

# ======================================================
# 🧠 1) ESTADO DEL GRAFO
# ======================================================
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    next_agent: Optional[str]
    sql_data: Optional[str]


# ======================================================
# ⚙️ 2) FUNCIONES AUXILIARES
# ======================================================
def limpiar_sql(sql_texto: str) -> str:
    """Limpia texto generado por el LLM para dejar solo el SELECT."""
    if not sql_texto:
        return ""
    limpio = re.sub(r'```sql|```', '', sql_texto, flags=re.I)
    limpio = re.sub(r'(?im)^\s*sql[\s:]+', '', limpio)
    m = re.search(r'(?is)(select\b.+)$', limpio)
    if m:
        limpio = m.group(1)
    return limpio.strip().rstrip(';')


def _asegurar_select_only(sql: str) -> str:
    """Evita que se ejecuten sentencias distintas de SELECT."""
    sql_clean = sql.strip().rstrip(';')
    if not re.match(r'(?is)^\s*select\b', sql_clean):
        raise ValueError("Solo se permite ejecutar consultas SELECT.")
    sql_clean = re.sub(r'(?is)\blimit\s+\d+\s*$', '', sql_clean).strip()
    return sql_clean


# ======================================================
# 🗄️ 3) FUNCIÓN CACHEADA: ESQUEMA LIVIANO
# ======================================================
@st.cache_data(ttl=600)
def get_schema_info(_db) -> str:
    """Obtiene las columnas de las principales vistas de negocio."""
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
    with _db._engine.connect() as conn:
        for t in tablas:
            try:
                columnas = conn.exec_driver_sql(f"SHOW COLUMNS FROM {t}").fetchmany(8)
                col_names = [c[0] for c in columnas]
                schema_info += f"{t}: {', '.join(col_names)}\n"
            except Exception as e:
                schema_info += f"{t}: (Error al obtener columnas: {e})\n"
    return schema_info


# ======================================================
# 🤖 4) AGENTES SECUNDARIOS
# ======================================================
def sql_agent_node(state: AgentState):
    st.info("🧩 SQL Agent (Lento - Plan B): obteniendo datos...")
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
    st.info("📊 Analyst Agent: interpretando métricas...")
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
    st.info("🔍 Audit Agent: detectando anomalías...")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.2)
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""
        Actúa como auditor de operaciones.
        Analiza los siguientes datos: {state['sql_data']}
        y detecta:
        - Inconsistencias o valores anómalos
        - Desviaciones frente a metas
        - Riesgos o alertas importantes.
        """),
        MessagesPlaceholder(variable_name="messages")
    ])
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({"messages": state["messages"]})
    return {"messages": [AIMessage(content=response)]}


def orchestrator_node(state: AgentState):
    st.info("🤖 Orchestrator Agent: analizando intención...")
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

    st.success(f"🗣️ Intención detectada → {next_agent}")
    return {"next_agent": next_agent}


def conversational_agent_node(state: AgentState):
    st.info("💬 Conversational Agent: respondiendo de forma natural...")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.4)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Eres IANA, una asistente IA ejecutiva y amigable."),
        MessagesPlaceholder(variable_name="messages")
    ])
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({"messages": state["messages"]})
    return {"messages": [AIMessage(content=response)]}


# ======================================================
# ⚡ 5) AGENTE SQL RÁPIDO CON EFECTO VISUAL (FINAL)
# ======================================================
def sql_final_agent_node(state: AgentState):
    user_question = state["messages"][-1].content
    st.info("🧩 SQL Agent (Rápido): Generando consulta...")
    st.markdown(f"💬 **Pregunta del usuario:** _{user_question}_")

    # --- Conexión y modelo ---
    creds = st.secrets["db_credentials"]
    uri = f"mysql+pymysql://{creds['user']}:{creds['password']}@{creds['host']}/{creds['database']}"
    db = SQLDatabase.from_uri(uri)
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash-latest",
        temperature=0.0,
        max_output_tokens=1024,
        timeout=40
    )

    # --- Obtener esquema ---
    with st.spinner("📘 Obteniendo esquema de base de datos..."):
        schema_info = get_schema_info(db)
    st.text_area("📘 Esquema de base de datos (resumen)", schema_info, height=180)

    # --- Crear prompt ---
    prompt_con_instrucciones = f"""
    Eres un experto en SQL para MySQL/MariaDB.
    Genera una consulta SELECT válida que responda a:
    "{user_question}"
    usando las columnas disponibles:

    {schema_info}

    Reglas:
    - Si mencionan 'ingresos', usa replica_VIEW_Fact_Ingresos y la columna Valor_Facturado.
    - Si se menciona un año, usa YEAR(ID_Fecha)=año.
    - Usa SUM(Valor_Facturado) para calcular ingresos acumulados.
    - Devuelve solo la consulta SQL sin comentarios.
    """

    # --- Generar SQL ---
    st.info("🤖 Solicitando al modelo que genere SQL...")
    try:
        with st.spinner("💭 IANA está pensando..."):
            sql_query_bruta = llm.invoke(prompt_con_instrucciones).content.strip()
        if not sql_query_bruta:
            raise ValueError("El modelo no devolvió ninguna consulta SQL.")
        st.code(sql_query_bruta, language="sql")
    except Exception as e:
        st.error(f"❌ Error al generar SQL: {e}")
        return {"messages": [AIMessage(content=f"Error al generar SQL: {e}")]}

    # --- Limpiar SQL ---
    try:
        sql_query_limpia = limpiar_sql(sql_query_bruta)
        sql_query_limpia = _asegurar_select_only(sql_query_limpia)
    except Exception as e:
        st.error(f"⚠️ SQL inválido: {e}")
        return {"messages": [AIMessage(content=f"SQL inválido: {e}")]}

    st.success("✅ SQL limpio y validado:")
    st.code(sql_query_limpia, language="sql")

    # --- Ejecutar consulta ---
    progress_bar = st.progress(0, text="⏳ Ejecutando consulta...")
    try:
        with db._engine.connect() as conn:
            progress_bar.progress(40, text="🛰️ Enviando consulta...")
            if "limit" not in sql_query_limpia.lower():
                sql_query_limpia += " LIMIT 3000"
            df = pd.read_sql(text(sql_query_limpia), conn)
            progress_bar.progress(100, text="✅ Consulta completada")

        progress_bar.empty()
        st.success(f"✅ ¡Consulta ejecutada! Filas devueltas: {len(df)}")

        # --- Efecto de escritura (typing) ---
        if df.empty:
            respuesta_final = "No se encontraron resultados para esa consulta."
        else:
            respuesta_final = (
                f"🧩 Consulta ejecutada con éxito:\n\n```sql\n{sql_query_limpia}\n```\n\n"
                + df.to_markdown(index=False)
            )

        placeholder = st.empty()
        typed = ""
        for char in respuesta_final:
            typed += char
            placeholder.markdown(typed)
            time.sleep(0.002)

        return {"messages": [AIMessage(content=respuesta_final)]}

    except Exception as e:
        progress_bar.empty()
        st.warning(f"⚠️ Error en ejecución directa: {e}. Activando modo experto...")
        try:
            llm_agent = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0)
            toolkit = SQLDatabaseToolkit(db=db, llm=llm_agent)
            agent = create_sql_agent(llm=llm_agent, toolkit=toolkit, verbose=False)
            result = agent.run(user_question)
            return {"messages": [AIMessage(content=f"Modo experto → Resultado:\n\n{result}")]}
        except Exception as e2:
            st.error(f"❌ Error crítico: {e2}")
            return {"messages": [AIMessage(content=f"Error crítico: {e2}")]}
