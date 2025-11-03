import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_core.messages import AIMessage, HumanMessage

# ============================================
# 🧩 1. SQL AGENT
# ============================================
def sql_agent():
    creds = st.secrets["db_credentials"]
    uri = f"mysql+pymysql://{creds['user']}:{creds['password']}@{creds['host']}/{creds['database']}"
    db = SQLDatabase.from_uri(uri)

    llm = ChatGoogleGenerativeAI(model="gemini-pro-latest", temperature=0)
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    agent = create_sql_agent(llm=llm, toolkit=toolkit, verbose=True)
    return agent


# ============================================
# 📊 2. ANALYST AGENT
# ============================================
def analyst_agent():
    llm = ChatGoogleGenerativeAI(model="gemini-pro-latest", temperature=0.3)

    def analyze(data):
        prompt = f"""
        Eres un analista financiero experto.
        Con base en estos datos:
        {data}

        Calcula y explica KPIs clave:
        - Margen Bruto
        - Cumplimiento de metas
        - Rentabilidad general

        Responde en tono cálido, ejecutivo y fácil de entender.
        """
        response = llm.invoke(prompt)
        return AIMessage(content=response.content)

    return analyze


# ============================================
# 🔎 3. AUDIT AGENT
# ============================================
def audit_agent():
    llm = ChatGoogleGenerativeAI(model="gemini-pro-latest", temperature=0.2)

    def audit(data):
        prompt = f"""
        Actúa como auditor de operaciones.
        Analiza los siguientes datos y detecta:
        - Inconsistencias o valores anómalos
        - Desviaciones frente a metas
        - Riesgos o alertas que el gerente debe saber
        Datos:
        {data}
        """
        response = llm.invoke(prompt)
        return AIMessage(content=response.content)

    return audit


# ============================================
# 🧭 4. ORCHESTRATOR AGENT
# ============================================
def orchestrator_agent():
    llm = ChatGoogleGenerativeAI(model="gemini-pro-latest", temperature=0.4)

    def orchestrate(message: HumanMessage):
        prompt = f"""
        Eres el gerente virtual de la empresa.
        Analiza la intención del usuario: {message.content}

        Decide si la pregunta requiere:
        - Consulta SQL (para métricas o valores exactos)
        - Análisis (para interpretación o tendencias)
        - Auditoría (para revisar alertas o errores)

        Responde con tono cercano, ejecutivo y natural.
        """
        result = llm.invoke(prompt)
        return AIMessage(content=result.content)

    return orchestrate