import logging
from typing import Dict, Any, Optional
from app.schemas.schemas import CandidateProfileBase, OutreachMessageBase, RecruiterBase
from app.integrations.llm.provider import llm_provider
from app.services.email_resolution_service import email_resolution_service

logger = logging.getLogger(__name__)

class OutreachGenerationService:
    """Generates personalized, non-spam recruiter communications for Email and LinkedIn."""

    async def generate_recruiter_email(
        self,
        candidate: CandidateProfileBase,
        job: Dict[str, Any],
        recruiter: Optional[RecruiterBase] = None
    ) -> OutreachMessageBase:
        # Dynamically resolve and verify recruiter contact for this specific job
        resolution = email_resolution_service.resolve_recruiter_contact(job, recruiter)
        
        display_recruiter_name = resolution.recruiter_name or "Hiring Team"
        salutation_target = resolution.recruiter_name.split()[0] if resolution.recruiter_name else "Hiring Team"
        recruiter_salutation = f"Hi {salutation_target}" if salutation_target != "Hiring Team" else "Dear Hiring Team"
        
        company = job.get("company", "the team")
        job_title = job.get("title", "Applied AI Engineer")

        system_prompt = (
            "You are a professional Executive Recruiter Outreach Assistant for Jashuva Billa. "
            "Generate a professional, high-impact recruiter email adhering strictly to this structure:\n"
            "1. Salutation (e.g. 'Hi [Recruiter Name / Team]')\n"
            "2. Opening: 'I hope you're doing well.'\n"
            "3. State reaching out regarding the specific [Job Title] position at [Company], stating 2.9 years of experience as an AI Engineer focused on production-oriented Generative AI and Agentic AI systems.\n"
            "4. Core technical summary: RAG, LangGraph-based agent orchestration, MCP/tool calling, context engineering, multi-agent workflows, evaluation using RAGAS/DeepEval and LLM-as-a-Judge, Python/FastAPI, Redis, and AWS/Bedrock.\n"
            "5. Relevance to role: Align role focus on production LLM applications, agentic workflows, and evaluation.\n"
            "6. Call to action: Note attached resume and express interest in discussing team fit.\n"
            "7. Closing signature with Jashuva Billa, AI Engineer | Generative AI | Agentic AI | RAG, Hyderabad, India, +91 9618751495, jashuvabilla@gmail.com, LinkedIn: linkedin.com/in/jashuva-billa."
        )

        user_prompt = (
            f"Target Company: {company}\n"
            f"Target Role: {job_title}\n"
            f"Recruiter: {display_recruiter_name}"
        )

        body = await llm_provider.generate_text(system_prompt, user_prompt)
        if not body or len(body) < 30:
            body = (
                f"{recruiter_salutation},\n\n"
                f"I hope you're doing well.\n\n"
                f"I’m reaching out regarding the {job_title} position at {company}. "
                f"I have 2.9 years of experience as an AI Engineer, focused on building production-oriented Generative AI and Agentic AI systems.\n\n"
                f"My experience includes RAG, LangGraph-based agent orchestration, MCP/tool calling, context engineering, "
                f"multi-agent workflows, evaluation using RAGAS/DeepEval and LLM-as-a-Judge, Python/FastAPI, Redis, and AWS/Bedrock.\n\n"
                f"The role's focus on production LLM applications, agentic workflows, context engineering, and evaluation is closely aligned with my experience.\n\n"
                f"I have attached my resume for your consideration. I would appreciate the opportunity to discuss whether my background would be a good fit for the team.\n\n"
                f"Thank you for your time.\n\n"
                f"Best regards,\n"
                f"Jashuva Billa\n"
                f"AI Engineer | Generative AI | Agentic AI | RAG\n"
                f"Hyderabad, India\n"
                f"+91 9618751495\n"
                f"jashuvabilla@gmail.com\n"
                f"LinkedIn: linkedin.com/in/jashuva-billa"
            )

        subject = f"Application: {job_title} — Jashuva Billa (2.9 yrs AI Engineer)"
        
        return OutreachMessageBase(
            channel="EMAIL",
            subject=subject,
            body=body.strip(),
            recipient_email=resolution.email,
            recipient_name=display_recruiter_name,
            email_status=resolution.status,
            email_source=resolution.source,
            email_confidence=resolution.confidence,
            recruiter_status=resolution.recruiter_status
        )

    async def generate_linkedin_outreach(
        self,
        candidate: CandidateProfileBase,
        job: Dict[str, Any],
        recruiter: Optional[RecruiterBase] = None
    ) -> OutreachMessageBase:
        resolution = email_resolution_service.resolve_recruiter_contact(job, recruiter)
        recruiter_salutation = resolution.recruiter_name.split()[0] if resolution.recruiter_name else "there"
        company = job.get("company", "the team")
        job_title = job.get("title", "AI Engineer")

        # LinkedIn messages should be strictly under 300 characters for connection requests
        body = (
            f"Hi {recruiter_salutation}, I saw the {job_title} opening at {company}. "
            f"With hands-on experience building multi-agent systems and RAG pipelines in Python & LangGraph, "
            f"I'd love to connect and share my background for the team!"
        )

        return OutreachMessageBase(
            channel="LINKEDIN",
            subject=f"Connect on {job_title} role at {company}",
            body=body,
            recipient_email=None,
            recipient_name=resolution.recruiter_name or "Hiring Team",
            email_status="NOT_FOUND",
            email_source=None,
            email_confidence=0.0,
            recruiter_status=resolution.recruiter_status
        )

outreach_service = OutreachGenerationService()

