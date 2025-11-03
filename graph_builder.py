import streamlit as st
from langgraph.graph import StateGraph
from langgraph.constants import END
from agents import sql_agent, analyst_agent, audit_agent, orchestrator_agent

def build_langgraph():
    """Construye el grafo principal de agentes LangGraph"""
    graph = StateGraph(state_schema=dict)

    graph.add_node("orchestrator", orchestrator_agent())
    graph.add_node("sql_agent", sql_agent())
    graph.add_node("analyst_agent", analyst_agent())
    graph.add_node("audit_agent", audit_agent())

    graph.add_edge("orchestrator", "sql_agent")
    graph.add_edge("orchestrator", "analyst_agent")
    graph.add_edge("orchestrator", "audit_agent")
    graph.add_edge("sql_agent", END)
    graph.add_edge("analyst_agent", END)
    graph.add_edge("audit_agent", END)

    graph.set_entry_point("orchestrator")

    return graph.compile()


def export_graph_mermaid(graph):
    """
    Genera y renderiza visualmente el diagrama LangGraph
    con soporte MermaidJS en Streamlit.
    """
    try:
        mermaid_code = graph.get_graph().draw_mermaid()

        # ✅ Crear HTML con soporte visual
        html = f"""
        <div class="mermaid">
        {mermaid_code}
        </div>
        <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
        </script>
        """

        # Renderizar visualmente dentro del sidebar o app
        st.components.v1.html(html, height=600, scrolling=True)

    except Exception as e:
        st.error(f"⚠️ Error al generar Mermaid: {e}")
