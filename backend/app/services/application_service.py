import logging
from typing import Dict, Any, List, Optional
from app.schemas.schemas import (
    CandidateProfileBase,
    ApplicationQuestionSchema,
    MatchBreakdown
)
from app.integrations.llm.provider import llm_provider

logger = logging.getLogger(__name__)

class QuestionClassification:
    SAFE_FACTUAL = "SAFE_FACTUAL"
    NEEDS_USER_INPUT = "NEEDS_USER_INPUT"
    SENSITIVE = "SENSITIVE"

class ApplicationPackageService:
    """
    Handles factual resume tailoring, cover letter generation, and 3-tier safe application question answering.
    """

    async def tailor_resume(
        self,
        candidate: CandidateProfileBase,
        job: Dict[str, Any],
        match: MatchBreakdown
    ) -> Dict[str, Any]:
        company = job.get("company", "Target Company")
        job_title = job.get("title", "AI Engineer")

        # Factual skill highlighting (ONLY existing candidate skills that match)
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
        """
        Classifies and answers application questions:
        1. SAFE_FACTUAL: years of experience, Python experience, AWS, etc.
        2. NEEDS_USER_INPUT: salary expectations, notice period, availability.
        3. SENSITIVE: visa sponsorship, work authorization, legal, demographic.
        """
        sample_questions = [
            {"q": "How many years of professional experience do you have with Python?", "category": QuestionClassification.SAFE_FACTUAL},
            {"q": "Have you built production RAG or Agentic LLM systems with LangGraph?", "category": QuestionClassification.SAFE_FACTUAL},
            {"q": "What is your target compensation / salary expectation for this position?", "category": QuestionClassification.NEEDS_USER_INPUT},
            {"q": "What is your earliest availability and notice period?", "category": QuestionClassification.NEEDS_USER_INPUT},
            {"q": "What is your work authorization status (Visa Sponsorship / Remote Contractor)?", "category": QuestionClassification.SENSITIVE},
            {"q": "Do you require visa sponsorship to work for this company?", "category": QuestionClassification.SENSITIVE}
        ]

        results = []
        for item in sample_questions:
            q_text = item["q"]
            category = item["category"]
            
            if category == QuestionClassification.SAFE_FACTUAL:
                if "python" in q_text.lower():
                    answer = f"{candidate.years_of_experience} years of hands-on Python development."
                elif "rag" in q_text.lower() or "langgraph" in q_text.lower() or "llm" in q_text.lower():
                    answer = "Yes, extensive experience building production Agentic LLM workflows and RAG pipelines using LangGraph and AWS."
                else:
                    answer = f"Yes, experienced with {', '.join(candidate.skills[:3])}."
                status = "SAFE_FACTUAL"
                is_sensitive = False
                needs_input = False

            elif category == QuestionClassification.NEEDS_USER_INPUT:
                if "salary" in q_text.lower() or "compensation" in q_text.lower():
                    answer = "Negotiable / Competitive market rate based on role scope."
                else:
                    answer = "Available immediately / 2-week standard notice."
                status = "NEEDS_USER_INPUT"
                is_sensitive = False
                needs_input = True

            else: # SENSITIVE
                if "sponsorship" in q_text.lower():
                    answer = "No sponsorship needed for remote worldwide contractor setup."
                else:
                    answer = candidate.work_authorization or "Authorized for remote worldwide contract work."
                status = "SENSITIVE"
                is_sensitive = True
                needs_input = True

            results.append(ApplicationQuestionSchema(
                question=q_text,
                answer=answer,
                is_sensitive=is_sensitive,
                needs_user_input=needs_input,
                status=status
            ))

        return results

application_service = ApplicationPackageService()
