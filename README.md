# Antigravity AI — Agentic Job Search & Application Platform

An enterprise-grade, multi-agent AI system built with **FastAPI**, **LangGraph**, **React**, and **Model Context Protocol (MCP)** that allows users to upload their resume once, specify search directives in natural language, and let autonomous agents discover, match, tailor, and prepare applications under human-in-the-loop governance.

---

## Key Features

- **Primary Intelligent Web Research (OpenAI Responses API + Web Search)**:
  - **OpenAI Responses API**: Uses `client.responses.create(...)` with the native built-in `web_search` tool (`search_context_size: high`).
  - **Live Web Intelligence**: Searches company career pages, official job postings, and credible platforms with zero hallucination.
  - **Source Evidence & Citations**: Preserves source URLs, titles, and verified attributes with explicit verification statuses (`VERIFIED`, `PARTIALLY_VERIFIED`, `UNVERIFIED`).
  - **Multi-Source Fallback Hierarchy**: `OpenAI Responses Web Search` → `RemoteOK / Arbeitnow Job APIs` → `DuckDuckGo Live Search`.
- **Autonomous Multi-Agent Pipeline (LangGraph)**:
  - **Supervisor**: Analyzes natural language search prompts into structured `SearchCriteria`.
  - **Candidate Agent**: Ingests PDF/text resumes and creates structured `CandidateProfile` models.
  - **Job Research Agent**: Executes multi-query search strategies with canonical MD5 deduplication.
  - **Matching Agent**: Deterministic 7-factor scoring (Skills 30%, Experience 20%, Role 20%, Location 15%, Education 5%, Cloud 5%, Domain 5%).
  - **Recruiter Agent**: Discovers public talent partners using evidence-based OpenAI web research with zero email hallucination.
  - **Application Agent**: Factual resume tailoring (no fabricated experience), custom cover letters, and safe application question answering.
  - **Outreach Agent**: Drafts concise email and compliant LinkedIn outreach notes.
  - **Human-in-the-Loop Approval Gate**: Interactive approval center for reviewing all packages before external dispatch.
- **Compliance & Security**:
  - Zero unauthorized LinkedIn scraping or browser bot automation.
  - Email dispatching guarded by idempotency keys (`candidate_id + job_id + action_type`).
  - Strict separation between automated internal actions and human-approved external dispatches.
- **Model Context Protocol (MCP)**:
  - Standardized FastMCP tool servers for Job Search, Email, Recruiters, and Applications.
- **Observability & Analytics**:
  - Real-time Server-Sent Events (SSE) streaming of agent reasoning steps.
  - Complete execution telemetry with latency tracking and step logs.
  - Interactive pipeline Kanban & table tracking board.

---

## Architecture Overview

```text
Streamlit UI / Web UI
       ↓
FastAPI Backend
       ↓
LangGraph Supervisor Agent
       ↓
JobResearchAgent
       ↓
OpenAI Responses API (tools=[{"type": "web_search", "search_context_size": "high"}])
       ↓ (Fallback on failure/offline: RemoteOK → Arbeitnow → DuckDuckGo)
Structured Job Evidence + Source Citations
       ↓
Canonical MD5 Deduplication
       ↓
Deterministic 7-Factor Matching (Skills 30%, Exp 20%, Role 20%, Loc 15%, Cloud 5%, Edu 5%, Dom 5%)
       ↓
Recruiter Web Research (Targeted for Strong Matches)
       ↓
Application Agent (Resume Tailoring + Cover Letter + 3-Tier Safe Q&A)
       ↓
Outreach Agent (Email Draft + Compliant LinkedIn Prep)
       ↓
HUMAN APPROVAL GATE (Mandatory Review & Authorization)
       ↓
Authorized Email MCP Dispatch / Manual LinkedIn Deep Links
       ↓
Lifecycle Tracking Database
```

---

## Quick Start (Local Development)

### 1. Prerequisites
- Python 3.11+
- Node.js 20+ & npm

### 2. Clone & Setup Environment
```bash
# Copy environment variables
cp .env.example .env
```

### 3. Install Dependencies
```bash
# Install backend requirements
pip install -r backend/requirements.txt

# Install frontend dependencies
cd frontend && npm install && cd ..
```

### 4. Run Backend & Frontend

**Terminal 1 (Backend API):**
```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
API Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)

**Terminal 2 (Streamlit UI):**
```bash
streamlit run streamlit_app.py --server.port 8501
```
Streamlit App: [http://localhost:8501](http://localhost:8501)

**Terminal 3 (React + TypeScript Web UI):**
```bash
cd frontend
npm run dev
```
Web App UI: [http://localhost:5173](http://localhost:5173)

---

## Running with Docker Compose

```bash
docker compose up --build
```
- Frontend UI: `http://localhost:3000`
- Backend API: `http://localhost:8000/docs`
- PostgreSQL & Redis automatically provisioned.

---

## Running Automated Tests

```bash
cd backend
python -m pytest tests/ -v
```

The test suite covers 23 comprehensive tests:
1. `test_openai_client_configuration`: Validates model configuration and client initialization.
2. `test_web_research_schema`: Pydantic validation of `JobResearchResult` and `SourceEvidence`.
3. `test_job_research_parsing`: JSON extraction and citation deserialization from model output.
4. `test_source_evidence`: Ensures source URLs and supports attributes are preserved.
5. `test_verified_job` & `test_unverified_job`: Proper tagging of verification statuses.
6. `test_job_deduplication`: MD5 canonical hash across multi-source postings.
7. `test_matching`: Deterministic 7-factor scoring engine (Skills 30%, Exp 20%, Role 20%, Loc 15%).
8. `test_recruiter_research`: Verifiable talent acquisition partner research.
9. `test_openai_failure_fallback` & `test_rate_limit_fallback`: Seamless fallback to RemoteOK, Arbeitnow, and DuckDuckGo.
10. `test_email_idempotency`: Protection against duplicate emails during retries.
11. `test_application_approval`: Human-in-the-loop governance structure.
12. `test_live_web_research_integration`: Optional live OpenAI API test (`RUN_LIVE_WEB_TEST=true`).

---

## API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/candidates/resume` | Upload PDF resume & parse candidate profile |
| `GET` | `/api/candidates/profile` | Retrieve candidate profile |
| `POST` | `/api/agent/run` | Execute multi-agent search & application workflow |
| `POST` | `/api/agent/stream` | Stream real-time agent reasoning via SSE |
| `GET` | `/api/jobs` | List discovered jobs with match scores & recruiters |
| `GET` | `/api/approvals` | List pending human approval packages |
| `POST` | `/api/approvals/{id}/decide` | Approve & send email, reject, or modify package |
| `GET` | `/api/applications` | Applications lifecycle tracker |
| `GET` | `/api/analytics/dashboard` | Dashboard KPIs and match distributions |

---

## License

MIT License. Designed and engineered for production-quality agentic AI workflows.
