from langgraph.graph import StateGraph, END
from graph_nodes import AgentState, analysis_and_llm_node, status_router_node, chef_feedback_node, append_data_node, communication_node, router_edge

def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("analysis", analysis_and_llm_node)
    workflow.add_node("router", status_router_node)
    workflow.add_node("chef_feedback_gen", chef_feedback_node)
    workflow.add_node("append_ignore", append_data_node)
    workflow.add_node("append_pending", append_data_node)
    workflow.add_node("append_approved", append_data_node)
    workflow.add_node("send_message", communication_node)
    
    workflow.set_entry_point("analysis")
    
    workflow.add_edge("analysis", "router")
    workflow.add_conditional_edges("router", router_edge,
        {
            'append_ignore': 'append_ignore',
            'append_pending': 'append_pending',
            'chef_feedback_gen': 'chef_feedback_gen',
            'end_path': END,
        }
    )
    workflow.add_edge("append_ignore", END)
    workflow.add_edge("append_pending", "send_message")
    workflow.add_edge("chef_feedback_gen", "send_message")
    workflow.add_edge("send_message", END)
    
    return workflow.compile()