from langgraph.graph import Graph
from agents.sql_agent import sql_agent
from agents.analyst_agent import analyst_agent
from agents.audit_agent import audit_agent
from agents.orchestrator_agent import orchestrator_agent

def build_langgraph():
    graph = Graph()
    graph.add_node("sql_agent", sql_agent)
    graph.add_node("analyst_agent", analyst_agent)
    graph.add_node("audit_agent", audit_agent)
    graph.add_node("orchestrator", orchestrator_agent)

    graph.add_edge("orchestrator", "sql_agent")
    graph.add_edge("orchestrator", "analyst_agent")
    graph.add_edge("orchestrator", "audit_agent")

    return graph

def export_graph_mermaid(graph):
    try:
        mermaid = graph.get_graph().draw_mermaid()
        return mermaid
    except Exception as e:
        return f"Error al generar Mermaid: {e}"