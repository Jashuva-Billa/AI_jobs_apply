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
            
            # Jashuva Billa Candidate Profile
            cand = CandidateProfile(
                name="Jashuva Billa",
                email="jashuvabilla@gmail.com",
                phone="+91 9618751495",
                location="Hyderabad, India",
                years_of_experience=2.0,
                summary="AI Engineer specializing in Generative AI, LangGraph multi-agent orchestration, RAG pipelines, MCP tool execution, and AWS deployment.",
                skills=[
                    "Python", "SQL", "Generative AI", "LLMs", "RAG", "Agentic AI", "Multi-Agent Systems",
                    "LangGraph", "LangChain", "MCP", "Milvus", "Semantic Search", "BM25", "Hybrid Retrieval",
                    "Reciprocal Rank Fusion (RRF)", "Cross-Encoder Reranking", "Docling", "Sentence Transformers",
                    "RAGAS", "DeepEval", "Bedrock Guardrails", "FastAPI", "PostgreSQL", "Redis", "AWS Bedrock",
                    "EKS", "ECR", "Lambda", "Docker", "Langfuse", "OpenTelemetry"
                ],
                technical_skills=["Python", "SQL", "FastAPI", "Docker", "Git"],
                cloud_skills=["AWS Bedrock", "EKS", "ECR", "Lambda", "API Gateway", "S3", "SageMaker", "CloudWatch"],
                frameworks=["LangGraph", "LangChain", "MCP"],
                models=["GPT-4o", "Claude 3.5 Sonnet", "Llama 3", "all-MiniLM-L6-v2", "E5"],
                databases=["PostgreSQL", "Milvus", "Redis/ElastiCache"],
                certifications=[],
                education=[{"degree": "Bachelor of Technology in Computer Science", "institution": "Jawaharlal Nehru Technological University Hyderabad", "year": "2019 - 2023"}],
                work_experience=[
                    {
                        "title": "AI Engineer",
                        "company": "Innovapath IT solutions",
                        "duration": "Feb 2024 - Present",
                        "description": "Built enterprise GenAI and Agentic AI assistants using RAG, LangGraph orchestration, domain agents, tool calling, memory, and policy-driven execution. Designed stateful LangGraph workflows with intent routing, conditional branching, reflection loops, and checkpointing. Implemented MCP-based tool execution, hybrid RAG (Milvus + BM25 + RRF), and AWS containerized deployments.",
                        "technologies": ["Python", "LangGraph", "RAG", "MCP", "Milvus", "FastAPI", "AWS", "Langfuse"]
                    }
                ],
                projects=[
                    {
                        "name": "Enterprise Agentic Copilot & Multi-Agent Orchestrator",
                        "description": "Stateful multi-agent system coordinating triage, troubleshooting, service, billing, and policy agents through LangGraph with MCP tools.",
                        "technologies": ["Python", "LangGraph", "MCP", "FastAPI", "Milvus", "Docker"]
                    }
                ],
                preferred_roles=["AI Engineer", "GenAI Engineer", "Agentic AI Engineer", "LLM Engineer", "Machine Learning Engineer"],
                preferred_locations=["Hyderabad", "Bangalore", "Remote", "India"],
                remote_preference=True,
                work_authorization="Indian Citizen / Authorized for remote global employment"
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
                    company_url=j_data["company_url"],
                    verification_status=j_data.get("verification_status", "VERIFIED"),
                    evidence=j_data.get("evidence", []),
                    research_provider="openai_web_search"
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
async def run_safe_migrations():
    """Safely adds missing columns to existing tables without dropping or deleting data."""
    async with engine.begin() as conn:
        from sqlalchemy import text
        dialect_name = conn.dialect.name
        if dialect_name == "mysql":
            columns_to_add = [
                ("recruiters", "email_type", "VARCHAR(50) DEFAULT 'COMPANY_RECRUITING'"),
                ("recruiters", "source_url", "VARCHAR(500) NULL"),
                ("recruiters", "source_type", "VARCHAR(100) DEFAULT 'PUBLIC_SOURCE'"),
                ("recruiters", "source_evidence", "TEXT NULL"),
                ("recruiters", "confidence", "VARCHAR(20) DEFAULT 'MEDIUM'"),
                ("recruiters", "verified_at", "DATETIME NULL"),
            ]
            for table_name, col_name, col_def in columns_to_add:
                try:
                    check_sql = text(
                        "SELECT COUNT(*) FROM information_schema.columns "
                        "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
                    )
                    res = await conn.execute(check_sql, {"t": table_name, "c": col_name})
                    if res.scalar() == 0:
                        logger.info(f"Adding missing column {col_name} to {table_name}")
                        await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}"))
                except Exception as e:
                    logger.warning(f"Migration error checking/adding {col_name} on {table_name}: {e}")
        elif dialect_name == "sqlite":
            for col_name, col_def in [
                ("email_type", "VARCHAR(50) DEFAULT 'COMPANY_RECRUITING'"),
                ("source_url", "VARCHAR(500) NULL"),
                ("source_type", "VARCHAR(100) DEFAULT 'PUBLIC_SOURCE'"),
                ("source_evidence", "TEXT NULL"),
                ("confidence", "VARCHAR(20) DEFAULT 'MEDIUM'"),
                ("verified_at", "DATETIME NULL"),
            ]:
                try:
                    await conn.execute(text(f"ALTER TABLE recruiters ADD COLUMN {col_name} {col_def}"))
                except Exception:
                    pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await run_safe_migrations()
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
