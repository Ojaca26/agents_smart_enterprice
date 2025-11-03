import streamlit as st
from langgraph.graph import StateGraph, END
from agents import (
    AgentState, 
    orchestrator_node,
    sql_final_agent_node, 
    analyst_agent_node, 
    audit_agent_node,
    conversational_agent_node,
    sql_agent_node # Este es el que solo obtiene datos
)

# --- 1. Función de Enrutamiento ---
# Esta función lee el estado y decide el siguiente paso.
def router(state: AgentState):
    next_agent = state.get("next_agent")
    
    if next_agent == "analyst_agent" or next_agent == "audit_agent":
        # Estos agentes necesitan datos primero
        return "sql_data_getter"
    elif next_agent == "sql_agent":
        # El agente SQL puede responder directamente
        return "sql_final_agent"
    else:
        # El agente conversacional responde directamente
        return "conversational_agent"

# --- 2. Función de Enrutamiento POST-SQL ---
# Decide a dónde ir después de obtener los datos
def post_sql_router(state: AgentState):
    next_agent = state.get("next_agent")
    if next_agent == "analyst_agent":
        return "analyst_agent"
    elif next_agent == "audit_agent":
        return "audit_agent"

def build_langgraph():
    """Construye el grafo condicional de agentes LangGraph"""
    graph = StateGraph(AgentState)

    # --- 1. Añadir los Nodos ---
    # Cada nodo es una función
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("sql_data_getter", sql_agent_node) # El que solo obtiene datos
    graph.add_node("sql_final_agent", sql_final_agent_node) # El que responde al usuario
    graph.add_node("analyst_agent", analyst_agent_node)
    graph.add_node("audit_agent", audit_agent_node)
    graph.add_node("conversational_agent", conversational_agent_node)

    # --- 2. Definir los Bordes (Edges) ---
    
    # Punto de entrada
    graph.set_entry_point("orchestrator")

    # Borde condicional desde el Orquestador
    graph.add_conditional_edges(
        "orchestrator",
        router, # La función que decide
        {
            "sql_data_getter": "sql_data_getter",
            "sql_final_agent": "sql_final_agent",
            "conversational_agent": "conversational_agent"
        }
    )
    
    # Borde condicional DESPUÉS de obtener los datos
    graph.add_conditional_edges(
        "sql_data_getter",
        post_sql_router, # La función que decide
        {
            "analyst_agent": "analyst_agent",
            "audit_agent": "audit_agent"
        }
    )

    # Todos los nodos finales apuntan a END
    graph.add_edge("sql_final_agent", END)
    graph.add_edge("analyst_agent", END)
    graph.add_edge("audit_agent", END)
    graph.add_edge("conversational_agent", END)

    # Compilar el grafo
    return graph.compile()
