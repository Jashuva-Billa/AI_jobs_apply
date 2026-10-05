# Antigravity AI — Agentic Job Search & Application Platform

An enterprise-grade, multi-agent AI system built with **FastAPI**, **LangGraph**, **React**, and **Model Context Protocol (MCP)** that allows users to upload their resume once, specify search directives in natural language, and let autonomous agents discover, match, tailor, and prepare applications under human-in-the-loop governance.

---

## Key Features

- **Autonomous Multi-Agent Pipeline (LangGraph)**:
  - **Supervisor**: Analyzes natural language search prompts into structured `SearchCriteria`.
  - **Candidate Agent**: Ingests PDF/text resumes and creates structured `CandidateProfile` models.
  - **Job Research Agent**: Executes multi-query search strategies with canonical MD5 deduplication.
  - **Matching Agent**: Deterministic 7-factor scoring (Skills 30%, Experience 20%, Role 20%, Location 15%, Education 5%, Cloud 5%, Domain 5%).
  - **Recruiter Agent**: Public talent partner discovery with verified sources and zero personal email hallucination.
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
Upload Resume
       ↓
Create Candidate Profile
       ↓
User enters natural-language job-search prompt
       ↓
Supervisor parses prompt
       ↓
Job Research Agent searches online
       ↓
Extract jobs & Canonical Deduplication
       ↓
Candidate/Job Multi-Factor Matching (30% Skills, 20% Exp, 20% Role, 15% Loc...)
       ↓
Rank jobs & Recruiter Discovery
       ↓
Generate application package (Tailored Resume, Cover Letter, Safe Q&A)
       ↓
HUMAN APPROVAL GATE (Review & Authorize)
       ↓
Authorized Email Dispatch / Prepared LinkedIn Action
       ↓
Lifecycle Status Tracking
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
python -m pytest tests/test_all.py -v
```

All 5 unit & integration tests verify:
1. Canonical job ID normalization & deduplication.
2. Deterministic multi-factor match scoring.
3. Safe factual answers vs sensitive question gating.
4. Recruiter discovery with source evidence verification.
5. Email dispatch idempotency protection.

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
