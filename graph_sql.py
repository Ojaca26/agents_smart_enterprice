# graph_sql.py
from __future__ import annotations

from typing import TypedDict, Literal, Any, Dict

from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from db import get_sql_database, load_schema_text, ALLOWED_TABLES

import json
import textwrap

def clean_sql(query: str) -> str:
    """Limpia SQL quitando formato Markdown, backticks y espacios basura."""
    if not query:
        return ""
    q = query.replace("```sql", "")
    q = q.replace("```", "")
    q = q.replace("`", "")
    return q.strip()

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
# 3. Nodos (agentes)
# ==========================

def router_node(state: GraphState) -> GraphState:
    """Clasifica la intención de la pregunta."""
    question = state["question"]

    system_prompt = """
    Eres un clasificador de intención para un asistente de analítica de negocios
    que trabaja con datos de una empresa de servicios/logística.

    Debes clasificar cada pregunta del usuario en EXACTAMENTE una de estas categorías:
    - ingresos      → preguntas sobre ventas, facturación, recaudo, ingresos
    - costos        → preguntas sobre costos, gastos, margen, rentabilidad
    - solicitudes   → preguntas sobre tiempos de atención, solicitudes, servicios, tickets
    - mixto         → si mezcla claramente varios de los anteriores
    - chitchat      → saludo, explicación general, cosas sin número específico

    Responde SOLO un JSON con la forma:
    {"route": "ingresos"}  # o costos, solicitudes, mixto, chitchat
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
    except Exception:
        q = question.lower()
        if any(w in q for w in ["ingreso", "venta", "facturaci", "recaudo"]):
            route = "ingresos"
        elif any(w in q for w in ["costo", "gasto", "rentab"]):
            route = "costos"
        elif any(w in q for w in ["solicitud", "ticket", "servicio", "tiempo de espera"]):
            route = "solicitudes"
        else:
            route = "chitchat"

    state["route"] = route  # type: ignore
    return state


def sql_agent_node(state: GraphState) -> GraphState:
    """Genera SQL sobre las vistas permitidas, sin ejecutarlo."""
    question = state["question"]
    route = state["route"]

    system_prompt = f"""
    Eres un generador de SQL experto para MariaDB.

    SOLO puedes usar las siguientes vistas:
    {', '.join(ALLOWED_TABLES)}

    A continuación tienes una descripción de las vistas y sus columnas:

    {schema_text}

    Reglas IMPORTANTES:
    - NO inventes tablas ni vistas.
    - NO inventes columnas.
    - Usa nombres exactamente como están en el schema.
    - Usa joins lógicos entre ID_Empresa, ID_Concepto, ID_Ubicacion, ID_Fecha, etc.
    - Debes devolver ÚNICAMENTE un bloque de SQL válido.
    - No agregues texto explicativo antes ni después del SQL.
    - No uses LIMIT a menos que el usuario lo pida.

    La categoría de la pregunta es: {route}.
    """

    messages = [
        SystemMessage(content=textwrap.dedent(system_prompt)),
        HumanMessage(content=question),
    ]
    sql = llm.invoke(messages).content.strip()

    state["sql_query"] = sql
    return state


def sql_validator_node(state: GraphState) -> GraphState:
    """Valida sintaxis básica y que las tablas usadas estén permitidas."""
    sql = state["sql_query"]
    upper = sql.upper()

    error = ""

    if "SELECT" not in upper or "FROM" not in upper:
        error = "El SQL generado no parece una sentencia SELECT válida."

    # Validar que solo use tablas conocidas (muy simple pero útil)
    allowed_upper = [t.upper() for t in ALLOWED_TABLES]
    tokens = upper.replace("\n", " ").split()
    for i, token in enumerate(tokens):
        if token in ("FROM", "JOIN"):
            if i + 1 < len(tokens):
                candidate = tokens[i + 1].strip(" ,`")
                # Manejar alias tipo nombre_tabla AS X
                if candidate.upper() not in allowed_upper:
                    error = f"Se encontró una tabla no permitida o mal escrita: '{candidate}'."
                    break

    state["error"] = error
    return state


def sql_executor_node(state: GraphState) -> GraphState:
    """Ejecuta el SQL en la base de datos."""
    sql = state["sql_query"]

    if not sql.strip():
        state["error"] = "No hay SQL para ejecutar."
        state["result"] = []
        return state

    try:
        cleaned_sql = clean_sql(sql)
        state["sql_query"] = cleaned_sql
        
        result = sql_db.run(cleaned_sql)
        state["result"] = result
        state["error"] = ""
    except Exception as e:
        state["result"] = []
        state["error"] = f"Error al ejecutar SQL: {e}"

    return state


def analyst_agent_node(state: GraphState) -> GraphState:
    """Toma la pregunta y el resultado y genera una respuesta entendible para negocio."""
    question = state["question"]
    result = state.get("result", [])
    error = state.get("error", "")

    if error:
        system_prompt = """
        Eres un analista de datos que explica errores de forma clara
        a un usuario de negocio. Responde en pocas frases, en español.
        """
        messages = [
            SystemMessage(content=textwrap.dedent(system_prompt)),
            HumanMessage(content=f"Hubo este error al procesar la consulta: {error}"),
        ]
        explanation = llm.invoke(messages).content
        state["result"] = {"type": "error", "message": explanation}
        return state

    # preview para no explotar tokens
    preview = result
    if isinstance(result, list) and len(result) > 20:
        preview = result[:20]

    system_prompt = """
    Eres un analista de inteligencia de negocios.
    Explica el resultado de una consulta SQL en términos de KPIs,
    totales, promedios o tendencias. Responde en español, breve y claro.
    No inventes datos que no estén en el resultado.
    """
    messages = [
        SystemMessage(content=textwrap.dedent(system_prompt)),
        HumanMessage(
            content=(
                f"Pregunta del usuario: {question}\n\n"
                f"Resultado (primeras filas en JSON): {json.dumps(preview, default=str)}"
            )
        ),
    ]
    answer = llm.invoke(messages).content
    state["result"] = {"type": "ok", "answer": answer, "rows": preview}
    return state


def chitchat_agent_node(state: GraphState) -> GraphState:
    """Responde preguntas generales que no requieren SQL."""
    question = state["question"]
    system_prompt = """
    Eres un asistente conversacional de DataInsights, especializado en explicar
    temas de analítica, inteligencia de negocios y uso de IA para empresas.
    Responde en español, tono profesional pero cercano.
    Si crees que el usuario podría beneficiarse de una consulta a la base de datos,
    sugiere cómo formular una pregunta de negocio (ej: ingresos por año, costos por zona, etc.).
    """
    messages = [
        SystemMessage(content=textwrap.dedent(system_prompt)),
        HumanMessage(content=question),
    ]
    answer = llm.invoke(messages).content
    state["result"] = {"type": "chat", "answer": answer}
    state["error"] = ""
    return state


# ==========================
# 4. Construcción del grafo
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
    if state["route"] == "chitchat":
        return "to_chitchat"
    return "to_sql"


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
    if state.get("error"):
        return "to_analyst"
    return "to_exec"


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
    """Función de alto nivel para usar desde Streamlit u otros módulos."""
    initial: GraphState = {
        "question": question,
        "route": "chitchat",  # valor inicial dummy, el router lo ajusta
        "sql_query": "",
        "result": [],
        "error": "",
    }
    final_state = graph_app.invoke(initial)
    return final_state
