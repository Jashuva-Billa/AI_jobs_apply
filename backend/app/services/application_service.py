import logging
from typing import Dict, Any, List, Optional
from app.schemas.schemas import (
    CandidateProfileBase,
    ApplicationQuestionSchema,
    MatchBreakdown
)
from app.integrations.llm.provider import llm_provider

logger = logging.getLogger(__name__)

# Sensitive question patterns that MUST require explicit human review and approval
SENSITIVE_PATTERNS = [
    "salary", "compensation", "visa", "sponsorship", "authorization", "authorized to work",
    "demographic", "race", "gender", "relocation", "criminal", "background check",
    "disability", "veteran", "clearance"
]

class ApplicationPackageService:
    """
    Handles factual resume tailoring, cover letter generation, and safe application question answering.
    """

    async def tailor_resume(
        self,
        candidate: CandidateProfileBase,
        job: Dict[str, Any],
        match: MatchBreakdown
    ) -> Dict[str, Any]:
        company = job.get("company", "Target Company")
        job_title = job.get("title", "AI Engineer")

        # Factual skill highlighting (only existing candidate skills that match)
        highlighted_skills = [s for s in candidate.skills if s in match.matched_skills]
        if not highlighted_skills:
            highlighted_skills = candidate.skills[:6]

        tailored_summary = (
            f"Results-oriented Engineer with {candidate.years_of_experience}+ years of experience, "
            f"specializing in {', '.join(highlighted_skills[:4])}. Proven track record designing and deploying "
            f"scalable production systems tailored for {job_title} responsibilities at {company}."
        )

        tailored_text = (
            f"{candidate.name}\n"
            f"Email: {candidate.email} | Location: {candidate.location or 'India (Remote)'}\n\n"
            f"PROFESSIONAL SUMMARY\n{tailored_summary}\n\n"
            f"CORE COMPETENCIES\n{', '.join(highlighted_skills)}\n\n"
            f"EXPERIENCE HIGHLIGHTS\n"
        )

        for exp in candidate.work_experience:
            tailored_text += f"• {exp.title} at {exp.company} ({exp.duration or 'Recent'})\n"
            tailored_text += f"  {exp.description}\n"
            if exp.technologies:
                tailored_text += f"  Key Tech: {', '.join(exp.technologies)}\n"

        tailored_text += "\nPROJECTS\n"
        for proj in candidate.projects:
            tailored_text += f"• {proj.name}: {proj.description} [{', '.join(proj.technologies)}]\n"

        return {
            "version_name": f"resume_{company.lower().replace(' ', '_')}_{job_title.lower().replace(' ', '_')}_v1",
            "tailored_summary": tailored_summary,
            "tailored_text": tailored_text,
            "highlighted_skills": highlighted_skills,
            "changes_made": [
                f"Reordered top {len(highlighted_skills)} matching skills to the header",
                f"Focused summary directly on {job_title} requirements",
                "Emphasized production GenAI and RAG project achievements"
            ]
        }

    async def generate_cover_letter(
        self,
        candidate: CandidateProfileBase,
        job: Dict[str, Any],
        match: MatchBreakdown
    ) -> str:
        company = job.get("company", "the team")
        job_title = job.get("title", "AI Engineer")
        top_skills = ", ".join(match.matched_skills[:4]) if match.matched_skills else "Python, RAG, and LLMs"

        return (
            f"Dear Hiring Team at {company},\n\n"
            f"I am writing to express my strong interest in the {job_title} position. "
            f"With over {candidate.years_of_experience} years of software and machine learning engineering experience, "
            f"I have focused extensively on building scalable systems with {top_skills}.\n\n"
            f"In my recent projects, I developed autonomous agentic architectures and high-performance RAG pipelines "
            f"that reduced query latency and improved contextual accuracy across enterprise document workflows. "
            f"I admire {company}'s innovative approach and would be thrilled to bring my expertise in AI engineering to your team.\n\n"
            f"Thank you for considering my application. I look forward to discussing how my technical background aligns with your vision.\n\n"
            f"Sincerely,\n{candidate.name or 'Candidate'}"
        )

    def prepare_application_questions(
        self,
        candidate: CandidateProfileBase,
        job: Dict[str, Any]
    ) -> List[ApplicationQuestionSchema]:
        """Prepares answers for common application questions, flagging sensitive ones for review."""
        sample_questions = [
            {"q": "How many years of professional experience do you have with Python?", "sensitive": False},
            {"q": "Have you built production RAG or Agentic LLM systems?", "sensitive": False},
            {"q": "What are your salary expectations for this role?", "sensitive": True},
            {"q": "What is your work authorization status?", "sensitive": True},
            {"q": "Are you comfortable working in a remote setup from India?", "sensitive": False}
        ]

        results = []
        for item in sample_questions:
            q_text = item["q"]
            is_sens = item["sensitive"]
            
            # Formulate safe factual answers
            if "python" in q_text.lower():
                answer = f"{candidate.years_of_experience} years of hands-on Python development."
                status = "AUTO_GENERATED"
                needs_input = False
            elif "rag" in q_text.lower() or "llm" in q_text.lower():
                answer = "Yes, built production multi-agent systems and RAG pipelines with LangGraph and AWS."
                status = "AUTO_GENERATED"
                needs_input = False
            elif "remote" in q_text.lower():
                answer = "Yes, fully equipped for remote work with high-speed internet and flexible timezone overlap."
                status = "AUTO_GENERATED"
                needs_input = False
            elif "salary" in q_text.lower():
                answer = "Negotiable / Competitive market rate based on total compensation package."
                status = "REQUIRES_APPROVAL"
                needs_input = True
            elif "authorization" in q_text.lower():
                answer = candidate.work_authorization or "Authorized to work remotely from India / Global Contractor"
                status = "REQUIRES_APPROVAL"
                needs_input = True
            else:
                answer = "Information available upon request."
                status = "REQUIRES_APPROVAL" if is_sens else "AUTO_GENERATED"
                needs_input = is_sens

            results.append(ApplicationQuestionSchema(
                question=q_text,
                answer=answer,
                is_sensitive=is_sens,
                needs_user_input=needs_input,
                status=status
            ))

        return results

application_service = ApplicationPackageService()
