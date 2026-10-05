# Agent Workflow & LangGraph State Machine

The multi-agent execution uses **LangGraph StateGraph** with typed states, checkpoints, and interruptible human-in-the-loop gates.

## Typed State Schema (`JobApplicationState`)

```python
class JobApplicationState(TypedDict):
    run_id: str
    user_prompt: str
    search_criteria: Dict[str, Any]
    candidate_profile: Dict[str, Any]
    discovered_jobs: List[Dict[str, Any]]
    normalized_jobs: List[Dict[str, Any]]
    deduplicated_jobs: List[Dict[str, Any]]
    matched_jobs: List[Dict[str, Any]]
    ranked_jobs: List[Dict[str, Any]]
    selected_job: Optional[Dict[str, Any]]
    recruiter: Optional[Dict[str, Any]]
    application_package: Optional[Dict[str, Any]]
    outreach: Optional[Dict[str, Any]]
    approval_required: bool
    approval_status: str
    errors: List[str]
    current_step: str
    events: List[Dict[str, Any]]
```

## Workflow Progression

1. `START` -> `parse_prompt`: Analyzes natural language instructions into `SearchCriteria`.
2. `load_candidate`: Retrieves candidate's factual profile.
3. `search_jobs`: Executes multi-query search strategies.
4. `normalize_jobs`: Cleans and normalizes remote/location formats.
5. `match_jobs`: Applies 7-factor weighted scoring.
6. `rank_jobs`: Filters roles >= 75% match threshold.
7. `discover_recruiters`: Locates public talent contacts.
8. `prepare_application`: Generates tailored resume, cover letter, and safe answers.
9. `prepare_outreach`: Drafts personalized email & LinkedIn copy.
10. `human_approval_gate`: Pauses workflow and notifies human user for explicit decision.
11. `execute_approved_action`: Dispatches authorized email with idempotency protection.
12. `track_application` -> `END`: Records final state in PostgreSQL.
