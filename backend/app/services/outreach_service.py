import logging
from typing import Dict, Any, Optional
from app.schemas.schemas import CandidateProfileBase, OutreachMessageBase, RecruiterBase
from app.integrations.llm.provider import llm_provider

logger = logging.getLogger(__name__)

class OutreachGenerationService:
    """Generates personalized, non-spam recruiter communications for Email and LinkedIn."""

    async def generate_recruiter_email(
        self,
        candidate: CandidateProfileBase,
        job: Dict[str, Any],
        recruiter: Optional[RecruiterBase]
    ) -> OutreachMessageBase:
        recruiter_name = recruiter.name.split()[0] if recruiter and recruiter.name else "Hiring Team"
        company = job.get("company", "the team")
        job_title = job.get("title", "AI Engineer")
        top_skills = ", ".join(candidate.skills[:4]) if candidate.skills else "Python, RAG, LangGraph, and LLMs"

        system_prompt = (
            "You are a professional Executive Recruiter Outreach Assistant. "
            "Write a concise, personalized, high-conversion recruiter email. "
            "RULES:\n"
            "1. Max 100-120 words. No fluffy buzzwords or generic spam.\n"
            "2. Highlight 2-3 specific matching technical capabilities (e.g. Python, RAG, LangGraph, AWS).\n"
            "3. State enthusiasm for the specific role and company.\n"
            "4. Include a clear, polite call-to-action.\n"
            "5. Address the recruiter by first name."
        )

        user_prompt = (
            f"Candidate Name: {candidate.name}\n"
            f"Candidate Summary: {candidate.summary}\n"
            f"Candidate Skills: {top_skills}\n"
            f"Target Company: {company}\n"
            f"Target Role: {job_title}\n"
            f"Recruiter Name: {recruiter_name}"
        )

        body = await llm_provider.generate_text(system_prompt, user_prompt)
        if not body or len(body) < 30:
            body = (
                f"Hi {recruiter_name},\n\n"
                f"I came across the {job_title} opportunity at {company}. "
                f"My background in designing production GenAI workflows using {top_skills} aligns directly with your team's requirements.\n\n"
                f"I've attached my tailored resume and would welcome the opportunity to discuss how my experience can support your AI roadmap.\n\n"
                f"Best regards,\n{candidate.name or 'Candidate'}"
            )

        subject = f"{candidate.name or 'Application'} — {job_title} Application & Background"
        
        return OutreachMessageBase(
            channel="EMAIL",
            subject=subject,
            body=body.strip(),
            recipient_email=recruiter.public_email if recruiter else None,
            recipient_name=recruiter.name if recruiter else "Hiring Team"
        )

    async def generate_linkedin_outreach(
        self,
        candidate: CandidateProfileBase,
        job: Dict[str, Any],
        recruiter: Optional[RecruiterBase]
    ) -> OutreachMessageBase:
        recruiter_name = recruiter.name.split()[0] if recruiter and recruiter.name else "there"
        company = job.get("company", "the team")
        job_title = job.get("title", "AI Engineer")

        # LinkedIn messages should be strictly under 300 characters for connection requests
        body = (
            f"Hi {recruiter_name}, I saw the {job_title} opening at {company}. "
            f"With hands-on experience building multi-agent systems and RAG pipelines in Python & LangGraph, "
            f"I'd love to connect and share my background for the team!"
        )

        return OutreachMessageBase(
            channel="LINKEDIN",
            subject=f"Connect on {job_title} role at {company}",
            body=body,
            recipient_email=None,
            recipient_name=recruiter.name if recruiter else "Hiring Manager"
        )

outreach_service = OutreachGenerationService()
