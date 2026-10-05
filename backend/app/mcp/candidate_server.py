from pydantic import BaseModel
from typing import Dict, Any, Optional
from app.schemas.schemas import CandidateProfileBase
from app.services.resume_service import resume_service

class ParseResumeParams(BaseModel):
    resume_text: str
    filename: Optional[str] = "resume.pdf"

class CandidateMCPTool:
    @staticmethod
    async def extract_candidate_profile(params: ParseResumeParams) -> Dict[str, Any]:
        profile = await resume_service.parse_resume_to_candidate_profile(
            resume_text=params.resume_text,
            filename=params.filename or "resume.pdf"
        )
        return profile.model_dump()

candidate_mcp_tool = CandidateMCPTool()
