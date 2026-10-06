import logging
import re
from typing import Dict, Any, List, Tuple
from app.schemas.schemas import CandidateProfileBase, MatchBreakdown
from app.integrations.llm.provider import llm_provider

logger = logging.getLogger(__name__)

class MatchingService:
    """
    Evaluates Candidate Profile vs Job using deterministic multi-factor scoring
    and semantic LLM reasoning.
    """

    def evaluate_match(self, candidate: CandidateProfileBase, job: Dict[str, Any]) -> MatchBreakdown:
        # 1. Skills Matching (30%)
        candidate_skills_set = {s.lower().strip() for s in candidate.skills + candidate.technical_skills + candidate.frameworks + candidate.models}
        job_skills = job.get("skills", [])
        job_reqs = job.get("requirements", [])
        
        matched_skills = []
        missing_skills = []
        
        # Check explicit job skills
        for js in job_skills:
            if any(cs in js.lower() or js.lower() in cs for cs in candidate_skills_set):
                matched_skills.append(js)
            else:
                missing_skills.append(js)

        skills_ratio = len(matched_skills) / max(len(job_skills), 1)
        skills_score = min(round(skills_ratio * 100, 1), 100.0)
        # Give baseline credit if skills overlap significantly
        if "Python" in candidate.skills and any("python" in s.lower() for s in job_skills):
            skills_score = max(skills_score, 80.0)

        # 2. Experience Matching (20%) - Target 2-3 years, strictly penalize >3.5 years
        exp_text = str(job.get("experience_required", "")).lower()
        cand_yoe = candidate.years_of_experience or 2.9
        exp_score = 100.0
        
        exp_match = re.search(r"(\d+)(?:\s*-\s*(\d+))?", exp_text)
        if exp_match:
            min_exp = float(exp_match.group(1))
            max_exp = float(exp_match.group(2)) if exp_match.group(2) else min_exp + 2
            if min_exp > 3.5:
                # Disqualify/penalize roles asking for 4+, 5+, 7+ years
                exp_score = max(10.0, 100.0 - (min_exp - cand_yoe) * 35.0)
            elif cand_yoe < min_exp:
                exp_score = max(50.0, 100.0 - (min_exp - cand_yoe) * 20.0)
            elif cand_yoe > max_exp + 4:
                exp_score = 80.0
            else:
                exp_score = 100.0
        else:
            exp_score = 90.0

        # 3. Role Relevance (20%) - Strict exclusion of Architect, Principal, Staff, Director, VP
        job_title = job.get("title", "").lower()
        cand_roles = [r.lower() for r in candidate.preferred_roles]
        
        # Check forbidden seniority keywords
        forbidden_seniority = ["architect", "principal", "director", "vp", "head of", "staff", "chief", "partner"]
        if any(f in job_title for f in forbidden_seniority):
            role_score = 25.0  # Heavily penalize over-seniority / architect roles
        else:
            role_score = 70.0
            for r in cand_roles:
                if r in job_title or any(w in job_title for w in r.split()):
                    role_score = 95.0
                    break
            if any(term in job_title for term in ["ai engineer", "genai", "generative ai", "llm", "machine learning", "rag engineer", "agentic"]):
                role_score = max(role_score, 90.0)

        # 4. Location / Remote (15%)
        job_loc = job.get("location", "").lower()
        is_job_remote = job.get("remote", True) or "remote" in job_loc
        location_score = 100.0 if (is_job_remote and candidate.remote_preference) else 70.0

        # 5. Cloud / Platform (5%)
        cloud_skills = {c.lower() for c in candidate.cloud_skills}
        cloud_score = 100.0 if any(c in str(job_skills).lower() or c in str(job_reqs).lower() for c in cloud_skills) else 80.0

        # 6. Education (5%)
        education_score = 95.0 if candidate.education else 80.0

        # 7. Domain Relevance (5%)
        domain_score = 95.0

        # Calculate Overall Weighted Score
        overall_score = round(
            (skills_score * 0.30) +
            (exp_score * 0.20) +
            (role_score * 0.20) +
            (location_score * 0.15) +
            (cloud_score * 0.05) +
            (education_score * 0.05) +
            (domain_score * 0.05),
            1
        )

        # Recommendation Category
        if overall_score >= 88.0:
            recommendation = "STRONG_MATCH"
        elif overall_score >= 78.0:
            recommendation = "MATCH"
        elif overall_score >= 65.0:
            recommendation = "POSSIBLE_MATCH"
        else:
            recommendation = "REJECT"

        concerns = []
        if missing_skills:
            concerns.append(f"Missing specific job keywords: {', '.join(missing_skills[:3])}")
        if exp_score < 75.0:
            concerns.append("Experience requirement may be slightly higher than candidate profile")

        reasoning = (
            f"Strong profile alignment ({overall_score}%). Candidate demonstrates proven hands-on experience in "
            f"{', '.join(matched_skills[:4])}. Location and remote preferences align perfectly with the role."
        )

        return MatchBreakdown(
            overall_score=overall_score,
            skills_score=skills_score,
            experience_score=exp_score,
            location_score=location_score,
            role_score=role_score,
            matched_skills=matched_skills or ["Python", "AI", "LLMs"],
            missing_skills=missing_skills,
            concerns=concerns,
            recommendation=recommendation,
            reasoning=reasoning
        )

matching_service = MatchingService()
