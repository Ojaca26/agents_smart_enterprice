# graph_sql.py
from __future__ import annotations

from typing import TypedDict, Literal, Any, Dict

from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from db import get_sql_database, load_schema_text, ALLOWED_TABLES

import json
import textwrap
import decimal


# ==========================
# UTILS
# ==========================

def clean_sql(query: str) -> str:
    """Limpia SQL quitando formato Markdown, backticks y basura."""
    if not query:
        return ""
    q = query.replace("```sql", "")
    q = q.replace("```", "")
    q = q.replace("`", "")
    return q.strip()


def safe_rows(rows):
    """Convierte DECIMAL y None a tipos seguros para Streamlit."""
    safe_list = []
    for row in rows:
        safe_row = {}
        for k, v in row.items():
            if isinstance(v, decimal.Decimal):
                safe_row[k] = float(v)
            elif v is None:
                safe_row[k] = ""
            else:
                safe_row[k] = v
        safe_list.append(safe_row)
    return safe_list


# ==========================
# 1. LLM y BD compartidos
# ==========================

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
)

sql_db = get_sql_database()
schema_text = load_schema_text()


# ==========================
# 2. Estado del grafo
# ==========================

class GraphState(TypedDict):
    question: str
    route: Literal["ingresos", "costos", "solicitudes", "mixto", "chitchat"]
    sql_query: str
    result: Any
    error: str


# ==========================
# 3. Nodos
# ==========================

def router_node(state: GraphState) -> GraphState:
    """Clasifica la intención de la pregunta."""
    question = state["question"]

    system_prompt = """
    Eres un clasificador de intención para un asistente de analítica de negocios.
    Categorías:
    - ingresos
    - costos
    - solicitudes
    - mixto
    - chitchat
    """

    messages = [
        SystemMessage(content=textwrap.dedent(system_prompt)),
        HumanMessage(content=question),
    ]
    raw = llm.invoke(messages).content

    route: str = "chitchat"
    try:
        data = json.loads(raw)
        value = data.get("route", "chitchat")
        if value in ["ingresos", "costos", "solicitudes", "mixto", "chitchat"]:
            route = value
    except:
        q = question.lower()
        if any(w in q for w in ["ingreso", "venta", "facturaci", "recaudo"]):
            route = "ingresos"
        elif any(w in q for w in ["costo", "gasto", "rentab"]):
            route = "costos"
        elif any(w in q for w in ["solicitud", "ticket", "servicio"]):
            route = "solicitudes"
        else:
            route = "chitchat"

    state["route"] = route
    return state


def sql_agent_node(state: GraphState) -> GraphState:
    """Genera SQL sobre las tablas permitidas."""
    question = state["question"]
    route = state["route"]

    system_prompt = f"""
    Eres un generador de SQL experto en MariaDB.

    SOLO puedes usar estas tablas:
    {', '.join(ALLOWED_TABLES)}

    Schema disponible:
    {schema_text}

    Reglas:
    - Devuelve SOLO el SQL limpio.
    - No uses ```sql ni ``` ni backticks.
    - No inventes tablas ni columnas.
    - Usa joins correctos.
    """

    messages = [
        SystemMessage(content=textwrap.dedent(system_prompt)),
        HumanMessage(content=question)
    ]
    sql_raw = llm.invoke(messages).content
    sql_clean = clean_sql(sql_raw)

    state["sql_query"] = sql_clean
    return state


def sql_validator_node(state: GraphState) -> GraphState:
    sql = state["sql_query"].upper()
    error = ""

    if "SELECT" not in sql or "FROM" not in sql:
        error = "El SQL generado no parece un SELECT válido."

    allowed = [t.upper() for t in ALLOWED_TABLES]
    tokens = sql.replace("\n", " ").split()

    for i, t in enumerate(tokens):
        if t in ("FROM", "JOIN") and i + 1 < len(tokens):
            candidate = tokens[i + 1].strip(" ,")
            if candidate.upper() not in allowed:
                error = f"Tabla no permitida o mal escrita: {candidate}"
                break

    state["error"] = error
    return state


def sql_executor_node(state: GraphState) -> GraphState:
    """Ejecuta SQL seguro."""
    sql = state["sql_query"]

    if not sql.strip():
        state["error"] = "SQL vacío."
        return state

    try:
        cleaned_sql = clean_sql(sql)
        result = sql_db.run(cleaned_sql)

        # convertir DECIMAL → float
        if isinstance(result, list):
            result = safe_rows(result)

        state["result"] = result
        state["error"] = ""
    except Exception as e:
        state["result"] = []
        state["error"] = f"Error al ejecutar SQL: {e}"

    return state


def analyst_agent_node(state: GraphState) -> GraphState:
    question = state["question"]
    result = state["result"]
    error = state["error"]

    if error:
        system_prompt = "Explica el error de forma simple."
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=error),
        ]
        exp = llm.invoke(messages).content
        state["result"] = {"type": "error", "message": exp}
        return state

    system_prompt = """
    Eres un analista de BI.
    Resume resultados SQL de forma clara.
    No inventes datos.
    """

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=f"Pregunta: {question}\nResultado JSON: {json.dumps(result, default=str)}"
        ),
    ]
    answer = llm.invoke(messages).content

    state["result"] = {"type": "ok", "answer": answer, "rows": result}
    return state


def chitchat_agent_node(state: GraphState) -> GraphState:
    question = state["question"]

    system_prompt = """
    Eres un asistente conversacional experto en analítica y BI.
    Responde en español.
    """

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=question),
    ]
    ans = llm.invoke(messages).content

    state["result"] = {"type": "chat", "answer": ans}
    return state


# ==========================
# 4. Construcción del Grafo
# ==========================

builder = StateGraph(GraphState)

builder.add_node("router", router_node)
builder.add_node("sql_agent", sql_agent_node)
builder.add_node("sql_validator", sql_validator_node)
builder.add_node("sql_executor", sql_executor_node)
builder.add_node("analyst_agent", analyst_agent_node)
builder.add_node("chitchat_agent", chitchat_agent_node)

builder.set_entry_point("router")


def _route_from_router(state: GraphState) -> str:
    return "to_chitchat" if state["route"] == "chitchat" else "to_sql"


builder.add_conditional_edges(
    "router",
    _route_from_router,
    {
        "to_chitchat": "chitchat_agent",
        "to_sql": "sql_agent",
    },
)

builder.add_edge("sql_agent", "sql_validator")


def _check_validation(state: GraphState) -> str:
    return "to_analyst" if state["error"] else "to_exec"


builder.add_conditional_edges(
    "sql_validator",
    _check_validation,
    {
        "to_analyst": "analyst_agent",
        "to_exec": "sql_executor",
    },
)

builder.add_edge("sql_executor", "analyst_agent")
builder.add_edge("chitchat_agent", END)
builder.add_edge("analyst_agent", END)

graph_app = builder.compile()


def run_graph(question: str) -> Dict[str, Any]:
    initial: GraphState = {
        "question": question,
        "route": "chitchat",
        "sql_query": "",
        "result": [],
        "error": "",
    }
    return graph_app.invoke(initial)
