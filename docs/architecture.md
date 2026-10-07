# System Architecture: ChatGPT Web + Model Context Protocol (MCP)

## 1. Architectural Overview

```text
                    CHATGPT WEB (AI Reasoning Layer)
                                 │
                                 │ Model Context Protocol (SSE / Streamable HTTP)
                                 ▼
                    JOB PLATFORM MCP SERVER (Port 8001)
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
           FastAPI            SQL DB          External Tools
         (Port 8000)      (Single Source)           │
              │                               ┌─────┴─────┐
              ▼                               ▼           ▼
         Job Search                         Email     LinkedIn
      (RemoteOK, Arbeitnow, Web)           (SMTP)     (Manual)
              │
              ▼
     7-Factor Match Engine (Deterministic)
              │
              ▼
      Application Engine (Canonical Idempotency)
              │
              ▼
     🛡️ MANDATORY HUMAN APPROVAL GATE (HITL)
              │
              ▼
       Approved Actions Only
```

---

## 2. Core Architectural Principles

1. **ChatGPT Web as the Intelligent Orchestration Layer:**
   ChatGPT Web interprets natural language goals, decides tool sequencing, analyzes candidate fit, prepares human reviews, and initiates authorized actions.

2. **Deterministic Backend Execution:**
   The backend provides deterministic, verifiable, and evidence-backed tools. It has zero active dependencies on `api.openai.com` or Google Gemini API.

3. **Zero LLM API Key Requirement:**
   The application operates with no `OPENAI_API_KEY` or `GEMINI_API_KEY` required.

4. **Authoritative SQL State & Canonical Idempotency:**
   - Single source of truth in SQL (MySQL / SQLite).
   - Canonical idempotency key: `{candidate_id}_{job_id}_apply`.
   - Automatic MySQL 1062 duplicate key conflict handling (transaction rollback + existing record reuse).

5. **Human-in-the-Loop (HITL) by Design:**
   Actions (such as sending emails or marking applications approved) strictly require explicit user confirmation.

---

## 3. Registered MCP Tools (22 Total)

| Tool Name | Type | Description |
|---|---|---|
| `get_candidate_profile` | Read | Retrieves candidate profile, skills, and 2.9 YoE experience from SQL. |
| `update_candidate_profile` | Write | Updates preferred roles, target locations, or skills in SQL. |
| `get_candidate_resume` | Read | Returns raw and parsed resume text. |
| `search_jobs` | Discovery | Searches live job portals (RemoteOK, Arbeitnow, DuckDuckGo) up to 100+ jobs. |
| `get_search_run` | Read | Returns durable metrics, timestamps, and current step of a search run. |
| `get_search_results` | Read | Returns paginated job search results and match scores. |
| `get_job_details` | Read | Retrieves comprehensive details for a specific job ID. |
| `match_jobs` | Compute | Deterministic 7-factor scoring (Skills 30%, Exp 20%, Role 20%, Loc 15%, Cloud 5%, Edu 5%, Domain 5%). |
| `find_recruiter` | Discovery | Discovers public, verified recruiter contacts without fabricating emails. |
| `prepare_application` | Write | Prepares factual tailored resume, cover letter, and drafts with canonical idempotency. |
| `prepare_applications_batch` | Batch/Write | Concurrently prepares application packages under bounded concurrency (max 10). |
| `get_application` | Read | Retrieves a single application package and details by application ID. |
| `get_applications` | Read | Queries persisted application records with optional status filtering. |
| `get_application_status` | Read | Retrieves aggregated persisted status, approval state, outreach delivery details, and audit history. |
| `get_pending_approvals` | Read | Fetches pending application packages awaiting human review. |
| `approve_application` | Action/Write | Approves a specific application by ID and dispatches authorized outreach. |
| `reject_application` | Action/Write | Rejects a specific application by ID. |
| `approve_application_batch` | Action/Write | Batch approves multiple applications by ID. |
| `approve_applications` | Action/Write | Approves applications in SQL upon explicit user command. |
| `reject_applications` | Action/Write | Rejects application records in SQL. |
| `prepare_recruiter_outreach` | Read | Prepares structured email and LinkedIn message copy for an application. |
| `send_approved_email` | Action/Write | Dispatches outreach email with idempotency key `candidate_id:job_id:EMAIL_OUTREACH`. |
| `prepare_linkedin_outreach` | Read/Action | Generates compliant copy and direct recruiter search URLs. |
| `get_analytics` | Read | Retrieves comprehensive application metrics and conversion funnel statistics. |
