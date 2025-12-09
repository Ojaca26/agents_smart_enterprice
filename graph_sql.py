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
    """
    Convierte tipos de datos complejos (Decimal, Date/Time objects, etc.) 
    a tipos seguros (float/str) para Streamlit.
    """
    safe_list = []
    
    # Asegurarse de que 'rows' es iterable
    if not isinstance(rows, list):
        rows = [rows]

    for row in rows:
        safe_row = {}
        for k, v in row.items():
            if isinstance(v, decimal.Decimal):
                # Decimal a Float (maneja Valores Monetarios)
                safe_row[k] = float(v)
            elif v is None:
                # None a string vacío
                safe_row[k] = ""
            elif isinstance(v, (int, float, str)):
                # Tipos primitivos seguros (int, float, str), los mantenemos
                safe_row[k] = v
            else:
                # Si es un objeto complejo del driver (Date, Time, BigInt, etc.), lo forzamos a cadena.
                try:
                    safe_row[k] = str(v)
                except Exception:
                    safe_row[k] = f"Error de Tipo: {type(v).__name__}"
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
# graph_sql.py (REEMPLAZAR la función router_node)

def router_node(state: GraphState) -> GraphState:
    """Clasifica la intención de la pregunta, con lógica de fallback robusta."""
    question = state["question"]

    system_prompt = """
    Eres un clasificador de intención para un asistente de analítica de negocios.
    Devuelve SOLO un objeto JSON con la clave 'route'.
    Categorías:
    - ingresos (Preguntas sobre Valor_Facturado, ventas, facturación)
    - costos (Preguntas sobre Costo_Total_Nomina, gastos)
    - solicitudes (Preguntas sobre Tiempo_Espera, tickets, servicios, ubicación)
    - mixto (Preguntas que requieren más de una tabla de hecho)
    - chitchat (Saludos, preguntas de conocimiento general o fuera de los datos)
    """

    messages = [
        SystemMessage(content=textwrap.dedent(system_prompt)),
        HumanMessage(content=question),
    ]
    raw = llm.invoke(messages).content

    route: str = "chitchat"
    try:
        # 1. Intenta parsear el JSON limpio del LLM
        data = json.loads(raw)
        value = data.get("route", "chitchat")
        if value in ["ingresos", "costos", "solicitudes", "mixto", "chitchat"]:
            route = value
    except:
        # 2. Lógica de Fallback Rápida y Robusta (Soluciona el problema de chitchat)
        q = question.lower()
        
        # Ruta Ingresos (con métricas clave)
        if any(w in q for w in ["ingreso", "venta", "facturaci", "recaudo", "valor_facturado", "margen", "rentabilidad"]):
            route = "ingresos"
        
        # Ruta Costos (con métricas clave, incluyendo 'promedio')
        elif any(w in q for w in ["costo", "gasto", "nomina", "costo_total", "costo_promedio"]):
            route = "costos"
            
        # Ruta Solicitudes (con métricas de tiempo y ubicación)
        elif any(w in q for w in ["solicitud", "ticket", "servicio", "tiempo", "espera", "ubicación", "kilos", "cajas", "placa"]):
            route = "solicitudes"
        
        # Ruta Mixto (si pregunta sobre ingresos Y costos)
        elif any(w in q for w in ["ingreso", "costo"]) and any(w in q for w in ["empresa", "año"]):
            route = "mixto"
        
        else:
            route = "chitchat"

    state["route"] = route
    return state


def sql_agent_node(state: GraphState) -> GraphState:
    """Genera SQL con reglas de esquema actualizadas (fechas DATE, CASTs, Costo_Total_Nomina)."""
    question = state["question"]
    route = state["route"]

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


def sql_validator_node(state: GraphState) -> GraphState:
    """Valida el SQL generado por seguridad y coherencia."""
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

    # Validación de JOINS entre hechos (si no es ruta 'mixto')
    if state["route"] != "mixto":
        fact_tables = ["FACT_COSTOS", "FACT_INGRESOS", "FACT_SOLICITUDES"]
        found_facts = [t for t in fact_tables if t in sql]
        
        if len(found_facts) > 1:
            error = (
                f"La pregunta '{state['question']}' ha generado un JOIN entre "
                f"múltiples tablas de hecho ({', '.join(found_facts)}). "
                "Genera un SQL que use SOLO una tabla de hecho."
            )
    
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
        # LangChain's SQLDatabase.run() devuelve una lista de dicts
        result = sql_db.run(cleaned_sql)

        # Aplicar limpieza de tipos para evitar errores de Streamlit/Pandas
        if isinstance(result, list):
            result = safe_rows(result)

        state["result"] = result
        state["error"] = ""
    except Exception as e:
        state["result"] = []
        state["error"] = f"Error al ejecutar SQL: {e}"

    return state


def analyst_agent_node(state: GraphState) -> GraphState:
    """Transforma el resultado SQL en una respuesta de negocio en Markdown."""
    question = state["question"]
    result = state["result"]
    error = state["error"]

    if error:
        system_prompt = "Eres un asistente técnico. Explica el error de forma simple, pidiendo al usuario que reformule la pregunta o revise el esquema. Nunca muestres el SQL generado."
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=error),
        ]
        exp = llm.invoke(messages).content
        state["result"] = {"type": "error", "message": exp}
        return state

    system_prompt = """
    Eres un analista de BI. Tu objetivo es transformar los datos JSON resultantes de una consulta SQL en una respuesta de negocio clara, concisa y veraz.

    Reglas de Formato:
    1.  **Siempre inicia con una frase resumen, usando negritas para destacar valores importantes.**
    2.  **Si el resultado tiene más de una fila y menos de 10, formatea la información CLAVE en una tabla Markdown.** Usa nombres de columna en español claro (ej: 'Anio' debe ser 'Año').
    3.  **Si el resultado es un único valor (ej: un total), preséntalo en negrita y como un encabezado H3.**
    4.  **No inventes datos. Si el resultado es vacío, dilo.**
    """

    messages = [
        SystemMessage(content=textwrap.dedent(system_prompt)),
        HumanMessage(
            content=f"Pregunta: {question}\nResultado JSON: {json.dumps(result, default=str)}"
        ),
    ]
    answer = llm.invoke(messages).content

    state["result"] = {"type": "ok", "answer": answer, "rows": result}
    return state


def chitchat_agent_node(state: GraphState) -> GraphState:
    """Maneja preguntas conversacionales."""
    question = state["question"]

    system_prompt = """
    Eres un asistente conversacional experto en analítica y BI.
    Responde en español, de forma amigable.
    """

    messages = [
        SystemMessage(content=textwrap.dedent(system_prompt)),
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
