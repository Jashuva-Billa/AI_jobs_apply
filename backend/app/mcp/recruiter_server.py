from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.services.recruiter_service import recruiter_service

class RecruiterSearchParams(BaseModel):
    company_name: str
    job_title: str

class RecruiterMCPTool:
    @staticmethod
    async def discover_recruiter(params: RecruiterSearchParams) -> Optional[Dict[str, Any]]:
        recruiter = await recruiter_service.discover_recruiter_for_job(
            company_name=params.company_name,
            job_title=params.job_title
        )
        return recruiter.model_dump() if recruiter else None

recruiter_mcp_tool = RecruiterMCPTool()
