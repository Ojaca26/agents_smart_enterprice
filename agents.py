import streamlit as st
from langchain_google_genai import ChatGoogleGenerai
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Importación clave para el estado
from typing import TypedDict, Optional, Annotated
from langgraph.graph.message import add_messages
import json

# =I. DEFINIR EL ESTADO DEL GRAFO =======================
# Este es el "cerebro" o la memoria compartida de la red de agentes.
class AgentState(TypedDict):
    # La lista de mensajes de chat
    messages: Annotated[list, add_messages]
    # La decisión del orquestador
    next_agent: Optional[str]
    # Los datos de la consulta SQL
    sql_data: Optional[str]

# =II. AGENTES ========================================

# --- 1. SQL AGENT (Modificado) ---
# Ahora recibe el 'state' completo, extrae el último mensaje, y 
# devuelve un dict para actualizar el 'sql_data'
def sql_agent_node(state: AgentState):
    st.info("🧩 SQL Agent: Consultando base de datos...")
    
    # Obtener la pregunta original del usuario
    user_question = state["messages"][-1].content
    
    # Configuración del agente SQL
    creds = st.secrets["db_credentials"]
    uri = f"mysql+pymysql://{creds['user']}:{creds['password']}@{creds['host']}/{creds['database']}"
    db = SQLDatabase.from_uri(uri)
    llm = ChatGoogleGenerativeAI(model="gemini-pro", temperature=0)
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    agent = create_sql_agent(llm=llm, toolkit=toolkit, verbose=False) # verbose=False para no ensuciar la consola
    
    try:
        # Ejecutar la consulta
        result = agent.run(user_question)
        return {"sql_data": result}
    except Exception as e:
        return {"sql_data": f"Error al ejecutar SQL: {e}"}

# --- 2. ANALYST AGENT (Modificado) ---
# Ahora recibe el 'state', extrae 'sql_data' y 'messages', 
# y devuelve un 'AIMessage' para el usuario.
def analyst_agent_node(state: AgentState):
    st.info("📊 Analyst Agent: Interpretando métricas...")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.3)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """
         Eres un analista financiero experto.
         Con base en estos datos: {data}
         Y la pregunta original del usuario: {question}

         Calcula y explica KPIs clave:
         - Margen Bruto
         - Cumplimiento de metas
         - Rentabilidad general

         Responde en tono cálido, ejecutivo y fácil de entender.
         """),
        ("human", "{question}")
    ])
    
    chain = prompt | llm | StrOutputParser()
    
    response = chain.invoke({
        "data": state["sql_data"],
        "question": state["messages"][-1].content
    })
    return {"messages": [AIMessage(content=response)]}

# --- 3. AUDIT AGENT (Modificado) ---
# Similar al analista, pero con su propio prompt
def audit_agent_node(state: AgentState):
    st.info("🔍 Audit Agent: Detectando anomalías...")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.2)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """
         Actúa como auditor de operaciones.
         Analiza los siguientes datos y detecta:
         - Inconsistencias o valores anómalos
         - Desviaciones frente a metas
         - Riesgos o alertas que el gerente debe saber
         Datos: {data}
         Pregunta del usuario: {question}
         """),
        ("human", "{question}")
    ])
    
    chain = prompt | llm | StrOutputParser()
    
    response = chain.invoke({
        "data": state["sql_data"],
        "question": state["messages"][-1].content
    })
    return {"messages": [AIMessage(content=response)]}

# --- 4. ORCHESTRATOR AGENT (¡Muy Modificado!) ---
# Ya no es un agente de chat. Es un ENRUTADOR.
# Su única salida es un 'dict' con la clave 'next_agent'.
def orchestrator_node(state: AgentState):
    st.info("🤖 Orchestrator Agent: Analizando intención...")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0)
    
    # Extraer la pregunta del usuario
    user_question = state["messages"][-1].content.lower()

    # Lógica de enrutamiento simple (puedes mejorar esto con un LLM si quieres)
    if any(x in user_question for x in ["margen", "rentabilidad", "cumplimiento", "tendencia"]):
        next_agent = "analyst_agent"
    elif any(x in user_question for x in ["alerta", "riesgo", "desviación", "problema", "auditoría"]):
        next_agent = "audit_agent"
    elif any(x in user_question for x in ["ingreso", "factura", "venta", "costo", "pedido", "cuánto", "lista"]):
        next_agent = "sql_agent" # El agente SQL ahora da la respuesta final
    else:
        next_agent = "conversational_agent" # Necesitamos un agente conversacional

    st.success(f"🗣️ Gerente Virtual (IA): Intención detectada. Enrutando a: {next_agent}")
    return {"next_agent": next_agent}

# --- 5. AGENTE CONVERSACIONAL (Nuevo) ---
# Maneja el "hola" y "gracias".
def conversational_agent_node(state: AgentState):
    st.info("💬 Conversational Agent: Generando respuesta...")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.4)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Eres IANA, una asistente IA ejecutiva y amigable. Responde al usuario de forma natural y cercana."),
        state["messages"][-1]
    ])
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({})
    
    return {"messages": [AIMessage(content=response)]}

# --- 6. AGENTE SQL (Final) ---
# Modificamos el 'sql_agent_node' para que también pueda ser un punto final,
# devolviendo un AIMessage con los datos.
def sql_final_agent_node(state: AgentState):
    st.info("🧩 SQL Agent: Consultando base de datos...")
    
    user_question = state["messages"][-1].content
    
    creds = st.secrets["db_credentials"]
    uri = f"mysql+pymysql://{creds['user']}:{creds['password']}@{creds['host']}/{creds['database']}"
    db = SQLDatabase.from_uri(uri)
    llm = ChatGoogleGenerativeAI(model="gemini-pro", temperature=0)
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    agent = create_sql_agent(llm=llm, toolkit=toolkit, verbose=False)
    
    try:
        result = agent.run(user_question)
        # La diferencia: devuelve un mensaje para el usuario
        response = f"¡Claro! Aquí tienes los datos que consultaste:\n\n```\n{result}\n```"
        return {"messages": [AIMessage(content=response)]}
    except Exception as e:
        return {"messages": [AIMessage(content=f"Lo siento, tuve un error al consultar la base de datos: {e}")]}
