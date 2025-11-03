import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI  # <-- ‼️ ESTA LÍNEA ES LA CORRECCIÓN
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

# =I. DEFINIR EL ESTADO DEL GRAFO =======================
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    next_agent: Optional[str]
    sql_data: Optional[str]

# =II. AGENTES ========================================

# --- 1. SQL AGENT (Obtiene datos) ---
def sql_agent_node(state: AgentState):
    st.info("🧩 SQL Agent: Obteniendo datos para el análisis...")
    user_question = state["messages"][-1].content
    
    creds = st.secrets["db_credentials"]
    uri = f"mysql+pymysql://{creds['user']}:{creds['password']}@{creds['host']}/{creds['database']}"
    db = SQLDatabase.from_uri(uri)
    llm = ChatGoogleGenerativeAI(model="gemini-pro", temperature=0) # <-- ‼️ CORREGIDO
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    agent = create_sql_agent(llm=llm, toolkit=toolkit, verbose=False) 
    
    try:
        result = agent.run(user_question)
        return {"sql_data": result}
    except Exception as e:
        return {"sql_data": f"Error al ejecutar SQL: {e}"}

# --- 2. ANALYST AGENT (CORREGIDO) ---
def analyst_agent_node(state: AgentState):
    st.info("📊 Analyst Agent: Interpretando métricas...")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.3) # <-- ‼️ CORREGIDO
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""
         Eres un analista financiero experto.
         Con base en estos datos: {state['sql_data']}
         Y la conversación previa, responde la última pregunta del usuario.
         
         Calcula y explica KPIs clave:
         - Margen Bruto
         - Cumplimiento de metas
         - Rentabilidad general
         Responde en tono cálido, ejecutivo y fácil de entender.
         """),
        MessagesPlaceholder(variable_name="messages")
    ])
    
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({"messages": state["messages"]})
    return {"messages": [AIMessage(content=response)]}

# --- 3. AUDIT AGENT (CORREGIDO) ---
def audit_agent_node(state: AgentState):
    st.info("🔍 Audit Agent: Detectando anomalías...")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.2) # <-- ‼️ CORREGIDO
    
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
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0) # <-- ‼️ CORREGIDO
    
    user_question = state["messages"][-1].content.lower()

    if any(x in user_question for x in ["margen", "rentabilidad", "cumplimiento", "tendencia"]):
        next_agent = "analyst_agent"
    elif any(x in user_question for x in ["alerta", "riesgo", "desviación", "problema", "auditoría"]):
        next_agent = "audit_agent"
    elif any(x in user_question for x in ["ingreso", "factura", "venta", "costo", "pedido", "cuánto", "lista"]):
        next_agent = "sql_agent"
    else:
        next_agent = "conversational_agent"

    st.success(f"🗣️ Gerente Virtual (IA): Intención detectada. Enrutando a: {next_agent}")
    return {"next_agent": next_agent}

# --- 5. AGENTE CONVERSACIONAL (¡CORREGIDO!) ---
def conversational_agent_node(state: AgentState):
    st.info("💬 Conversational Agent: Generando respuesta...")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.4) # <-- ‼️ CORREGIDO
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Eres IANA, una asistente IA ejecutiva y amigable. Responde al usuario de forma natural y cercana."),
        MessagesPlaceholder(variable_name="messages")
    ])
    
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({"messages": state["messages"]})
    
    return {"messages": [AIMessage(content=response)]}

# --- 6. AGENTE SQL (Final - Responde al usuario) ---
def sql_final_agent_node(state: AgentState):
    st.info("🧩 SQL Agent: Consultando base de datos...")
    
    user_question = state["messages"][-1].content
    
    creds = st.secrets["db_credentials"]
    uri = f"mysql+pymysql://{creds['user']}:{creds['password']}@{creds['host']}/{creds['database']}"
    db = SQLDatabase.from_uri(uri)
    llm = ChatGoogleGenerativeAI(model="gemini-pro", temperature=0) # <-- ‼️ CORREGIDO
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    agent = create_sql_agent(llm=llm, toolkit=toolkit, verbose=False)
    
    try:
        result = agent.run(user_question)
        response = f"¡Claro! Aquí tienes los datos que consultaste:\n\n```\n{result}\n```"
        return {"messages": [AIMessage(content=response)]}
    except Exception as e:
        return {"messages": [AIMessage(content=f"Lo siento, tuve un error al consultar la base de datos: {e}")]}
