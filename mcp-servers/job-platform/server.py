import sys
import os
import logging
from typing import Optional, List, Dict, Any

# Ensure backend directory is in python path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from urllib.parse import urlparse
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
import uvicorn

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from auth.handler import mcp_auth
from instructions.system_prompt import JOB_PLATFORM_AGENT_INSTRUCTIONS
from app.config.settings import settings

# Import tool implementations
from tools.candidate import get_candidate_profile as _get_candidate_profile
from tools.candidate import update_candidate_profile as _update_candidate_profile
from tools.candidate import get_candidate_resume as _get_candidate_resume
from tools.jobs import search_jobs as _search_jobs
from tools.jobs import get_search_run as _get_search_run
from tools.jobs import get_search_results as _get_search_results
from tools.matching import match_jobs as _match_jobs
from tools.recruiters import find_recruiter as _find_recruiter
from tools.applications import prepare_application as _prepare_application
from tools.applications import prepare_applications_batch as _prepare_applications_batch
from tools.applications import get_application_status as _get_application_status
from tools.approvals import get_pending_approvals as _get_pending_approvals
from tools.approvals import approve_applications as _approve_applications
from tools.approvals import reject_applications as _reject_applications
from tools.outreach import send_approved_email as _send_approved_email
from tools.outreach import prepare_linkedin_outreach as _prepare_linkedin_outreach

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("job-platform-mcp")

# Initialize official MCP server
SERVER_NAME = os.getenv("MCP_SERVER_NAME", "job-platform-mcp")
mcp = MCPServer(SERVER_NAME, instructions=JOB_PLATFORM_AGENT_INSTRUCTIONS)

# ---------------------------------------------------------------------------
# 1. CANDIDATE TOOLS
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_candidate_profile(candidate_id: Optional[str] = None) -> Dict[str, Any]:
    """
    [READ-ONLY] Retrieve the structured candidate profile from SQL database.
    Use this tool whenever you need factual candidate experience, skills, preferred roles, or locations.
    Never hallucinate missing information.
    """
    return await _get_candidate_profile(candidate_id=candidate_id)

@mcp.tool()
async def update_candidate_profile(
    candidate_id: Optional[str] = None,
    preferred_roles: Optional[List[str]] = None,
    preferred_locations: Optional[List[str]] = None,
    skills: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    [WRITE] Update candidate preferences (roles, locations, skills) in SQL.
    Use this tool when the user requests updating their job preferences or technical tags.
    """
    return await _update_candidate_profile(
        candidate_id=candidate_id,
        preferred_roles=preferred_roles,
        preferred_locations=preferred_locations,
        skills=skills
    )

@mcp.tool()
async def get_candidate_resume(candidate_id: Optional[str] = None) -> Dict[str, Any]:
    """
    [READ-ONLY] Retrieve the full factual resume text and parsed skills for the candidate.
    Use this tool before writing tailored cover letters or answering detailed application questions.
    """
    return await _get_candidate_resume(candidate_id=candidate_id)

# ---------------------------------------------------------------------------
# 2. JOB DISCOVERY & SEARCH TOOLS
# ---------------------------------------------------------------------------

@mcp.tool()
async def search_jobs(
    query: str,
    location: Optional[str] = "India",
    remote: Optional[bool] = True,
    seniority: Optional[str] = "mid",
    max_results: Optional[int] = 100,
    candidate_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    [READ/DISCOVERY] Search live job openings across RemoteOK, Arbeitnow, and DuckDuckGo career pages.
    Creates a durable SearchRun in SQL and returns structured job opportunities with source URLs.
    Supports up to 100 results (`max_results=100`).
    Never invents jobs or application links.
    """
    return await _search_jobs(
        query=query,
        location=location,
        remote=remote,
        seniority=seniority,
        max_results=max_results,
        candidate_id=candidate_id
    )

@mcp.tool()
async def get_search_run(run_id: str) -> Dict[str, Any]:
    """
    [READ-ONLY] Retrieve the status, timestamps, and job processing metrics for a durable SearchRun.
    Statuses: SEARCHING, MATCHING, PREPARING_APPLICATIONS, WAITING_FOR_APPROVAL, PARTIALLY_APPROVED, COMPLETED, FAILED.
    """
    return await _get_search_run(run_id=run_id)

@mcp.tool()
async def get_search_results(run_id: str, page: int = 1, page_size: int = 100) -> Dict[str, Any]:
    """
    [READ-ONLY] Retrieve paginated jobs and match evaluation records for a search run.
    Allows retrieving all 100+ discovered jobs without losing context across conversations.
    """
    return await _get_search_results(run_id=run_id, page=page, page_size=page_size)

# ---------------------------------------------------------------------------
# 3. DETERMINISTIC 7-FACTOR MATCHING TOOL
# ---------------------------------------------------------------------------

@mcp.tool()
async def match_jobs(
    job_ids: Optional[List[str]] = None,
    run_id: Optional[str] = None,
    candidate_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    [COMPUTATION & PERSISTENCE] Run the official deterministic 7-factor matching engine against candidate profile.
    Weights: Skills (30%), Experience (20%), Role (20%), Location (15%), Cloud (5%), Education (5%), Domain (5%).
    Thresholds: STRONG (>=85), QUALIFIED (>=75), POSSIBLE (>=65), REJECTED (<65).
    ChatGPT must NOT calculate scores itself; always use this tool.
    """
    return await _match_jobs(job_ids=job_ids, run_id=run_id, candidate_id=candidate_id)

# ---------------------------------------------------------------------------
# 4. RECRUITER DISCOVERY TOOL
# ---------------------------------------------------------------------------

@mcp.tool()
async def find_recruiter(
    job_id: Optional[str] = None,
    company: Optional[str] = None
) -> Dict[str, Any]:
    """
    [READ/SEARCH] Discover evidence-backed public technical recruiter or talent acquisition contacts for a company.
    Distinguishes direct recruiter contacts from generic company inboxes.
    Never invents email addresses.
    """
    return await _find_recruiter(job_id=job_id, company=company)

# ---------------------------------------------------------------------------
# 5. APPLICATION PACKAGE PREPARATION TOOLS
# ---------------------------------------------------------------------------

@mcp.tool()
async def prepare_application(
    candidate_id: Optional[str] = None,
    job_id: str = "",
    run_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    [WRITE] Prepares a complete factual application package (tailored resume, cover letter,
    outreach email draft, LinkedIn outreach note) and creates a PENDING approval record in SQL.
    Does NOT submit or send anything externally.
    """
    return await _prepare_application(candidate_id=candidate_id, job_id=job_id, run_id=run_id)

@mcp.tool()
async def prepare_applications_batch(
    run_id: str,
    job_ids: Optional[List[str]] = None,
    max_concurrency: int = 10
) -> Dict[str, Any]:
    """
    [WRITE/BATCH] Prepares application packages for all qualified jobs under bounded concurrency (default 10).
    Creates PENDING approval records in SQL and transitions the SearchRun to WAITING_FOR_APPROVAL.
    Do NOT use for rejected or low-match jobs.
    """
    return await _prepare_applications_batch(run_id=run_id, job_ids=job_ids, max_concurrency=max_concurrency)

# ---------------------------------------------------------------------------
# 6. HUMAN-IN-THE-LOOP (HITL) APPROVAL TOOLS
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_pending_approvals(run_id: Optional[str] = None) -> Dict[str, Any]:
    """
    [READ-ONLY] Retrieve all pending applications waiting for human review.
    Returns structured list with match scores, company names, job titles, and recruiter email previews.
    Always present this list to the user and request explicit confirmation before approving.
    """
    return await _get_pending_approvals(run_id=run_id)

@mcp.tool()
async def approve_applications(approval_ids: List[str]) -> Dict[str, Any]:
    """
    [WRITE / ACTION - REQUIRES EXPLICIT USER CONFIRMATION]
    Approves the specified applications in SQL.
    Dispatches authorized recruiter outreach emails (with idempotency protection) and updates search run metrics.
    Only call this tool after the human user has explicitly authorized the action in chat.
    """
    return await _approve_applications(approval_ids=approval_ids)

@mcp.tool()
async def reject_applications(approval_ids: List[str]) -> Dict[str, Any]:
    """
    [WRITE] Rejects the specified application approval records in SQL and updates SearchRun metrics.
    """
    return await _reject_applications(approval_ids=approval_ids)

# ---------------------------------------------------------------------------
# 7. OUTREACH TOOLS
# ---------------------------------------------------------------------------

@mcp.tool()
async def send_approved_email(application_id: str) -> Dict[str, Any]:
    """
    [WRITE / ACTION] Sends an outreach email for an application whose status is explicitly APPROVED.
    Protected by candidate_id:job_id:EMAIL_OUTREACH idempotency key.
    Will reject attempts to send emails for non-approved applications.
    """
    return await _send_approved_email(application_id=application_id)

@mcp.tool()
async def prepare_linkedin_outreach(application_id: str) -> Dict[str, Any]:
    """
    [READ-ONLY / 100% COMPLIANT] Generates compliant LinkedIn outreach copy and deep-links to recruiter profiles.
    Does NOT use automated browser sessions, scraping, or cookie theft.
    """
    return await _prepare_linkedin_outreach(application_id=application_id)

@mcp.tool()
async def get_application_status(application_id: str) -> Dict[str, Any]:
    """
    [READ-ONLY] Retrieve the current persisted status, approval state, outreach delivery details,
    and audit history for a specific application ID across all lifecycle stages (PENDING, APPROVED, REJECTED, SUBMITTED, FAILED).
    Guaranteed read-only: never mutates state, sends emails, or performs outreach.
    """
    return await _get_application_status(application_id=application_id)

# ---------------------------------------------------------------------------
# HTTP / SSE / ASGI SERVER MOUNTING
# ---------------------------------------------------------------------------

async def health_check(request):
    """Health check endpoint for monitoring and ChatGPT connectivity verification."""
    auth_meta = mcp_auth.get_auth_metadata()
    return JSONResponse({
        "status": "HEALTHY",
        "service": SERVER_NAME,
        "mcp_version": "2.x",
        "transports": ["/sse", "/mcp"],
        "auth": auth_meta,
        "registered_tools_count": 16,
        "candidate": "Jashuva Billa",
        "experience": "2.9 years",
        "role": "AI Engineer / Generative AI / Agentic AI / RAG"
    })

async def get_instructions_endpoint(request):
    """Returns the agent system instructions."""
    return JSONResponse({
        "instructions": JOB_PLATFORM_AGENT_INSTRUCTIONS
    })

def get_transport_security_settings() -> TransportSecuritySettings:
    """
    Build TransportSecuritySettings allowing localhost, ngrok, and any configured custom hosts/origins.
    Protects against DNS rebinding while allowing public tunnel connectivity (e.g. ngrok, ChatGPT Web).
    """
    allowed_hosts = {
        "localhost",
        "localhost:*",
        "127.0.0.1",
        "127.0.0.1:*",
        "0.0.0.0",
        "0.0.0.0:*",
        "[::1]",
        "[::1]:*",
        "celery-ecosystem-suspense.ngrok-free.dev",
        "celery-ecosystem-suspense.ngrok-free.dev:*",
    }

    # Parse ALLOWED_HOSTS / MCP_ALLOWED_HOSTS from settings and environment
    env_hosts = os.getenv("ALLOWED_HOSTS", "") or os.getenv("MCP_ALLOWED_HOSTS", "") or getattr(settings, "ALLOWED_HOSTS", "")
    if env_hosts:
        for host_entry in str(env_hosts).split(","):
            h = host_entry.strip()
            if h:
                if h.startswith("http://") or h.startswith("https://"):
                    parsed = urlparse(h)
                    if parsed.netloc:
                        h = parsed.netloc
                allowed_hosts.add(h)
                if not h.endswith(":*"):
                    allowed_hosts.add(f"{h}:*")

    # Parse MCP_PUBLIC_URL if present
    public_url = os.getenv("MCP_PUBLIC_URL", "") or getattr(settings, "MCP_PUBLIC_URL", "") or ""
    if public_url:
        parsed = urlparse(str(public_url).strip())
        if parsed.netloc:
            h = parsed.netloc
            allowed_hosts.add(h)
            if not h.endswith(":*"):
                allowed_hosts.add(f"{h}:*")

    # Base allowed origins (ChatGPT Web, local origins, ngrok)
    allowed_origins = {
        "http://localhost:*",
        "http://127.0.0.1:*",
        "http://[::1]:*",
        "https://chatgpt.com",
        "https://chatgpt.com:*",
        "https://chat.openai.com",
        "https://chat.openai.com:*",
        "https://platform.openai.com",
        "https://platform.openai.com:*",
        "https://celery-ecosystem-suspense.ngrok-free.dev",
        "https://celery-ecosystem-suspense.ngrok-free.dev:*",
        "http://celery-ecosystem-suspense.ngrok-free.dev",
        "http://celery-ecosystem-suspense.ngrok-free.dev:*",
    }

    # Add HTTP/HTTPS origins for all allowed hosts
    for h in list(allowed_hosts):
        clean_h = h[:-2] if h.endswith(":*") else h
        allowed_origins.add(f"http://{clean_h}")
        allowed_origins.add(f"https://{clean_h}")
        allowed_origins.add(f"http://{clean_h}:*")
        allowed_origins.add(f"https://{clean_h}:*")

    # Parse ALLOWED_ORIGINS / MCP_ALLOWED_ORIGINS from env/settings
    env_origins = os.getenv("ALLOWED_ORIGINS", "") or os.getenv("MCP_ALLOWED_ORIGINS", "") or getattr(settings, "MCP_ALLOWED_ORIGINS", "") or ""
    if env_origins:
        for origin_entry in str(env_origins).split(","):
            o = origin_entry.strip()
            if o:
                allowed_origins.add(o)
                if not o.endswith(":*"):
                    allowed_origins.add(f"{o}:*")

    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=list(allowed_hosts),
        allowed_origins=list(allowed_origins),
    )

transport_security = get_transport_security_settings()

# Create Starlette app mounting MCP SSE and Streamable HTTP endpoints
routes = [
    Route("/health", health_check, methods=["GET"]),
    Route("/info", health_check, methods=["GET"]),
    Route("/instructions", get_instructions_endpoint, methods=["GET"]),
    Mount("/", app=mcp.sse_app(transport_security=transport_security))
]

middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )
]

app = Starlette(routes=routes, middleware=middleware)

if __name__ == "__main__":
    host = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_SERVER_PORT", "8001"))
    logger.info(f"Starting Job Platform MCP Server on {host}:{port}...")
    uvicorn.run(app, host=host, port=port, log_level="info")
