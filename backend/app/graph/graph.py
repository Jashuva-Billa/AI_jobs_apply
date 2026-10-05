from langgraph.graph import StateGraph, END
from app.graph.state import JobApplicationState
from app.graph.nodes import (
    parse_prompt_node,
    load_candidate_node,
    search_jobs_node,
    normalize_jobs_node,
    match_jobs_node,
    rank_jobs_node,
    discover_recruiters_node,
    prepare_application_node,
    prepare_outreach_node,
    execute_approved_action_node,
    track_application_node
)
from app.graph.routing import should_continue_after_match, check_approval_gate

def build_job_application_graph():
    """Assembles the LangGraph multi-agent workflow."""
    workflow = StateGraph(JobApplicationState)

    # Add Nodes
    workflow.add_node("parse_prompt", parse_prompt_node)
    workflow.add_node("load_candidate", load_candidate_node)
    workflow.add_node("search_jobs", search_jobs_node)
    workflow.add_node("normalize_jobs", normalize_jobs_node)
    workflow.add_node("match_jobs", match_jobs_node)
    workflow.add_node("rank_jobs", rank_jobs_node)
    workflow.add_node("discover_recruiters", discover_recruiters_node)
    workflow.add_node("prepare_application", prepare_application_node)
    workflow.add_node("prepare_outreach", prepare_outreach_node)
    workflow.add_node("execute_approved_action", execute_approved_action_node)
    workflow.add_node("track_application", track_application_node)

    # Connect Edges
    workflow.set_entry_point("parse_prompt")
    workflow.add_edge("parse_prompt", "load_candidate")
    workflow.add_edge("load_candidate", "search_jobs")
    workflow.add_edge("search_jobs", "normalize_jobs")
    workflow.add_edge("normalize_jobs", "match_jobs")
    workflow.add_edge("match_jobs", "rank_jobs")

    workflow.add_conditional_edges(
        "rank_jobs",
        should_continue_after_match,
        {
            "discover_recruiters": "discover_recruiters",
            "track_application": "track_application"
        }
    )

    workflow.add_edge("discover_recruiters", "prepare_application")
    workflow.add_edge("prepare_application", "prepare_outreach")
    
    # After preparing outreach, the system pauses at the human approval gate
    # In interactive execution, if approved, it moves to execute_approved_action
    workflow.add_conditional_edges(
        "prepare_outreach",
        check_approval_gate,
        {
            "execute_approved_action": "execute_approved_action",
            "track_application": "track_application"
        }
    )

    workflow.add_edge("execute_approved_action", "track_application")
    workflow.add_edge("track_application", END)

    return workflow.compile()

job_application_graph = build_job_application_graph()
