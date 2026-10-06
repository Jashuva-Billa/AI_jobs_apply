# 🚀 Antigravity AI — Agentic Job Search & Application Platform

An enterprise-grade, autonomous multi-agent AI system built with **FastAPI**, **LangGraph**, **Streamlit**, and **Model Context Protocol (MCP)**. 

Upload your resume once, define your career goals in natural language (either in the local dashboard or directly in **ChatGPT Web**), and let autonomous agents discover verified job openings, perform deterministic 7-factor matching, research recruiters, and prepare tailored application packages—all strictly governed by **Human-in-the-Loop (HITL)** approval before any external action is taken.

---

## 📌 Architecture & Dual-Mode Execution

The platform supports two complementary operational workflows:

```text
                                  ┌───────────────────────────────────────────────┐
                                  │           ChatGPT Web (Custom MCP)            │
                                  └──────────────────────┬────────────────────────┘
                                                         │ HTTPS (ngrok /sse)
                                                         ▼
┌───────────────────────────┐     ┌───────────────────────────────────────────────┐
│   Streamlit Web UI        │     │         Job Platform MCP Server               │
│   (Port 8501)             │     │         (Port 8001)                           │
└─────────────┬─────────────┘     └──────────────────────┬────────────────────────┘
              │                                          │
              │ REST / Local Async                       │ SQLAlchemy Async
              ▼                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      Authoritative SQL Database & State Layer                   │
│         (Candidate Profile, Live Jobs, 7-Factor Matches, Pending Approvals)     │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│               Deterministic Multi-Agent Engine (FastAPI + LangGraph)            │
│  [Job Research] ➔ [7-Factor Matcher] ➔ [Recruiter Agent] ➔ [Application Agent]  │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     🛡️ MANDATORY HUMAN-IN-THE-LOOP (HITL) GATE                  │
│            • No auto-applying   • No auto-emailing   • Explicit Authorization   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 1. Mode A: ChatGPT Web + MCP (Conversational AI Assistant)
ChatGPT connects via the **Model Context Protocol (MCP)** to discover and invoke tools directly in conversation. You chat with ChatGPT, ask it to find roles and prepare applications, review generated packages inside ChatGPT, and explicitly authorize actions.

### 2. Mode B: Streamlit Dashboard UI
Interactive browser dashboard with visual Kanban boards, real-time SSE telemetry, match score analytics, and one-click package inspection and approval.

---

## ⚡ Server Ecosystem (What You Need to Run)

To run the full end-to-end platform with both the local UI and ChatGPT MCP integration, start these services:

| Service | Script / Command | Port / URL | Purpose |
| :--- | :--- | :--- | :--- |
| **1. FastAPI Backend** | `uvicorn app.main:app --port 8000` | `http://localhost:8000` | REST API, LangGraph orchestration, SSE streaming |
| **2. Streamlit Dashboard** | `streamlit run streamlit_app.py --server.port 8501` | `http://localhost:8501` | Interactive visual dashboard & Kanban board |
| **3. MCP Server** | `python mcp-servers/job-platform/server.py` | `http://localhost:8001` | Official MCP SSE protocol server & tool execution |
| **4. Ngrok Tunnel** | `ngrok http 8001` | `https://<subdomain>.ngrok-free.dev` | Secure public HTTPS tunnel for ChatGPT Web |

---

## 🛠️ Complete Step-by-Step Startup Guide

### Step 1: Clone & Configure Environment

Ensure you have created your `.env` file from `.env.example`:

```bash
# Copy example configuration
cp .env.example .env
```

Ensure the key parameters are configured in your `.env`:
```env
# Database (SQLite by default, MySQL optional)
DATABASE_URL=sqlite+aiosqlite:///./jobs_platform.db

# LLM Provider (Gemini Primary, OpenAI Fallback)
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key

# MCP Server
MCP_SERVER_NAME=job-platform-mcp
MCP_SERVER_HOST=0.0.0.0
MCP_SERVER_PORT=8001
MCP_AUTH_MODE=development
ALLOWED_HOSTS=localhost,127.0.0.1,celery-ecosystem-suspense.ngrok-free.dev
MCP_PUBLIC_URL=https://celery-ecosystem-suspense.ngrok-free.dev
```

---

### Step 2: Launch the 4 Core Services

Open **4 separate terminal windows** (or use the one-click `start_services.bat` launcher):

#### Terminal 1: FastAPI Backend
```powershell
# In project root
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: [http://localhost:8000/health](http://localhost:8000/health)

#### Terminal 2: Streamlit Dashboard UI
```powershell
# In project root
streamlit run streamlit_app.py --server.port 8501
```
- Dashboard: [http://localhost:8501](http://localhost:8501)

#### Terminal 3: Job Platform MCP Server
```powershell
# In project root
python mcp-servers/job-platform/server.py
```
- Local SSE Endpoint: `http://localhost:8001/sse`
- Health Endpoint: `http://localhost:8001/health`

#### Terminal 4: Ngrok HTTPS Tunnel (For ChatGPT)
```powershell
# In project root
ngrok http 8001
```
- Note the public forwarding URL displayed by ngrok (e.g. `https://celery-ecosystem-suspense.ngrok-free.dev`).

---

## 🤖 ChatGPT Web + MCP Integration Guide

You can connect your local system directly to **ChatGPT Web** (ChatGPT Plus, Team, or Enterprise) as a custom MCP connector.

### Connecting in ChatGPT:
1. Open [ChatGPT Web](https://chatgpt.com).
2. Go to **Settings** ➔ **Apps & Connectors** (or **Explore GPTs / Actions**).
3. Select **Add Custom MCP Server / Connector**.
4. Configure the server:
   - **Server Name:** `job-platform-mcp`
   - **Server URL:** `https://<your-ngrok-subdomain>.ngrok-free.dev/sse` (e.g., `https://celery-ecosystem-suspense.ngrok-free.dev/sse`)
   - **Authentication:** `None` (Development mode)
5. Click **Connect & Scan Tools**.
   ChatGPT will automatically discover and register all **16 business tools**.

---

## 🧰 Available MCP Tools Reference (16 Total)

| Tool Name | Type | Description |
| :--- | :--- | :--- |
| `get_candidate_profile` | `READ-ONLY` | Retrieves structured candidate profile (skills, experience, preferences) from SQL. |
| `update_candidate_profile` | `WRITE` | Updates candidate roles, location preferences, or skills in SQL. |
| `get_candidate_resume` | `READ-ONLY` | Retrieves full resume text and parsed competencies. |
| `search_jobs` | `READ/DISCOVERY` | Discovers live verified job listings across RemoteOK, Arbeitnow, and career pages. |
| `get_search_run` | `READ-ONLY` | Retrieves durable search run metrics and step progress. |
| `get_search_results` | `READ-ONLY` | Retrieves paginated discovered jobs and match evaluations. |
| `match_jobs` | `COMPUTATION` | Executes deterministic 7-factor scoring engine (Skills 30%, Exp 20%, Role 20%, Loc 15%). |
| `find_recruiter` | `READ/SEARCH` | Discovers verified public technical recruiters without email hallucination. |
| `prepare_application` | `WRITE/HITL` | Prepares tailored resume, cover letter, and outreach drafts; inserts `PENDING` approval record. |
| `prepare_applications_batch` | `WRITE/BATCH` | Prepares application packages for all qualified jobs under bounded concurrency. |
| `get_pending_approvals` | `READ-ONLY` | Retrieves all pending applications awaiting human authorization. |
| `get_application_status` | `READ-ONLY` | Retrieves lifecycle status, approval state, and complete audit history for any application ID. |
| `approve_applications` | `WRITE/ACTION` | **Explicit Human Gate:** Approves applications by exact UUID, triggers authorized email outreach. |
| `reject_applications` | `WRITE` | Rejects application approval records by exact UUID. |
| `send_approved_email` | `WRITE/ACTION` | Dispatches outreach email for explicitly approved applications (idempotency-guarded). |
| `prepare_linkedin_outreach` | `READ-ONLY` | Generates compliant LinkedIn outreach copy and deep-links to recruiter profiles. |

---

## 💬 Example Prompt for ChatGPT Web

Once connected, you can converse naturally with ChatGPT:

> *"Find me remote AI Engineer and GenAI Engineer roles matching my resume in India or Remote-friendly companies. Search for live openings, rank them using the deterministic 7-factor engine, and prepare application packages for all qualified matches. Present the pending approval summary table before taking any external action."*

**What happens autonomously:**
1. ChatGPT inspects candidate profile via `get_candidate_profile`.
2. Searches live openings via `search_jobs`.
3. Runs deterministic 7-factor scoring via `match_jobs`.
4. Prepares tailored resume summaries, cover letters, and outreach drafts via `prepare_applications_batch` (status: `PENDING`).
5. Fetches pending applications via `get_pending_approvals` and formats a review table with exact UUIDs.
6. Awaits your approval (e.g., *"Approve application `<APPROVAL_UUID>`"*) before calling `approve_applications`.
7. Inspects status at any point via `get_application_status`.

---

## 🛡️ Human-in-the-Loop (HITL) Safety Guarantees

- **Zero Silent Applications:** The platform is architected so that `prepare_application` and `prepare_applications_batch` **never** apply or email automatically.
- **Strict State Transitions:** Packages enter `PENDING_APPROVAL` status. Only explicit human invocation of `approve_applications` allows email dispatch.
- **Idempotency Protection:** Every outbound email is keyed by `candidate_id:job_id:EMAIL_OUTREACH` to prevent accidental duplicate dispatches.
- **Compliance:** 100% compliant with LinkedIn Terms of Service (uses deep-links and manual copy rather than bot automation or cookie theft).

---

## 🧪 Running Automated Tests

Run the full automated test suite covering all services, MCP tools, and HITL gates:

```powershell
# Run MCP Tool suite
python backend/tests/test_mcp_server.py

# Run Prepare Application & Approval workflow tests
python backend/tests/test_prepare_application.py

# Run Read-Only Application Status audit tests
python backend/tests/test_get_application_status.py

# Run full pytest suite
pytest backend/tests/ -v
```

---

## 📄 License

MIT License. Designed and engineered for production-grade agentic AI workflows.
