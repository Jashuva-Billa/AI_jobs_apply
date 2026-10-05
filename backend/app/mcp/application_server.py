from pydantic import BaseModel
from typing import Dict, Any, List
from app.schemas.schemas import CandidateProfileBase, MatchBreakdown
from app.services.application_service import application_service

class TailorResumeParams(BaseModel):
    candidate: Dict[str, Any]
    job: Dict[str, Any]
    match: Dict[str, Any]

class ApplicationMCPTool:
    @staticmethod
    async def tailor_application_package(params: TailorResumeParams) -> Dict[str, Any]:
        cand = CandidateProfileBase(**params.candidate)
        match = MatchBreakdown(**params.match)
        tailored = await application_service.tailor_resume(cand, params.job, match)
        cover_letter = await application_service.generate_cover_letter(cand, params.job, match)
        questions = application_service.prepare_application_questions(cand, params.job)

        return {
            "tailored_resume": tailored,
            "cover_letter": cover_letter,
            "questions": [q.model_dump() for q in questions]
        }

application_mcp_tool = ApplicationMCPTool()
