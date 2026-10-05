from app.integrations.openai.client import openai_client_wrapper, OpenAIClientWrapper
from app.integrations.openai.schemas import (
    SourceEvidence,
    RecruiterResearchResult,
    JobResearchResult,
    JobResearchResponse
)
from app.integrations.openai.web_research import openai_web_research, OpenAIWebResearchService
from app.integrations.openai.prompts import (
    JOB_RESEARCH_INSTRUCTIONS,
    RECRUITER_RESEARCH_INSTRUCTIONS,
    build_job_research_prompt
)

__all__ = [
    "openai_client_wrapper",
    "OpenAIClientWrapper",
    "SourceEvidence",
    "RecruiterResearchResult",
    "JobResearchResult",
    "JobResearchResponse",
    "openai_web_research",
    "OpenAIWebResearchService",
    "JOB_RESEARCH_INSTRUCTIONS",
    "RECRUITER_RESEARCH_INSTRUCTIONS",
    "build_job_research_prompt"
]
