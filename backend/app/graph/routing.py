from typing import Literal
from app.graph.state import JobApplicationState

def should_continue_after_match(state: JobApplicationState) -> Literal["discover_recruiters", "track_application"]:
    ranked_jobs = state.get("ranked_jobs", [])
    if ranked_jobs and ranked_jobs[0].get("match", {}).get("overall_score", 0) >= 60.0:
        return "discover_recruiters"
    return "track_application"

def check_approval_gate(state: JobApplicationState) -> Literal["execute_approved_action", "track_application"]:
    if state.get("approval_status") == "APPROVED":
        return "execute_approved_action"
    return "track_application"
