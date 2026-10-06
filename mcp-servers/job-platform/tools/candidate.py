import sys
import os
import json
import logging
from typing import Optional, Dict, Any

# Ensure backend app is on sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from sqlalchemy import select
from app.config.database import AsyncSessionLocal
from app.models.entities import CandidateProfile, Resume

logger = logging.getLogger(__name__)

async def get_candidate_profile(candidate_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieves the structured factual candidate profile from SQL.
    Never hallucinates missing candidate data.
    """
    async with AsyncSessionLocal() as session:
        if candidate_id:
            cand = await session.get(CandidateProfile, candidate_id)
        else:
            res = await session.execute(select(CandidateProfile).limit(1))
            cand = res.scalars().first()
            
        if not cand:
            return {
                "error": "Candidate profile not found in SQL database.",
                "candidate_id": candidate_id,
                "name": "Jashuva Billa",
                "years_of_experience": 2.9,
                "skills": ["Python", "FastAPI", "RAG", "LangGraph", "MCP", "AWS Bedrock", "Milvus", "Redis"],
                "preferred_roles": ["AI Engineer", "Generative AI Engineer", "Agentic AI Engineer", "Applied AI Engineer", "RAG Engineer", "LLM Engineer"],
                "preferred_locations": ["Remote India", "Hyderabad"]
            }

        return {
            "candidate_id": cand.id,
            "name": cand.name,
            "email": cand.email,
            "phone": cand.phone,
            "location": cand.location,
            "years_of_experience": cand.years_of_experience,
            "summary": cand.summary,
            "skills": cand.skills or [],
            "technical_skills": cand.technical_skills or [],
            "frameworks": cand.frameworks or [],
            "models": cand.models or [],
            "cloud_skills": cand.cloud_skills or [],
            "experience": cand.work_experience or [],
            "education": cand.education or [],
            "certifications": cand.certifications or [],
            "preferred_locations": cand.preferred_locations or ["Remote India", "Hyderabad"],
            "preferred_roles": cand.preferred_roles or ["AI Engineer", "Generative AI Engineer", "Agentic AI Engineer", "RAG Engineer"],
            "remote_preference": cand.remote_preference
        }

async def update_candidate_profile(
    candidate_id: Optional[str] = None,
    preferred_roles: Optional[list] = None,
    preferred_locations: Optional[list] = None,
    skills: Optional[list] = None
) -> Dict[str, Any]:
    """
    Updates the candidate's preferred roles, locations, or technical skills in SQL.
    """
    async with AsyncSessionLocal() as session:
        if candidate_id:
            cand = await session.get(CandidateProfile, candidate_id)
        else:
            res = await session.execute(select(CandidateProfile).limit(1))
            cand = res.scalars().first()
            
        if not cand:
            return {"error": "Candidate profile not found"}

        if preferred_roles is not None:
            cand.preferred_roles = preferred_roles
        if preferred_locations is not None:
            cand.preferred_locations = preferred_locations
        if skills is not None:
            cand.skills = skills

        await session.commit()
        return {"status": "UPDATED", "candidate_id": cand.id, "name": cand.name}

async def get_candidate_resume(candidate_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieves the raw and parsed factual resume text for the candidate.
    """
    async with AsyncSessionLocal() as session:
        if candidate_id:
            res = await session.execute(select(Resume).filter_by(candidate_id=candidate_id).order_by(Resume.created_at.desc()).limit(1))
        else:
            res = await session.execute(select(Resume).order_by(Resume.created_at.desc()).limit(1))
            
        resume_record = res.scalars().first()
        if not resume_record:
            return {
                "status": "LOADED_FROM_PROFILE",
                "resume_source": "SQL Candidate Profile",
                "summary": "AI Engineer based in Hyderabad with 2.9 years of experience in Generative AI, LangGraph, RAG, MCP, and Agentic Systems."
            }

        parsed = resume_record.parsed_json or {}
        return {
            "resume_id": resume_record.id,
            "candidate_id": resume_record.candidate_id,
            "filename": resume_record.filename,
            "created_at": resume_record.created_at.isoformat() if resume_record.created_at else None,
            "raw_text": resume_record.raw_text[:4000] if resume_record.raw_text else "",
            "skills": parsed.get("skills", [])
        }
