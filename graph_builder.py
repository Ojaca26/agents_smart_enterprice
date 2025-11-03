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
    Genera un diagrama visual colorido del flujo LangGraph
    con íconos y estilos por agente.
    """
    try:
        mermaid_code = graph.get_graph().draw_mermaid()

        # 🎨 Personalización de estilos e íconos
        style = """
        %%{init: {'theme': 'default', 'themeVariables': { 'fontFamily': 'Inter', 'primaryColor': '#1E88E5'}}}%%
        graph TD;
        classDef orchestrator fill:#1976d2,stroke:#0d47a1,stroke-width:2px,color:#fff,font-weight:bold;
        classDef analyst_agent fill:#43a047,stroke:#1b5e20,stroke-width:2px,color:#fff,font-weight:bold;
        classDef sql_agent fill:#fbc02d,stroke:#f57f17,stroke-width:2px,color:#000,font-weight:bold;
        classDef audit_agent fill:#e53935,stroke:#b71c1c,stroke-width:2px,color:#fff,font-weight:bold;
        classDef memory_agent fill:#8e24aa,stroke:#4a148c,stroke-width:2px,color:#fff,font-weight:bold;

        %% Etiquetas con emojis
        orchestrator:::orchestrator --> sql_agent:::sql_agent
        orchestrator:::orchestrator --> analyst_agent:::analyst_agent
        orchestrator:::orchestrator --> audit_agent:::audit_agent
        sql_agent:::sql_agent --> __end__
        analyst_agent:::analyst_agent --> __end__
        audit_agent:::audit_agent --> __end__

        %% Nombres más atractivos
        orchestrator["💼 Orchestrator Agent"]
        sql_agent["🧩 SQL Agent"]
        analyst_agent["📊 Analyst Agent"]
        audit_agent["🔍 Audit Agent"]
        __end__["🏁 End"]
        """

        # ✅ Crear HTML visual
        html = f"""
        <div class="mermaid">
        {style}
        </div>
        <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
        </script>
        """

        st.components.v1.html(html, height=650, scrolling=True)

    except Exception as e:
        st.error(f"⚠️ Error al generar Mermaid: {e}")
