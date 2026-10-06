# ChatGPT Web + Model Context Protocol (MCP) Setup Guide

This guide walks you through connecting your local **AI Job Platform MCP Server** directly to **ChatGPT Web**.

---

## 1. Prerequisites
- Python 3.10+ with repository dependencies installed (`pip install -r backend/requirements.txt` and `pip install mcp`)
- A secure tunneling tool for exposing your local MCP server to ChatGPT Web (e.g. `ngrok`, `cloudflared`, or `localtunnel`)
- A ChatGPT Plus / Team / Enterprise account with access to custom MCP Apps / Actions.

---

## 2. Architecture Overview
```text
┌────────────────────────┐
│      ChatGPT Web       │  (Reasoning & Autonomous Orchestration Layer)
└───────────┬────────────┘
            │  HTTPS / Streamable SSE (Model Context Protocol)
            ▼
┌────────────────────────┐
│  job-platform-mcp      │  (Port 8001: Tool Execution & State Gateway)
└───────────┬────────────┘
            │  SQLAlchemy (Async)
            ▼
┌────────────────────────┐
│   Authoritative DB     │  (SQLite / MySQL: Candidates, Jobs, Matches, Approvals)
└────────────────────────┘
```

---

## 3. Starting the MCP Server Locally

1. **Configure Environment:**
   Ensure your `.env` has:
   ```env
   MCP_SERVER_NAME=job-platform-mcp
   MCP_SERVER_HOST=0.0.0.0
   MCP_SERVER_PORT=8001
   MCP_AUTH_MODE=development
   DATABASE_URL=sqlite+aiosqlite:///./jobs_platform.db
   ```
   *(Note: No `OPENAI_API_KEY` is required for this workflow!)*

2. **Launch the MCP Server:**
   ```bash
   cd mcp-servers/job-platform
   python server.py
   ```
   The server starts on `http://0.0.0.0:8001`.

3. **Verify Local Health:**
   ```bash
   curl http://localhost:8001/health
   ```
   Expected response:
   ```json
   {
     "status": "HEALTHY",
     "service": "job-platform-mcp",
     "mcp_version": "2.x",
     "transports": ["/sse", "/mcp"],
     "registered_tools_count": 16
   }
   ```

---

## 4. Exposing Secure HTTPS for ChatGPT Web

ChatGPT Web requires a publicly accessible HTTPS endpoint. Use `ngrok` or Cloudflare tunnel:

### Option A: Using Ngrok
```bash
ngrok http 8001
```
Ngrok will generate a secure public forwarding URL, for example:
`https://abcd-1234-5678.ngrok-free.dev`

Your MCP SSE endpoint will be:
`https://abcd-1234-5678.ngrok-free.dev/sse`

### Option B: Using Cloudflare Tunnel
```bash
cloudflared tunnel --url http://localhost:8001
```

---

## 5. Connecting to ChatGPT Web

1. Open **[ChatGPT Web](https://chatgpt.com)**.
2. Go to **Settings** → **Apps & Connectors** (or **Custom GPTs / Actions**).
3. Select **Add Custom MCP Server / Connector**.
4. Enter configuration details:
   - **Server Name:** `job-platform-mcp`
   - **MCP Server URL:** `https://your-tunnel-domain.ngrok-free.dev/sse` (or `/mcp`)
   - **Authentication:** None (in `development` mode) or Bearer Token (if `MCP_AUTH_MODE=protected`)
5. Click **Scan & Discover Tools**.
   ChatGPT will automatically register all 16 business tools:
   1. `get_candidate_profile` (Read-only candidate overview)
   2. `update_candidate_profile` (Update preferences and skills)
   3. `get_candidate_resume` (Read-only factual resume text)
   4. `search_jobs` (Live multi-source job search across RemoteOK, Arbeitnow, Career portals)
   5. `get_search_run` (Durable search run inspection)
   6. `get_search_results` (Paginated search results & match evaluations)
   7. `match_jobs` (Deterministic 7-factor scoring engine)
   8. `find_recruiter` (Evidence-backed public recruiter discovery)
   9. `prepare_application` (Single application preparation into PENDING_APPROVAL)
   10. `prepare_applications_batch` (Bounded concurrency batch preparation into PENDING_APPROVAL)
   11. `get_pending_approvals` (Read-only review table for human authorization)
   12. `get_application_status` (Read-only aggregate status, outreach delivery, and audit history)
   13. `approve_applications` (Human approval gate by exact UUIDs)
   14. `reject_applications` (Application rejection by exact UUIDs)
   15. `send_approved_email` (Outreach email dispatch with idempotency key)
   16. `prepare_linkedin_outreach` (Compliant manual deep links and outreach copy)

---

## 6. Example Conversational Prompt for ChatGPT

Once connected, start a new chat in ChatGPT and type:

> "Find me remote AI Engineer, GenAI Engineer, and RAG Engineer roles matching my resume in India or Remote-friendly companies. Search for 50+ opportunities, rank them using the deterministic matching engine, and prepare application packages for all qualified matches. Present the pending approvals before taking any action."

ChatGPT will autonomously:
1. Fetch your factual candidate profile (`get_candidate_profile`).
2. Search live job listings across RemoteOK, Arbeitnow, and career pages (`search_jobs`).
3. Execute the 7-factor deterministic match scoring (`match_jobs`).
4. Prepare tailored application artifacts across all matches in parallel (`prepare_applications_batch`).
5. Retrieve and present the human-in-the-loop approval summary table (`get_pending_approvals`).
6. Await your explicit approval command (e.g., *"Approve the top 20 applications"*) before calling `approve_applications`.
