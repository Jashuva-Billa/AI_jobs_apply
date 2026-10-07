# 🚀 Antigravity AI — Agentic Job Search & Application Platform (ChatGPT Web + MCP)

An enterprise-grade, autonomous job application platform designed for **ChatGPT Web + Model Context Protocol (MCP)** integration.

> [!IMPORTANT]
> **Zero LLM API Dependency:** The backend does **NOT** require OpenAI API (`OPENAI_API_KEY`) or Google Gemini API (`GEMINI_API_KEY`) credentials. **ChatGPT Web** serves as the AI reasoning and conversational interface, while the backend provides deterministic data persistence, multi-source job discovery, 7-factor matching, recruiter verification, idempotency protection, and Human-in-the-Loop (HITL) execution.

---

## 📌 Target Architecture

```text
                    CHATGPT WEB (AI Reasoning Layer)
                                 │
                                 │ Model Context Protocol (MCP SSE)
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

### Division of Responsibilities:
- **ChatGPT Web:** Understanding user natural language directives, reasoning over search parameters, deciding which MCP tools to invoke, analyzing matches, explaining recommendations, preparing outreach copy, and requesting human approval.
- **Backend / MCP Server:** Data persistence, 7-factor deterministic match scoring, job retrieval & normalization, recruiter domain verification, canonical idempotency (`{candidate_id}_{job_id}_apply`), MySQL 1062 duplicate error handling, audit logging, and authorized email dispatch.

---

## 🛠️ Complete Ecosystem & Startup Guide

To run the complete platform with both the Streamlit operations dashboard and ChatGPT Web MCP integration, start these services:

| Service | Script / Command | Port / URL | Purpose |
| :--- | :--- | :--- | :--- |
| **1. FastAPI Backend** | `uvicorn app.main:app --port 8000` | `http://localhost:8000` | REST API, data persistence, deterministic matching |
| **2. Streamlit Dashboard** | `streamlit run streamlit_app.py --server.port 8501` | `http://localhost:8501` | 8-Tab operations dashboard & visual review center |
| **3. Job Platform MCP Server** | `python mcp-servers/job-platform/server.py` | `http://localhost:8001` | MCP SSE server exposing 22 business tools |
| **4. Ngrok Tunnel** | `ngrok http 8001` | `https://<subdomain>.ngrok-free.dev` | Secure public HTTPS tunnel for ChatGPT Web |

You can also launch all services at once using [`start_services.bat`](file:///c:/Users/Jashuva/Desktop/AI_jobs_apply/start_services.bat).

---

## 🤖 ChatGPT Web + MCP Integration Setup

1. Open [ChatGPT Web](https://chatgpt.com).
2. Go to **Settings** ➔ **Apps & Connectors** (or **Custom GPTs / Actions**).
3. Click **Add Custom MCP Server / Connector**.
4. Configure the connection:
   - **Server Name:** `job-platform-mcp`
   - **Server URL:** `https://<your-subdomain>.ngrok-free.dev/sse` (e.g., `https://celery-ecosystem-suspense.ngrok-free.dev/sse`)
   - **Authentication:** `None` (Development mode)
5. Click **Connect & Scan Tools**.
   ChatGPT will automatically discover and register all **22 business tools**.

---

## 🧰 Registered MCP Tools Reference (22 Tools)

| Tool Name | Type | Action / Safety | Description |
| :--- | :--- | :--- | :--- |
| `get_candidate_profile` | Candidate | `READ-ONLY` | Retrieves candidate factual profile, technical skills, and experience from SQL. |
| `get_candidate_resume` | Candidate | `READ-ONLY` | Returns raw and parsed resume text. |
| `update_candidate_profile` | Candidate | `WRITE` | Updates candidate profile fields in SQL. |
| `search_jobs` | Job Search | `DISCOVERY` | Searches live jobs across RemoteOK, Arbeitnow, and DuckDuckGo up to 100+ jobs. |
| `get_search_run` | Persistence | `READ-ONLY` | Retrieves durable `SearchRun` status and processing counters from SQL. |
| `get_search_results` | Persistence | `READ-ONLY` | Fetches discovered jobs and match records for a search run. |
| `get_job_details` | Job Search | `READ-ONLY` | Retrieves comprehensive details for a specific job. |
| `match_jobs` | Matching | `COMPUTATION` | Deterministic 7-factor scoring (Skills 30%, Exp 20%, Role 20%, Loc 15%, Cloud 5%, Edu 5%, Domain 5%). |
| `find_recruiter` | Recruiter | `DISCOVERY` | Discovers verified public recruiter contacts without fabricating emails. |
| `prepare_application` | Application | `WRITE / HITL` | Generates tailored package and creates `PENDING` approval record with canonical idempotency. |
| `prepare_applications_batch` | Application | `BATCH` | Parallel application package generation under bounded concurrency (max 10). |
| `get_application` | Application | `READ-ONLY` | Retrieves a single application package and details by application ID. |
| `get_applications` | Application | `READ-ONLY` | Queries persisted application records with optional status filtering. |
| `get_application_status` | Application | `READ-ONLY` | Read-only application and approval audit status checker. |
| `get_pending_approvals` | HITL Approval | `READ-ONLY` | Retrieves pending application approval requests awaiting human review. |
| `approve_application` | HITL Approval | `ACTION` | Approves a specific application by ID and dispatches authorized outreach. |
| `reject_application` | HITL Approval | `WRITE` | Rejects a specific application by ID. |
| `approve_application_batch` | HITL Approval | `ACTION` | Batch approves multiple applications by ID. |
| `approve_applications` | HITL Approval | `ACTION` | Approves list of application approval IDs upon explicit confirmation. |
| `reject_applications` | HITL Approval | `WRITE` | Rejects list of application approval IDs in SQL. |
| `prepare_recruiter_outreach` | Outreach | `READ-ONLY` | Prepares structured email and LinkedIn message copy for an application. |
| `send_approved_email` | Outreach | `ACTION` | Sends recruiter email **ONLY** for `APPROVED` applications (Idempotent). |
| `prepare_linkedin_outreach` | Outreach | `READ-ONLY` | Generates 100% compliant LinkedIn copy and direct recruiter profile search links. |
| `get_analytics` | Analytics | `READ-ONLY` | Retrieves comprehensive application metrics and conversion funnel statistics. |

---

## 🛡️ Deterministic Matching & Human Governance

### 1. Deterministic 7-Factor Matching Model
Match scores are strictly computed by the backend:
- **Core Skills:** 30%
- **Years of Experience:** 20%
- **Role Relevance:** 20%
- **Location / Remote Policy:** 15%
- **Cloud Proficiency:** 5%
- **Education Alignment:** 5%
- **Domain Specialization:** 5%

### 2. Canonical Idempotency & Database Integrity
Applications use the strict canonical idempotency key:
```text
{candidate_id}_{job_id}_apply
```
If an application already exists or a MySQL 1062 duplicate key conflict occurs, the transaction rolls back gracefully and reuses the existing record without HTTP 500 crashes.

### 3. Mandatory Human-in-the-Loop (HITL)
- Applications and outreach emails are **NEVER** submitted automatically.
- Application packages remain in `PENDING` status until the user explicitly calls `approve_application` or confirms through the Streamlit Approval Center.
- LinkedIn outreach remains 100% compliant: generates personalized message copy with 1-click deep links, without browser automation, Selenium, or cookie scraping.

---

## 🖥️ Streamlit Operations Dashboard (8 Tabs)

The Streamlit UI ([`streamlit_app.py`](file:///c:/Users/Jashuva/Desktop/AI_jobs_apply/streamlit_app.py)) serves as an operational dashboard:
1. **👤 Candidate Profile:** Factual candidate profile and resume ingestion.
2. **🔍 Job Search:** Search trigger and execution overview.
3. **💼 Search Results:** Evaluated jobs with 7-factor score breakdowns.
4. **📊 Applications:** Visual Kanban pipeline across lifecycle stages.
5. **🛡️ Human Intervention / Approval Center:** Individual & batch approval review bar.
6. **👥 Recruiters:** Verified recruiter contacts with source evidence citations.
7. **📈 Analytics:** Telemetry, KPIs, and match score distribution.
8. **⚡ System / MCP Status:** Real-time health status of MCP Server, SQL Database, Email, and LinkedIn.

---

## 🧪 Running Automated Tests

Run the full automated test suite covering all services, MCP tools, and idempotency:

```powershell
pytest backend/tests/ -v
```

All 72+ tests pass with zero external LLM API dependencies.
