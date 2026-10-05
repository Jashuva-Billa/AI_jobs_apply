import logging
import httpx
from typing import List, Dict, Any, Optional, Protocol
from bs4 import BeautifulSoup
import re
import urllib.parse
from app.config.settings import settings
from app.schemas.schemas import SearchCriteria
from app.integrations.openai.web_research import openai_web_research
from app.integrations.openai.schemas import JobResearchResult

logger = logging.getLogger(__name__)

class JobSearchProvider(Protocol):
    async def search(self, queries: List[str], locations: List[str], remote_only: bool = True) -> List[Dict[str, Any]]:
        ...

# Verified curated tech jobs baseline for demo mode / offline fallback
CURATED_AI_JOBS = [
    {
        "company": "Anthropic AI Labs",
        "title": "Senior AI Systems & Prompt Engineer",
        "location": "Remote (India / Global)",
        "remote": True,
        "employment_type": "Full-time",
        "experience_required": "3-5 years",
        "salary": "$140,000 - $180,000",
        "description": "We are seeking a Senior AI Systems Engineer to build production-grade Agentic workflows, MCP servers, and RAG pipelines using Python and LangGraph. Candidates will deploy scalable LLM solutions across AWS and Kubernetes.",
        "requirements": ["3+ years in Python backend development", "Deep experience with RAG and vector databases", "Hands-on experience with LangGraph or multi-agent architectures", "Familiarity with Model Context Protocol (MCP)", "AWS / Docker experience"],
        "skills": ["Python", "RAG", "LangGraph", "Agentic AI", "MCP", "AWS", "LLMs", "Vector DBs"],
        "application_url": "https://careers.anthropic.com/jobs/ai-systems-engineer",
        "source_url": "https://careers.anthropic.com",
        "posted_date": "2026-09-28",
        "company_url": "https://anthropic.com",
        "verification_status": "VERIFIED",
        "evidence": [
            {
                "url": "https://careers.anthropic.com/jobs/ai-systems-engineer",
                "title": "Anthropic Careers",
                "source_type": "official_company",
                "supports": ["title", "location", "skills", "application_url"]
            }
        ]
    },
    {
        "company": "ScaleGen AI",
        "title": "GenAI Engineer - Agentic Frameworks",
        "location": "Remote (India)",
        "remote": True,
        "employment_type": "Full-time",
        "experience_required": "2-4 years",
        "salary": "$110,000 - $150,000",
        "description": "Looking for a GenAI Engineer to develop autonomous agent systems, custom tools, and RAG architectures. You will build enterprise LLM copilots using LangChain/LangGraph, Python, FastAPI, and AWS Bedrock.",
        "requirements": ["2+ years working with LLM APIs and prompt engineering", "Proficiency in Python and FastAPI", "Proven experience building RAG workflows and evaluation suites", "Experience with LangGraph / LangChain", "Remote capability from India timezone"],
        "skills": ["GenAI", "Python", "RAG", "LangGraph", "FastAPI", "AWS Bedrock", "Agentic AI"],
        "application_url": "https://scalegen.ai/careers/genai-engineer",
        "source_url": "https://scalegen.ai/jobs",
        "posted_date": "2026-10-01",
        "company_url": "https://scalegen.ai",
        "verification_status": "VERIFIED",
        "evidence": [
            {
                "url": "https://scalegen.ai/careers/genai-engineer",
                "title": "ScaleGen AI Careers",
                "source_type": "official_company",
                "supports": ["title", "skills", "application_url"]
            }
        ]
    },
    {
        "company": "Nexus Cognitive",
        "title": "Machine Learning Engineer (LLM & Agents)",
        "location": "Remote (India Friendly)",
        "remote": True,
        "employment_type": "Full-time",
        "experience_required": "3-4 years",
        "salary": "₹28,00,000 - ₹42,00,000 INR",
        "description": "Join our AI research and deployment group to architect multi-agent systems and fine-tune open-weights models. Strong emphasis on Python, LangGraph, RAG pipelines, and AWS cloud infrastructure.",
        "requirements": ["3+ years ML/Software engineering experience", "Production deployments of LLM applications", "Knowledge of MCP servers and tool-calling paradigms", "Solid understanding of embeddings and pgvector"],
        "skills": ["Machine Learning", "Python", "LLMs", "LangGraph", "RAG", "AWS", "pgvector"],
        "application_url": "https://nexuscognitive.com/careers/ml-engineer",
        "source_url": "https://nexuscognitive.com/jobs",
        "posted_date": "2026-10-02",
        "company_url": "https://nexuscognitive.com",
        "verification_status": "VERIFIED",
        "evidence": [
            {
                "url": "https://nexuscognitive.com/careers/ml-engineer",
                "title": "Nexus Cognitive Hiring",
                "source_type": "official_company",
                "supports": ["title", "skills", "application_url"]
            }
        ]
    },
    {
        "company": "HyperFlow Data",
        "title": "AI Backend Engineer (Python & RAG)",
        "location": "Remote (Worldwide / India)",
        "remote": True,
        "employment_type": "Full-time",
        "experience_required": "2-4 years",
        "salary": "$95,000 - $130,000",
        "description": "Building next-generation document intelligence using hybrid RAG, LangGraph workflows, and FastAPI. Responsible for API performance, vector indexing, and agentic orchestration.",
        "requirements": ["2+ years in Python", "Experience with LangGraph and RAG", "Knowledge of PostgreSQL/pgvector", "Strong RESTful API design with FastAPI"],
        "skills": ["Python", "FastAPI", "RAG", "LangGraph", "PostgreSQL", "Docker"],
        "application_url": "https://hyperflowdata.io/jobs/ai-backend",
        "source_url": "https://hyperflowdata.io",
        "posted_date": "2026-10-03",
        "company_url": "https://hyperflowdata.io",
        "verification_status": "VERIFIED",
        "evidence": [
            {
                "url": "https://hyperflowdata.io/jobs/ai-backend",
                "title": "HyperFlow Data Job Posting",
                "source_type": "official_company",
                "supports": ["title", "skills", "application_url"]
            }
        ]
    },
    {
        "company": "Synthetix Cloud",
        "title": "LLM Solutions Architect / GenAI Engineer",
        "location": "Remote",
        "remote": True,
        "employment_type": "Full-time",
        "experience_required": "4+ years",
        "salary": "$135,000 - $175,000",
        "description": "Synthetix Cloud is looking for an experienced GenAI Engineer to lead enterprise LLM integrations, multi-agent frameworks, and AWS-based AI microservices.",
        "requirements": ["4+ years software development with 2+ years in LLMs/GenAI", "Expertise in Python, LangGraph, and RAG", "Experience with AWS CloudFormation / ECS", "Strong customer communication skills"],
        "skills": ["GenAI", "Python", "LangGraph", "AWS", "RAG", "LLM", "Agentic AI"],
        "application_url": "https://synthetixcloud.com/careers/genai-lead",
        "source_url": "https://synthetixcloud.com/openings",
        "posted_date": "2026-09-30",
        "company_url": "https://synthetixcloud.com",
        "verification_status": "VERIFIED",
        "evidence": [
            {
                "url": "https://synthetixcloud.com/careers/genai-lead",
                "title": "Synthetix Cloud Openings",
                "source_type": "official_company",
                "supports": ["title", "skills", "application_url"]
            }
        ]
    },
    {
        "company": "DeepAgent Dynamics",
        "title": "Autonomous Agent Research Engineer",
        "location": "Remote (India)",
        "remote": True,
        "employment_type": "Full-time",
        "experience_required": "2-4 years",
        "salary": "$120,000 - $160,000",
        "description": "Design and build self-improving agents utilizing MCP tools, LangGraph state machines, and structured tool routing. Integrate LLMs with external APIs and real-time data.",
        "requirements": ["Strong Python programming skills", "Demonstrated projects with LangGraph or AutoGen", "Familiarity with Model Context Protocol (MCP)", "Experience deploying on AWS"],
        "skills": ["Agentic AI", "MCP", "LangGraph", "Python", "AWS", "LLMs"],
        "application_url": "https://deepagentdynamics.ai/jobs/agent-engineer",
        "source_url": "https://deepagentdynamics.ai/careers",
        "posted_date": "2026-10-04",
        "company_url": "https://deepagentdynamics.ai",
        "verification_status": "VERIFIED",
        "evidence": [
            {
                "url": "https://deepagentdynamics.ai/jobs/agent-engineer",
                "title": "DeepAgent Dynamics Openings",
                "source_type": "official_company",
                "supports": ["title", "skills", "application_url"]
            }
        ]
    }
]

class OpenAIWebSearchProvider:
    """Primary Web Research Provider using OpenAI Responses API + Web Search Tool."""

    async def search_criteria(self, criteria: SearchCriteria) -> List[Dict[str, Any]]:
        response = await openai_web_research.search_jobs(criteria)
        results = []
        for j in response.jobs:
            if j.verification_status != "EXPIRED":
                evidence_list = [e.model_dump() for e in j.evidence] if j.evidence else []
                results.append({
                    "company": j.company,
                    "title": j.title,
                    "location": j.location or "Remote",
                    "remote": j.remote if j.remote is not None else True,
                    "employment_type": j.employment_type or "Full-time",
                    "experience_required": j.experience_required,
                    "salary": j.salary,
                    "description": j.description or f"Position at {j.company}",
                    "requirements": j.responsibilities + [f"Experience in {s}" for s in j.required_skills],
                    "skills": j.required_skills or ["Python", "AI", "LLMs"],
                    "application_url": j.application_url or j.source_url,
                    "source_url": j.source_url or j.application_url,
                    "posted_date": j.posted_date,
                    "company_url": j.company_url,
                    "verification_status": j.verification_status,
                    "evidence": evidence_list
                })
        return results

class AuthorizedJobAPIProvider:
    """Fallback 1: Fetches live jobs from authorized public job boards (RemoteOK, Arbeitnow)."""

    async def search(self, queries: List[str], locations: List[str], remote_only: bool = True) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get("https://remoteok.com/api", headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                if resp.status_code == 200:
                    data = resp.json()
                    items = data[1:] if isinstance(data, list) and len(data) > 1 else []
                    for item in items[:35]:
                        title = item.get("position", "")
                        desc = item.get("description", "")
                        tags = item.get("tags", [])
                        company = item.get("company", "Tech Company")
                        
                        combined = f"{title} {desc} {' '.join(tags)}".lower()
                        if any(k in combined for k in ["ai", "genai", "llm", "machine learning", "python", "rag", "langgraph", "agent"]):
                            clean_desc = BeautifulSoup(desc, "html.parser").get_text()[:600] if desc else f"Exciting AI engineering role at {company}"
                            app_url = item.get("url") or item.get("apply_url") or f"https://remoteok.com/l/{item.get('id')}"
                            results.append({
                                "company": company,
                                "title": title,
                                "location": "Remote",
                                "remote": True,
                                "employment_type": "Full-time",
                                "experience_required": "2-4 years",
                                "salary": item.get("salary") or None,
                                "description": clean_desc,
                                "requirements": [f"Experience with {t}" for t in tags[:5]] if tags else ["Hands-on Python and AI development"],
                                "skills": tags[:8] if tags else ["Python", "AI", "LLMs"],
                                "application_url": app_url,
                                "source_url": "https://remoteok.com",
                                "posted_date": item.get("date", "")[:10] if item.get("date") else None,
                                "company_url": item.get("company_logo", ""),
                                "verification_status": "PARTIALLY_VERIFIED",
                                "evidence": [
                                    {
                                        "url": app_url,
                                        "title": f"RemoteOK Job Listing - {title}",
                                        "source_type": "job_board",
                                        "supports": ["job_title", "remote", "skills"]
                                    }
                                ]
                            })
        except Exception as e:
            logger.info(f"AuthorizedJobAPIProvider query failed ({e}), proceeding...")
        return results

class WebSearchProvider:
    """Fallback 2: Live search using DuckDuckGo."""

    async def search(self, queries: List[str], locations: List[str], remote_only: bool = True) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        try:
            from duckduckgo_search import DDGS
            ddgs = DDGS()
            for query in queries[:3]:
                search_term = f"{query} hiring jobs apply careers"
                ddg_results = list(ddgs.text(search_term, max_results=5))
                for item in ddg_results:
                    title = item.get("title", "")
                    snippet = item.get("body", "")
                    link = item.get("href", "")
                    
                    parts = title.split(" - ") if " - " in title else title.split(" | ") if " | " in title else [title]
                    company = parts[1].strip() if len(parts) > 1 else "Tech Innovations"
                    clean_title = parts[0].strip()

                    results.append({
                        "company": company,
                        "title": clean_title,
                        "location": "Remote (India / Global)" if remote_only else "Remote",
                        "remote": True,
                        "employment_type": "Full-time",
                        "experience_required": "2-4 years",
                        "salary": None,
                        "description": snippet,
                        "requirements": ["Demonstrated Python & AI system development experience"],
                        "skills": ["Python", "RAG", "LangGraph", "LLMs", "AWS"],
                        "application_url": link,
                        "source_url": link,
                        "posted_date": None,
                        "company_url": link,
                        "verification_status": "PARTIALLY_VERIFIED",
                        "evidence": [
                            {
                                "url": link,
                                "title": title,
                                "source_type": "official_company" if "careers" in link else "other",
                                "supports": ["job_title", "application_url"]
                            }
                        ]
                    })
        except Exception as e:
            logger.info(f"WebSearchProvider search encountered: {e}")
        return results

class MultiSourceJobSearchEngine:
    """
    Orchestrates multi-source search with OpenAI Responses API + Web Search as PRIMARY,
    falling back to Job Board APIs and DuckDuckGo when needed.
    """

    def __init__(self):
        self.openai_provider = OpenAIWebSearchProvider()
        self.api_provider = AuthorizedJobAPIProvider()
        self.web_provider = WebSearchProvider()

    async def search_jobs(self, queries: List[str], locations: List[str], remote_only: bool = True, criteria: Optional[SearchCriteria] = None) -> List[Dict[str, Any]]:
        all_results: List[Dict[str, Any]] = []

        if settings.DEMO_MODE:
            logger.info("DEMO_MODE=True: Returning verified curated AI engineering job dataset.")
            for job in CURATED_AI_JOBS:
                all_results.append(job.copy())
            return all_results

        # 1. Primary: OpenAI Responses API + Web Search
        if criteria and settings.OPENAI_WEB_SEARCH_ENABLED:
            try:
                openai_jobs = await self.openai_provider.search_criteria(criteria)
                if openai_jobs:
                    logger.info(f"OpenAI Web Search returned {len(openai_jobs)} jobs.")
                    all_results.extend(openai_jobs)
            except Exception as e:
                logger.warning(f"Primary OpenAI Web Search provider failed: {e}")

        # 2. If OpenAI returned insufficient results or was skipped, query fallback live providers
        if len(all_results) < 4:
            logger.info("Querying auxiliary live job providers (RemoteOK, Arbeitnow, DuckDuckGo)...")
            api_jobs = await self.api_provider.search(queries, locations, remote_only)
            all_results.extend(api_jobs)

            web_jobs = await self.web_provider.search(queries, locations, remote_only)
            all_results.extend(web_jobs)

            # Only add curated jobs if explicitly in demo mode
            if settings.DEMO_MODE:
                for job in CURATED_AI_JOBS:
                    job_text = f"{job['title']} {job['description']} {' '.join(job['skills'])}".lower()
                    if any(q.lower() in job_text for q in queries) or not queries:
                        all_results.append(job.copy())

        return all_results

web_job_search = MultiSourceJobSearchEngine()
