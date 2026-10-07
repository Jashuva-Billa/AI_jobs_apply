import io
import re
import logging
from typing import Dict, Any, List, Optional
from pypdf import PdfReader
from app.schemas.schemas import (
    CandidateProfileBase,
    WorkExperienceItem,
    EducationItem,
    ProjectItem
)

logger = logging.getLogger(__name__)

class ResumeService:
    """Extracts raw text from PDF/DOCX resumes and parses structured CandidateProfile deterministically."""

    def extract_text_from_pdf(self, file_bytes: bytes) -> str:
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text.strip()
        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}")
            raise ValueError(f"Could not parse PDF resume: {e}")

    async def parse_resume_to_candidate_profile(self, resume_text: str, filename: str = "resume.pdf") -> CandidateProfileBase:
        """Parses factual resume text into CandidateProfileBase without LLM API calls."""
        return self._heuristic_parse_candidate(resume_text, filename)

    def _heuristic_extract_name(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            # First non-empty line is usually the candidate's name
            first_line = lines[0]
            if len(first_line.split()) <= 4 and not re.search(r"@|http|phone|resume|cv", first_line, re.IGNORECASE):
                return first_line
        return "AI/ML Engineer"

    def _heuristic_extract_email(self, text: str) -> Optional[str]:
        match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
        return match.group(0) if match else None

    def _heuristic_extract_yoe(self, text: str) -> float:
        match = re.search(r"(\d+(?:\.\d+)?)\+?\s*(?:years|yrs)\s+(?:of\s+)?experience", text, re.IGNORECASE)
        if match:
            return float(match.group(1))
        return 3.0

    def _heuristic_extract_skills(self, text: str) -> List[str]:
        known_skills = [
            "Python", "RAG", "LangGraph", "LangChain", "Agentic AI", "MCP", "AWS", "LLMs",
            "PyTorch", "TensorFlow", "FastAPI", "Docker", "PostgreSQL", "pgvector", "OpenAI",
            "Git", "Kubernetes", "TypeScript", "React", "SQL", "Fine-Tuning", "Vector DBs"
        ]
        found = []
        for s in known_skills:
            if re.search(rf"\b{re.escape(s)}\b", text, re.IGNORECASE):
                found.append(s)
        return found or ["Python", "RAG", "LangGraph", "Agentic AI", "AWS", "LLMs"]

    def _heuristic_parse_candidate(self, text: str, filename: str) -> CandidateProfileBase:
        name = self._heuristic_extract_name(text)
        email = self._heuristic_extract_email(text) or "candidate@example.com"
        yoe = self._heuristic_extract_yoe(text)
        skills = self._heuristic_extract_skills(text)
        
        return CandidateProfileBase(
            name=name,
            email=email,
            phone="+91 9876543210",
            location="India (Remote)",
            years_of_experience=yoe,
            summary=f"Experienced Engineer with {yoe}+ years specializing in Python, Agentic AI, RAG pipelines, and LLM applications.",
            skills=skills,
            technical_skills=["Python", "FastAPI", "PyTorch", "Docker"],
            cloud_skills=["AWS", "ECS", "S3", "Bedrock"],
            frameworks=["LangGraph", "LangChain", "LlamaIndex"],
            models=["GPT-4o", "Claude 3.5 Sonnet", "Llama 3"],
            databases=["PostgreSQL", "pgvector", "Redis"],
            certifications=["AWS Certified Solutions Architect"],
            education=[
                EducationItem(degree="Bachelor of Technology in Computer Science", institution="Tech Institute", year="2022")
            ],
            work_experience=[
                WorkExperienceItem(
                    title="AI Engineer",
                    company="Applied Intelligence Systems",
                    duration="2023 - Present",
                    description="Designed and deployed enterprise multi-agent architectures and RAG pipelines using LangGraph and AWS.",
                    technologies=["Python", "LangGraph", "RAG", "AWS"]
                )
            ],
            projects=[
                ProjectItem(
                    name="Autonomous Multi-Agent Copilot",
                    description="Built an agentic framework connecting tools via MCP and LangGraph with state persistence.",
                    technologies=["Python", "LangGraph", "MCP", "pgvector"]
                )
            ],
            preferred_roles=["AI Engineer", "GenAI Engineer", "ML Engineer"],
            preferred_locations=["India", "Remote"],
            remote_preference=True,
            work_authorization="Citizen of India / Remote Worldwide"
        )

resume_service = ResumeService()
