from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from app.services.job_service import job_service
from app.schemas.schemas import SearchCriteria

class JobSearchParams(BaseModel):
    roles: List[str] = Field(default_factory=lambda: ["AI Engineer", "GenAI Engineer"])
    skills: List[str] = Field(default_factory=lambda: ["Python", "RAG", "LangGraph"])
    locations: List[str] = Field(default_factory=lambda: ["Remote", "India"])
    remote_required: bool = True

class JobResult(BaseModel):
    company: str
    title: str
    location: str
    remote: bool
    salary: Optional[str] = None
    description: str
    requirements: List[str]
    skills: List[str]
    application_url: Optional[str] = None
    canonical_job_id: str

class JobMCPTool:
    """MCP Tool Adapter for Job Search."""
    
    @staticmethod
    async def search_jobs(params: JobSearchParams) -> List[Dict[str, Any]]:
        criteria = SearchCriteria(
            roles=params.roles,
            skills=params.skills,
            locations=params.locations,
            remote_required=params.remote_required
        )
        jobs, _, _ = await job_service.search_and_deduplicate(criteria)
        return jobs

job_mcp_tool = JobMCPTool()
