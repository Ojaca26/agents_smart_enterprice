import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser

# Importación clave para el estado
from typing import TypedDict, Optional, Annotated
from langgraph.graph.message import add_messages
import json

# --- ¡NUEVAS IMPORTACIONES de Autollantas! ---
import re
import pandas as pd
from sqlalchemy import text
# ---------------------------------------------

# =I. DEFINIR EL ESTADO DEL GRAFO =======================
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    next_agent: Optional[str]
    sql_data: Optional[str]

# =II. FUNCIONES AUXILIARES (Copiadas de Autollantas) =================
def limpiar_sql(sql_texto: str) -> str:
    """ Limpia texto generado por LLM para dejar solo la consulta SQL válida. """
    if not sql_texto: return ""
    limpio = re.sub(r'```sql|```', '', sql_texto, flags=re.I)
    limpio = re.sub(r'(?im)^\s*sql[\s:]+', '', limpio)
    m = re.search(r'(?is)(select\b.+)$', limpio)
    if m: limpio = m.group(1)
    return limpio.strip().rstrip(';')

def _asegurar_select_only(sql: str) -> str:
    """ Asegura que solo se ejecuten consultas SELECT. """
    sql_clean = sql.strip().rstrip(';')
    if not re.match(r'(?is)^\s*select\b', sql_clean): raise ValueError("Solo se permite ejecutar consultas SELECT.")
    sql_clean = re.sub(r'(?is)\blimit\s+\d+\s*$', '', sql_clean).strip()
    return sql_clean

# =III. AGENTES ========================================

# --- 1. SQL AGENT (Obtiene datos) ---
# Este agente sigue usando el 'create_sql_agent' lento. 
# Lo vamos a dejar así por ahora para el analista y auditor.
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

# --- 2. ANALYST AGENT ---
def analyst_agent_node(state: AgentState):
    st.info("📊 Analyst Agent: Interpretando métricas...")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.3)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""
         Eres un analista financiero experto.
         Con base en estos datos: {state['sql_data']}
         Y la conversación previa, responde la última pregunta del usuario.
         Responde en tono cálido, ejecutivo y fácil de entender.
         """),
        MessagesPlaceholder(variable_name="messages")
    ])
    
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({"messages": state["messages"]})
    return {"messages": [AIMessage(content=response)]}

# --- 3. AUDIT AGENT ---
def audit_agent_node(state: AgentState):
    st.info("🔍 Audit Agent: Detectando anomalías...")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.2)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""
         Actúa como auditor de operaciones.
         Analiza los siguientes datos: {state['sql_data']}
         Y basándote en la conversación, detecta:
         - Inconsistencias o valores anómalos
         - Desviaciones frente a metas
         - Riesgos o alertas que el gerente debe saber
         """),
        MessagesPlaceholder(variable_name="messages")
    ])
    
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({"messages": state["messages"]})
    return {"messages": [AIMessage(content=response)]}

# --- 4. ORCHESTRATOR AGENT (Sin cambios) ---
def orchestrator_node(state: AgentState):
    st.info("🤖 Orchestrator Agent: Analizando intención...")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0)
    user_question = state["messages"][-1].content.lower()

    if any(x in user_question for x in ["margen", "rentabilidad", "cumplimiento", "tendencia"]):
        next_agent = "analyst_agent"
    elif any(x in user_question for x in ["alerta", "riesgo", "desviación", "problema", "auditoría"]):
        next_agent = "audit_agent"
    elif any(x in user_question for x in ["ingreso", "factura", "venta", "costo", "pedido", "cuánto", "lista", "total"]):
        next_agent = "sql_agent" # <-- Este es el que vamos a cambiar
    else:
        next_agent = "conversational_agent"

    st.success(f"🗣️ Gerente Virtual (IA): Intención detectada. Enrutando a: {next_agent}")
    return {"next_agent": next_agent}

# --- 5. AGENTE CONVERSACIONAL ---
def conversational_agent_node(state: AgentState):
    st.info("💬 Conversational Agent: Generando respuesta...")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.4)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Eres IANA, una asistente IA ejecutiva y amigable. Responde al usuario de forma natural y cercana."),
        MessagesPlaceholder(variable_name="messages")
    ])
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({"messages": state["messages"]})
    return {"messages": [AIMessage(content=response)]}


# --- 6. AGENTE SQL (Final - ¡AHORA ES EL MÉTODO RÁPIDO!) ---
def sql_final_agent_node(state: AgentState):
    st.info("🧩 SQL Agent (Rápido): Generando consulta...")
    user_question = state["messages"][-1].content
    
    # --- 1. Conexión y LLM ---
    creds = st.secrets["db_credentials"]
    uri = f"mysql+pymysql://{creds['user']}:{creds['password']}@{creds['host']}/{creds['database']}"
    db = SQLDatabase.from_uri(uri)
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.0) # Usamos un LLM potente

    # --- 2. Obtener Esquema (Paso clave) ---
    try:
        # A diferencia de 'autollantas', no especificamos tablas
        # para que funcione con tu base de datos de IANA.
        schema_info = db.get_table_info()
    except Exception as e:
        return {"messages": [AIMessage(content=f"Error al obtener esquema de BD: {e}")]}

    # --- 3. Construir el Prompt (Lógica de 'autollantas') ---
    prompt_con_instrucciones = f"""
    Tu tarea es generar una consulta SQL limpia (SOLO SELECT) para responder la pregunta del usuario, basándote ESTRICTAMENTE en el siguiente esquema.

    --- ESQUEMA DE LA BASE DE DATOS ---
    {schema_info}
    --- FIN DEL ESQUEMA ---

    --- REGLAS DE SQL ---
    1. Siempre que filtres por fecha, usa funciones de fecha como YEAR(), MONTH(), etc.
    2. Si piden "ventas 2025", asume YEAR(columna_de_fecha) = 2025.
    3. Responde siempre con la mayor cantidad de información posible según la pregunta.
    
    --- PREGUNTA ---
    {user_question}

    --- SALIDA ---
    Devuelve SOLO la consulta SQL (sin explicaciones, sin markdown ```sql```).
    """
    
    # --- 4. Llamada Directa al LLM (El método RÁPIDO) ---
    try:
        sql_query_bruta = llm.invoke(prompt_con_instrucciones).content
        st.code(sql_query_bruta, language="sql") # Para depurar

        # --- 5. Limpiar y Ejecutar ---
        sql_query_limpia = limpiar_sql(sql_query_bruta)
        sql_query_limpia = _asegurar_select_only(sql_query_limpia)

        if not sql_query_limpia:
            return {"messages": [AIMessage(content="No pude generar una consulta SQL válida.")]}

        # --- 6. Ejecución del SQL ---
        st.info("⏳ Ejecutando consulta directa...")
        engine = db._engine # Accedemos al motor de SQLAlchemy
        with engine.connect() as conn:
            # Usamos 'text' de sqlalchemy
            df = pd.read_sql(text(sql_query_limpia), conn)
        
        st.success(f"✅ ¡Consulta ejecutada! Filas: {len(df)}")
        
        # Convertir DataFrame a string para el chat
        if df.empty:
            result_string = "No se encontraron resultados para esa consulta."
        else:
            result_string = df.to_markdown(index=False)
        
        response = f"¡Claro! Aquí tienes los datos que consultaste:\n\n{result_string}"
        return {"messages": [AIMessage(content=response)]}

    except Exception as e:
        # --- PLAN B (El Agente Lento) ---
        # Si el método rápido falla, intentamos con el agente.
        st.warning(f"La consulta directa falló ({e}). Intentando con el Agente SQL experto...")
        try:
            llm_agent = ChatGoogleGenerativeAI(model="gemini-pro", temperature=0)
            toolkit = SQLDatabaseToolkit(db=db, llm=llm_agent)
            agent = create_sql_agent(llm=llm_agent, toolkit=toolkit, verbose=False)
            
            result = agent.run(user_question)
            response = f"Usé mi método experto y esto encontré:\n\n```\n{result}\n```"
            return {"messages": [AIMessage(content=response)]}
        except Exception as e2:
            return {"messages": [AIMessage(content=f"Lo siento, ambos métodos de SQL fallaron. Error final: {e2}")]}
