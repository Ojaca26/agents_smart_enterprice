from langgraph.graph import StateGraph, END
from agents import sql_agent, analyst_agent, audit_agent, orchestrator_agent

def build_langgraph():
    """
    Construye el grafo principal de agentes LangGraph
    para el DataCenter empresarial (IANA OML).
    """
    # Crear grafo con esquema genérico
    graph = StateGraph(state_schema=dict)

    # --- Registrar nodos (agentes) ---
    graph.add_node("orchestrator", orchestrator_agent())
    graph.add_node("sql_agent", sql_agent())
    graph.add_node("analyst_agent", analyst_agent())
    graph.add_node("audit_agent", audit_agent())

    # --- Definir relaciones entre nodos ---
    graph.add_edge("orchestrator", "sql_agent")
    graph.add_edge("orchestrator", "analyst_agent")
    graph.add_edge("orchestrator", "audit_agent")

    # --- Cierre de flujo ---
    graph.add_edge("sql_agent", END)
    graph.add_edge("analyst_agent", END)
    graph.add_edge("audit_agent", END)

    # ✅ Definir el punto de entrada (entrypoint)
    graph.set_entrypoint("orchestrator")

    # Compilar el grafo para ejecución
    return graph.compile()


def export_graph_mermaid(graph):
    """
    Genera un diagrama visual en formato Mermaid
    que muestra las conexiones entre agentes.
    """
    try:
        mermaid_code = graph.get_graph().draw_mermaid()
        return mermaid_code
    except Exception as e:
        return f"⚠️ Error al generar Mermaid: {e}"
