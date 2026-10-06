# System Architecture: ChatGPT Web + Model Context Protocol (MCP)

## 1. Architectural Evolution

### Previous Architecture (Deprecated):
```text
Streamlit ──► FastAPI ──► LangGraph ──► OpenAI Responses API (LLM) ──► OpenAI Web Search
```
*Limitations:* Hard dependency on paid OpenAI API credits (`OPENAI_API_KEY`), fragile client-side polling, and lack of conversational human intervention.

### New Architecture (Official MCP):
```text
┌─────────────────────────────────────────────────────────────┐
│                         CHATGPT WEB                         │
│             (Primary Conversational & Reasoning Agent)      │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               │ Model Context Protocol (SSE / Streamable HTTP)
                               │ (Port 8001: job-platform-mcp)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    JOB PLATFORM MCP SERVER                  │
│  ┌───────────────────────┬────────────────────────────────┐ │
│  │ 1. Candidate Tools    │ 2. Live Job Discovery          │ │
│  │ 3. 7-Factor Matching  │ 4. Recruiter Research          │ │
│  │ 5. App Preparation    │ 6. Human-in-the-Loop Approvals │ │
│  │ 7. Email & LinkedIn   │ 8. Durable Search Runs         │ │
│  └───────────────────────┴────────────────────────────────┘ │
└───────────────┬─────────────────────────────┬───────────────┘
                │                             │
                ▼                             ▼
┌───────────────────────────────┐   ┌─────────────────────────┐
│     SQL DATABASE (DURABLE)    │   │  OPERATIONS DASHBOARD   │
│ (SQLite / MySQL Async Engine) │   │     (Streamlit UI)      │
└───────────────────────────────┘   └─────────────────────────┘
```

---

## 2. Core Architectural Principles

1. **ChatGPT Web as the Intelligent Orchestration Layer:**
   ChatGPT Web interprets natural language goals, decides tool sequencing, analyzes candidate fit, prepares human reviews, and initiates authorized actions.

2. **Deterministic MCP Backend Layer:**
   The backend provides deterministic, verifiable, and evidence-backed tools. It never simulates LLM responses or hallucinates missing candidate details.

3. **Zero OpenAI API Key Dependency:**
   The application operates with `OPENAI_API_KEY=` completely empty. Live job discovery queries RemoteOK, Arbeitnow, and DuckDuckGo/Bing career pages directly.

4. **Authoritative SQL State & Durability:**
   ChatGPT context is ephemeral; the SQL database is authoritative. Every search creates a durable `SearchRun` entity tracking jobs, match scores, approval states, and idempotency keys.

5. **Human-in-the-Loop (HITL) by Design:**
   Write actions (such as sending emails or marking applications approved) strictly require an explicit user confirmation command in ChatGPT before executing.

---

## 3. Registered MCP Tools

| Tool Name | Type | Description |
|---|---|---|
| `get_candidate_profile` | Read | Retrieves candidate profile, skills, and 2.9 YoE experience from SQL. |
| `update_candidate_profile` | Write | Updates preferred roles, target locations, or skills in SQL. |
| `get_candidate_resume` | Read | Returns raw and parsed resume text. |
| `search_jobs` | Discovery | Searches live job portals (RemoteOK, Arbeitnow, DDG) up to 100+ jobs. |
| `get_search_run` | Read | Returns durable metrics, timestamps, and current step of a search run. |
| `get_search_results` | Read | Returns paginated job search results and match scores. |
| `match_jobs` | Compute/Write | Deterministic 7-factor scoring (Skills 30%, Exp 20%, Role 20%, Loc 15%, Cloud 5%, Edu 5%, Domain 5%). |
| `find_recruiter` | Discovery | Discovers public, verified recruiter contacts without fabricating emails. |
| `prepare_application` | Write | Prepares factual tailored resume, cover letter, and drafts. |
| `prepare_applications_batch` | Batch/Write | Concurrently prepares application packages under bounded concurrency (max 10). |
| `get_pending_approvals` | Read | Fetches pending application packages awaiting human review. |
| `approve_applications` | Action/Write | Approves applications in SQL upon explicit user command. |
| `reject_applications` | Action/Write | Rejects application records in SQL. |
| `send_approved_email` | Action/Write | Dispatches outreach email with idempotency key `candidate_id:job_id:EMAIL_OUTREACH`. |
| `prepare_linkedin_outreach` | Read/Action | Generates compliant copy and direct recruiter search URLs. |
