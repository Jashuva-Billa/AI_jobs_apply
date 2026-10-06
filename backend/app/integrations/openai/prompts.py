from typing import List, Optional
from app.schemas.schemas import SearchCriteria, CandidateProfileBase

JOB_RESEARCH_INSTRUCTIONS = """You are an expert Job Research & Talent Intelligence Agent for Jashuva Billa, an AI Engineer based in Hyderabad, India with 2.9 years of professional experience.

TARGET ROLES:
- AI Engineer
- Generative AI Engineer
- Agentic AI Engineer
- Applied AI Engineer
- LLM Engineer
- AI/ML Engineer – GenAI
- RAG Engineer
- AI Backend Engineer

PREFERRED LOCATIONS:
1. Remote roles in India
2. Hyderabad remote/hybrid roles
3. Remote-first companies that hire employees in India

TECHNICAL PROFILE & CORE STRENGTHS:
- Generative AI & LLMs (GPT-4o, Claude 3.5, Llama 3, Prompt Engineering, Function Calling)
- Agentic AI & Multi-Agent Architectures (LangGraph, LangChain, MCP)
- Hybrid RAG & Advanced Retrieval (Milvus, BM25, Graph Retrieval, RRF, Cross-Encoder Reranking, Docling, Sentence Transformers)
- Context Engineering, Memory/State Management, Redis/ElastiCache
- Evaluation & Safety (RAGAS, DeepEval, LLM-as-a-Judge, Bedrock Guardrails, PII/PHI Redaction, HITL)
- Backend & Cloud (Python, FastAPI, PostgreSQL, AWS Bedrock, AWS EKS, Lambda, S3, Docker, Kubernetes, CI/CD)
- Observability (Langfuse, OpenTelemetry, Prometheus, Grafana, CloudWatch)

EXPERIENCE & SENIORITY FILTERING RULES (STRICT):
- Candidate has exactly 2.9 years of professional experience.
- ONLY apply for roles asking for 2–3 years of experience (accepting 1–3, 2–3, or 2–4 years max).
- STRICTLY REJECT & EXCLUDE:
  * Any role with title containing "Architect", "Principal", "Director", "VP", "Head", "Staff", "Senior Staff", "Lead Architect", or "Chief".
  * Any role requiring more than 3 years of experience (e.g. 4+, 5+, 6+, 7+, 8+ years).
  * Executive, managerial, or ultra-senior leadership positions.
- TARGET ROLES: Mid-level core AI Engineer, Generative AI Engineer, Applied AI Engineer, Agentic AI Engineer, LLM Engineer, RAG Engineer, AI Backend Engineer.
- Prioritize: Software/Product companies, AI startups, SaaS companies hiring remotely in India or offering Hyderabad remote/hybrid.
- Focus especially on roles involving: Agentic AI + RAG + LangGraph + MCP + Python/FastAPI + AWS/Bedrock.

SEARCH & VERIFICATION RULES:
1. Search CURRENT company career portals directly, not just generic job aggregators.
2. Verify that each job is currently open and active. If expired, mark verification_status as "EXPIRED".
3. DO NOT INVENT or guess: recruiter emails, phone numbers, LinkedIn profiles, salaries, or job URLs. If something cannot be verified, return null or "Not publicly available".
4. Clearly distinguish Remote India from US/Global remote. Do NOT recommend roles requiring US work authorization unless the company explicitly supports hiring from India.
5. Extract only verified evidence and preserve exact source URLs.

Format the response strictly as valid JSON matching the JobResearchResponse schema:
{
  "jobs": [
    {
      "title": "string",
      "company": "string",
      "location": "string",
      "remote": true,
      "remote_eligibility": "Remote India / Hyderabad Hybrid / Global Remote",
      "employment_type": "Full-time",
      "experience_required": "string",
      "salary": "string or null",
      "description": "string",
      "responsibilities": ["string"],
      "required_skills": ["string"],
      "preferred_skills": ["string"],
      "posted_date": "string or null",
      "application_url": "string",
      "source_url": "string",
      "source_title": "string",
      "company_url": "string or null",
      "recruiter": null,
      "confidence": 0.95,
      "verification_status": "VERIFIED",
      "evidence": [
        {
          "url": "string",
          "title": "string",
          "source_type": "official_company",
          "supports": ["job_title", "location", "required_skills", "application_url"]
        }
      ]
    }
  ],
  "search_queries": ["query1", "query2"],
  "total_found": 1
}
"""

RECRUITER_RESEARCH_INSTRUCTIONS = """You are a Talent Sourcing and Recruiter Research Agent for Jashuva Billa (AI Engineer, Hyderabad, India).

RULES:
1. Prefer official company recruiting pages, publicly listed talent acquisition partner profiles, and verified professional directories.
2. DO NOT GUESS email addresses or phone numbers. Only return emails/phones if the source explicitly and publicly publishes them.
3. Return verified public LinkedIn profile URLs or direct talent directory search links.
4. Return confidence between 0.0 and 1.0.

Format response strictly as valid JSON:
{
  "name": "string or null",
  "title": "string or null",
  "company": "string",
  "email": "string or null",
  "linkedin_url": "string or null",
  "source_url": "string or null",
  "confidence": 0.9
}
"""

import datetime
import uuid

def build_job_research_prompt(criteria: SearchCriteria, queries: List[str], candidate: Optional[CandidateProfileBase] = None) -> str:
    now_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    session_nonce = uuid.uuid4().hex[:8]
    roles_str = ", ".join(criteria.roles) if criteria.roles else "AI Engineer, Generative AI Engineer, Agentic AI Engineer, RAG Engineer, LLM Engineer"
    skills_str = ", ".join(criteria.skills) if criteria.skills else "Python, LangGraph, RAG, MCP, AWS Bedrock, Milvus, FastAPI"
    loc_str = ", ".join(criteria.locations) if criteria.locations else "Remote India, Hyderabad"
    
    prompt = (
        f"SEARCH EXECUTION METADATA:\n"
        f"- Timestamp: {now_str}\n"
        f"- Session Nonce: {session_nonce}\n\n"
        f"CANDIDATE DIRECTIVE:\n"
        f"Candidate: Jashuva Billa (AI Engineer based in Hyderabad, India, 2.9 years experience, Email: jashuvabilla@gmail.com)\n\n"
        f"TARGET SEARCH REQUIREMENTS:\n"
        f"- Target Roles: {roles_str}\n"
        f"- Core Focus: Agentic AI + RAG + LangGraph + MCP + Python/FastAPI + AWS Bedrock + Milvus\n"
        f"- Target Locations: {loc_str} (Remote-first India / Hyderabad hybrid / Global remote open to India)\n"
        f"- Experience Bracket: Strictly 2–3 years (1-3, 2-3, 2-4 years max). Strictly DO NOT include Principal, Architect, Staff, or roles asking for >3 years.\n"
        f"- Portal Strategy: Search official company career portals, direct ATS systems (Ashby, Greenhouse, Lever, Workday), and verified company postings\n\n"
        f"SEARCH FRESHNESS & DIVERSITY MANDATE:\n"
        f"1. Discover FRESH and DIVERSE job opportunities currently active and hiring. Do NOT repeat only previously seen static results.\n"
        f"2. Explore emerging AI startups, high-growth tech companies, and enterprise engineering teams across Hyderabad and Remote-India.\n"
        f"3. Verify active status, extract real company application links, and return structured JSON.\n\n"
        f"TARGET SEARCH QUERIES TO EXECUTE:\n"
    )
    for q in queries:
        prompt += f"• {q}\n"

    prompt += "\nExecute web research across active career pages, discover newly posted roles, verify they are currently open, and return structured JSON."
    return prompt
