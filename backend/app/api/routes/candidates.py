import logging
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.config.database import get_db
from app.models.entities import CandidateProfile, Resume
from app.schemas.schemas import CandidateProfileCreate, CandidateProfileResponse
from app.services.resume_service import resume_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/candidates", tags=["Candidates"])

@router.post("/resume", response_model=CandidateProfileResponse)
async def upload_resume(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Upload resume (PDF/text), extract structured candidate profile, and persist to database."""
    content = await file.read()
    filename = file.filename or "resume.pdf"
    
    if filename.endswith(".pdf"):
        raw_text = resume_service.extract_text_from_pdf(content)
    else:
        raw_text = content.decode("utf-8", errors="ignore")

    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from uploaded file.")

    # Parse into structured profile
    parsed_profile = await resume_service.parse_resume_to_candidate_profile(raw_text, filename)
    
    # Check if a candidate already exists or create new
    result = await db.execute(select(CandidateProfile).limit(1))
    existing_candidate = result.scalars().first()

    if existing_candidate:
        # Update existing profile
        for key, value in parsed_profile.model_dump().items():
            setattr(existing_candidate, key, value)
        candidate = existing_candidate
    else:
        candidate = CandidateProfile(**parsed_profile.model_dump())
        db.add(candidate)
    
    await db.flush()

    # Save resume artifact
    resume_record = Resume(
        candidate_id=candidate.id,
        filename=filename,
        raw_text=raw_text,
        parsed_json=parsed_profile.model_dump()
    )
    db.add(resume_record)
    await db.commit()
    await db.refresh(candidate)

    return candidate

@router.get("/profile", response_model=CandidateProfileResponse)
async def get_candidate_profile(db: AsyncSession = Depends(get_db)):
    """Fetch current candidate profile."""
    result = await db.execute(select(CandidateProfile).limit(1))
    candidate = result.scalars().first()
    if not candidate:
        # Return default initialized sample profile
        sample = CandidateProfile(
            name="Alex Morgan",
            email="alex.morgan.ai@example.com",
            phone="+91 98765 43210",
            location="Bangalore, India (Remote)",
            years_of_experience=3.5,
            summary="Experienced AI Engineer specializing in Python, RAG pipelines, LangGraph multi-agent architectures, and AWS LLM deployment.",
            skills=["Python", "RAG", "LangGraph", "Agentic AI", "MCP", "AWS", "LLMs", "FastAPI", "Docker", "pgvector"],
            technical_skills=["Python", "FastAPI", "PyTorch", "Docker", "Git"],
            cloud_skills=["AWS", "ECS", "S3", "Bedrock"],
            frameworks=["LangGraph", "LangChain", "LlamaIndex"],
            models=["GPT-4o", "Claude 3.5 Sonnet", "Llama 3"],
            databases=["PostgreSQL", "pgvector", "Redis"],
            certifications=["AWS Certified Machine Learning Specialist"],
            education=[{"degree": "B.Tech in Computer Science", "institution": "National Institute of Technology", "year": "2022"}],
            work_experience=[
                {
                    "title": "GenAI Systems Engineer",
                    "company": "Cognitive Scale AI",
                    "duration": "2023 - Present",
                    "description": "Architected multi-agent RAG pipelines using LangGraph and AWS ECS, reducing retrieval latency by 45%.",
                    "technologies": ["Python", "LangGraph", "RAG", "AWS", "pgvector"]
                }
            ],
            projects=[
                {
                    "name": "Enterprise Agentic Copilot",
                    "description": "Autonomous multi-agent document analysis platform with Model Context Protocol (MCP) integrations.",
                    "technologies": ["Python", "LangGraph", "MCP", "FastAPI"]
                }
            ],
            preferred_roles=["AI Engineer", "GenAI Engineer", "ML Engineer", "LLM Solutions Architect"],
            preferred_locations=["India", "Remote"],
            remote_preference=True,
            work_authorization="Indian Citizen / Worldwide Remote Contractor"
        )
        db.add(sample)
        await db.commit()
        await db.refresh(sample)
        return sample

    return candidate

@router.put("/profile", response_model=CandidateProfileResponse)
async def update_candidate_profile(
    profile_data: CandidateProfileCreate,
    db: AsyncSession = Depends(get_db)
):
    """Update candidate profile."""
    result = await db.execute(select(CandidateProfile).limit(1))
    candidate = result.scalars().first()
    if not candidate:
        candidate = CandidateProfile(**profile_data.model_dump())
        db.add(candidate)
    else:
        for key, value in profile_data.model_dump().items():
            setattr(candidate, key, value)
    
    await db.commit()
    await db.refresh(candidate)
    return candidate
