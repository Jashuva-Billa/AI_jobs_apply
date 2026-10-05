import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config.settings import settings
from app.config.database import engine, Base, AsyncSessionLocal
from app.api.routes import (
    candidates,
    agent,
    jobs,
    approvals,
    applications,
    recruiters,
    analytics,
    auth
)
from app.models.entities import Job, CandidateProfile, JobMatch, Recruiter
from app.integrations.web.search import CURATED_AI_JOBS
from app.services.matching_service import matching_service
from app.schemas.schemas import CandidateProfileBase

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

async def seed_initial_data():
    """Seeds initial jobs, recruiters, and default candidate profile if empty."""
    async with AsyncSessionLocal() as session:
        from sqlalchemy import func, select
        cnt = await session.scalar(select(func.count(Job.id)))
        if cnt == 0:
            logger.info("Seeding initial verified AI Engineering jobs and recruiters...")
            
            # Default candidate
            cand = CandidateProfile(
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
            session.add(cand)
            await session.flush()

            cand_schema = CandidateProfileBase(
                name=cand.name,
                email=cand.email,
                years_of_experience=cand.years_of_experience,
                skills=cand.skills,
                technical_skills=cand.technical_skills,
                cloud_skills=cand.cloud_skills,
                frameworks=cand.frameworks,
                preferred_roles=cand.preferred_roles,
                remote_preference=cand.remote_preference
            )

            # Insert curated jobs and compute baseline matches
            for idx, j_data in enumerate(CURATED_AI_JOBS):
                j_obj = Job(
                    canonical_job_id=f"canonical_seed_{idx}",
                    company=j_data["company"],
                    title=j_data["title"],
                    location=j_data["location"],
                    remote=j_data["remote"],
                    employment_type=j_data["employment_type"],
                    experience_required=j_data["experience_required"],
                    salary=j_data["salary"],
                    description=j_data["description"],
                    requirements=j_data["requirements"],
                    skills=j_data["skills"],
                    application_url=j_data["application_url"],
                    source_url=j_data["source_url"],
                    source_urls=[j_data["source_url"]],
                    posted_date=j_data["posted_date"],
                    company_url=j_data["company_url"]
                )
                session.add(j_obj)
                await session.flush()

                # Add match
                match_res = matching_service.evaluate_match(cand_schema, j_data)
                session.add(JobMatch(
                    job_id=j_obj.id,
                    candidate_id=cand.id,
                    overall_score=match_res.overall_score,
                    skills_score=match_res.skills_score,
                    experience_score=match_res.experience_score,
                    location_score=match_res.location_score,
                    role_score=match_res.role_score,
                    matched_skills=match_res.matched_skills,
                    missing_skills=match_res.missing_skills,
                    concerns=match_res.concerns,
                    recommendation=match_res.recommendation,
                    reasoning=match_res.reasoning
                ))

            await session.commit()
            logger.info("Database initialized and seeded successfully.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_initial_data()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(candidates.router, prefix=settings.API_V1_STR)
app.include_router(agent.router, prefix=settings.API_V1_STR)
app.include_router(jobs.router, prefix=settings.API_V1_STR)
app.include_router(approvals.router, prefix=settings.API_V1_STR)
app.include_router(applications.router, prefix=settings.API_V1_STR)
app.include_router(recruiters.router, prefix=settings.API_V1_STR)
app.include_router(analytics.router, prefix=settings.API_V1_STR)
app.include_router(auth.router, prefix=settings.API_V1_STR)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT
    }
