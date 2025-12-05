# graph.py
from langgraph.graph import StateGraph, END
from graph_nodes import (
    AgentState,
    analysis_and_llm_node,
    status_router_node,
    chef_feedback_node,
    append_data_node,
    communication_node,
    router_edge,
)

def build_graph():
    """
    Builds and returns the compiled LangGraph workflow
    matching the exact logic in the main script.
    """
    workflow = StateGraph(AgentState)

    # === Add all nodes ===
    workflow.add_node("analysis", analysis_and_llm_node)
    workflow.add_node("router", status_router_node)
    workflow.add_node("chef_feedback_gen", chef_feedback_node)
    workflow.add_node("append_ignore", append_data_node)
    workflow.add_node("append_pending", append_data_node)
    workflow.add_node("append_approved", append_data_node)   # Still used for data append simulation
    workflow.add_node("send_message", communication_node)

    # === Entry point ===
    workflow.set_entry_point("analysis")

    # === Static edges ===
    workflow.add_edge("analysis", "router")

    # === Conditional routing from router ===
    workflow.add_conditional_edges(
        "router",
        router_edge,
        {
            "append_ignore": "append_ignore",
            "append_pending": "append_pending",
            "append_approved": "append_approved",   # This is the correct path for Approved by Manager
        }
    )

    # === Final paths ===
    workflow.add_edge("append_ignore", END)
    workflow.add_edge("append_pending", END)

    # Approved by Manager path: append → generate chef feedback → send message → end
    workflow.add_edge("append_approved", "chef_feedback_gen")
    workflow.add_edge("chef_feedback_gen", "send_message")
    workflow.add_edge("send_message", END)

    return workflow.compile()