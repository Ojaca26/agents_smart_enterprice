# ==========================================================
# 🕸️ GRAPH BUILDER - LangGraph para IANA DataCenter
# Compatible con LangGraph >= 0.1.2
# ==========================================================

from langgraph.graph import StateGraph, END
from agents import sql_agent, analyst_agent, audit_agent, orchestrator_agent

# ==========================================================
# 🔧 Construcción del flujo de agentes
# ==========================================================
def build_langgraph():
    """
    Construye el grafo principal de agentes LangGraph
    para el DataCenter empresarial.
    """
    # Crear grafo vacío con nombre descriptivo
    graph = StateGraph(name="DataCenterGraph")

    # Registrar los nodos (cada agente es un nodo)
    graph.add_node("orchestrator", orchestrator_agent())
    graph.add_node("sql_agent", sql_agent())
    graph.add_node("analyst_agent", analyst_agent())
    graph.add_node("audit_agent", audit_agent())

    # Definir las conexiones entre nodos
    graph.add_edge("orchestrator", "sql_agent")
    graph.add_edge("orchestrator", "analyst_agent")
    graph.add_edge("orchestrator", "audit_agent")

    # Cierre de cada flujo
    graph.add_edge("sql_agent", END)
    graph.add_edge("analyst_agent", END)
    graph.add_edge("audit_agent", END)

    # Compilar el grafo para ejecución
    return graph.compile()

# ==========================================================
# 🎨 Exportar el diagrama en formato Mermaid
# ==========================================================
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
