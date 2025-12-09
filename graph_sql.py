# graph_sql.py
from __future__ import annotations

from typing import TypedDict, Literal, Any, Dict
import streamlit as st # Importamos streamlit aquí para poder acceder a st.secrets

from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from db import get_sql_database, load_schema_text, ALLOWED_TABLES

import json
import textwrap
import decimal


# ==========================
# UTILS (safe_rows y clean_sql - Versiones Robustas)
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
    """Convierte tipos de datos complejos a tipos seguros (float/str) para Streamlit."""
    safe_list = []
    if not isinstance(rows, list):
        rows = [rows]

    for row in rows:
        safe_row = {}
        for k, v in row.items():
            if isinstance(v, decimal.Decimal):
                safe_row[k] = float(v)
            elif v is None:
                safe_row[k] = ""
            elif isinstance(v, (int, float, str)):
                safe_row[k] = v
            else:
                try:
                    safe_row[k] = str(v)
                except Exception:
                    safe_row[k] = f"Error de Tipo: {type(v).__name__}"
        safe_list.append(safe_row)
    return safe_list


# ==========================
# 1. LLM y BD compartidos
# ==========================
try:
    # FIX CRÍTICO: Forzamos a LangChain a leer la clave directamente de st.secrets
    # Esto soluciona el ChatGoogleGenerativeAIError
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
        google_api_key=st.secrets["GEMINI_API_KEY"],
    )
except KeyError:
    # Fallback si st.secrets no se carga (debería fallar aquí si no se corrigió secrets.toml)
    st.error("Error crítico: La variable GEMINI_API_KEY no se encontró en st.secrets.", icon="⚠️")
    llm = None # Para evitar que el código falle si el LLM es None
except Exception as e:
    st.error(f"Error al inicializar LLM: {e}", icon="⚠️")
    llm = None

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
    """Clasifica la intención de la pregunta, con lógica de fallback robusta."""
    if llm is None:
        state["error"] = "Error de API: El modelo de lenguaje no pudo inicializarse. Revise la clave GEMINI_API_KEY."
        return state
        
    question = state["question"]
    # ... (System prompt se mantiene igual)

    messages = [
        SystemMessage(content=textwrap.dedent("""
        Eres un clasificador de intención para un asistente de analítica de negocios.
        Devuelve SOLO un objeto JSON con la clave 'route'.
        Categorías:
        - ingresos (Preguntas sobre Valor_Facturado, ventas, facturación)
        - costos (Preguntas sobre Costo_Total_Nomina, gastos)
        - solicitudes (Preguntas sobre Tiempo_Espera, tickets, servicios, ubicación)
        - mixto (Preguntas que requieren más de una tabla de hecho)
        - chitchat (Saludos, preguntas de conocimiento general o fuera de los datos)
        """)),
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
        # Lógica de Fallback Rápida y Robusta (para evitar chitchat)
        q = question.lower()
        
        # ... (Lógica de clasificación robusta se mantiene igual)
        if any(w in q for w in ["ingreso", "venta", "facturaci", "recaudo", "valor_facturado", "margen", "rentabilidad"]):
            route = "ingresos"
        elif any(w in q for w in ["costo", "gasto", "nomina", "costo_total", "costo_promedio"]):
            route = "costos"
        elif any(w in q for w in ["solicitud", "ticket", "servicio", "tiempo", "espera", "ubicación", "kilos", "cajas", "placa"]):
            route = "solicitudes"
        elif any(w in q for w in ["ingreso", "costo"]) and any(w in q for w in ["empresa", "año"]):
            route = "mixto"
        else:
            route = "chitchat"

    state["route"] = route
    return state


def sql_agent_node(state: GraphState) -> GraphState:
    """Genera SQL con reglas de esquema actualizadas (fechas DATE, CASTs, Costo_Total_Nomina)."""
    if llm is None:
        state["error"] = "Error de API: El modelo de lenguaje no pudo inicializarse. Revise la clave GEMINI_API_KEY."
        return state
        
    question = state["question"]
    route = state["route"]

    # ... (system prompt con todas las reglas de negocio, JOINs y fechas)
    system_prompt = f"""
    Eres un generador de SQL experto en MariaDB.

    SOLO puedes usar estas tablas:
    {', '.join(ALLOWED_TABLES)}

    Schema disponible:
    {schema_text}

    ################################################
    # REGLAS DE RELACIONES Y TIPOS CRUZADOS (JOINs) #
    ################################################
    - tbl_fact_ingresos.ID_Empresa = tbl_dim_empresa.ID_Empresa
    - tbl_fact_solicitudes.ID_Empresa = tbl_dim_empresa.ID_Empresa
    - Cuando uses tbl_fact_costos (para ID_Empresa/ID_Usuario) que son DOUBLE y se unen a BIGINT:
        - DEBES usar un CAST en el campo double para unirte: 
          JOIN tbl_dim_empresa AS de ON **CAST(fc.ID_Empresa AS SIGNED)** = de.ID_Empresa
          JOIN tbl_dim_usuario AS du ON **CAST(fc.ID_Usuario AS SIGNED)** = du.ID_USUARIO

    #########################################
    # REGLAS CRUCIALES PARA FILTROS DE TIEMPO #
    #########################################
    - Para **tbl_fact_ingresos** y **tbl_fact_costos**: La columna ID_Fecha es de tipo **DATE**.
        - Para obtener el año, usa: **YEAR(ID_Fecha) AS Anio**.
        - Para filtrar por año o mes, usa rangos de fechas: `WHERE ID_Fecha BETWEEN '2024-01-01' AND '2024-12-31'`.
    - Para **tbl_fact_solicitudes**: Usa ID_Fecha_Solicitud o ID_Fecha_Resolucion (TEXT/VARCHAR).
        - Para obtener el año, usa: **LEFT(ID_Fecha_Solicitud, 4) AS Anio**.

    #########################################
    # REGLAS DE MÉTRICAS Y NOMBRES #
    #########################################
    - La métrica de costo total a usar en tbl_fact_costos es **Costo_Total_Nomina**.
    - La métrica de tiempo de espera a usar en tbl_fact_solicitudes es **Tiempo_Espera_Minutos** o **Tiempo_Espera_Horas**.
    - Para la columna 'Año', usa el alias estricto 'Anio' (sin la 'ñ') en el SQL.

    Reglas de Generación SQL:
    1. Devuelve **SOLO el SQL limpio**, sin ```sql ni ``` ni backticks.
    2. No inventes tablas ni columnas.
    3. Siempre que sea posible, usa las **columnas precalculadas** de las tablas de dimensión para consultas simples y totales.
    """

    messages = [
        SystemMessage(content=textwrap.dedent(system_prompt)),
        HumanMessage(content=question)
    ]
    sql_raw = llm.invoke(messages).content
    sql_clean = clean_sql(sql_raw)

    state["sql_query"] = sql_clean
    return state

# (Las funciones sql_validator_node, sql_executor_node, analyst_agent_node, y chitchat_agent_node
# y la construcción del grafo se mantienen igual, ya que ya tienen las correcciones)
def sql_validator_node(state: GraphState) -> GraphState:
    sql = state["sql_query"].upper()
    error = ""
    # ... (Validación) ...
    state["error"] = error
    return state
    
def sql_executor_node(state: GraphState) -> GraphState:
    sql = state["sql_query"]
    # ... (Ejecución) ...
    return state
    
def analyst_agent_node(state: GraphState) -> GraphState:
    # ... (Formateo) ...
    return state
    
def chitchat_agent_node(state: GraphState) -> GraphState:
    # ... (Conversación) ...
    return state

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
