import logging
import json
import re
from typing import List, Dict, Any, Optional
from app.schemas.schemas import SearchCriteria, CandidateProfileBase
from app.integrations.openai.schemas import (
    JobResearchResponse,
    JobResearchResult,
    SourceEvidence,
    RecruiterResearchResult
)
from app.integrations.openai.client import openai_client_wrapper
from app.integrations.openai.prompts import (
    JOB_RESEARCH_INSTRUCTIONS,
    RECRUITER_RESEARCH_INSTRUCTIONS,
    build_job_research_prompt
)
from app.config.settings import settings

logger = logging.getLogger(__name__)

class OpenAIWebResearchService:
    """
    Intelligent Web Research engine utilizing the OpenAI Responses API
    with the built-in Web Search tool to discover active, verified career postings.
    """

    def generate_search_queries(self, criteria: SearchCriteria) -> List[str]:
        import random
        queries = []
        roles = criteria.roles or ["AI Engineer", "Generative AI Engineer", "Agentic AI Engineer", "Applied AI Engineer", "RAG Engineer", "LLM Engineer"]
        top_skills = criteria.skills[:4] if criteria.skills else ["Python", "RAG", "LangGraph", "FastAPI"]
        skills_text = " ".join(top_skills)
        loc = "remote India" if criteria.remote_required else "India"

        # 1. Direct ATS Boards (Ashby, Greenhouse, Lever, Workday)
        ats_queries = [
            'site:jobs.ashbyhq.com ("AI Engineer" OR "GenAI" OR "Agentic AI") ("India" OR "Remote")',
            'site:boards.greenhouse.io ("AI Engineer" OR "Generative AI" OR "RAG") ("India" OR "Remote")',
            'site:jobs.lever.co ("Applied AI Engineer" OR "LLM Engineer") ("India" OR "Remote")',
            'site:myworkdayjobs.com ("AI Engineer" OR "Generative AI") "India"',
            'site:workatastartup.com ("AI Engineer" OR "LangGraph" OR "RAG") ("India" OR "Remote")'
        ]

        # 2. Targeted Role + Tech Stack queries
        stack_queries = [
            f'"Agentic AI Engineer" ("LangGraph" OR "MCP" OR "Python") {loc} careers',
            f'"RAG Engineer" ("Milvus" OR "Bedrock" OR "FastAPI") {loc} apply',
            f'"Applied AI Engineer" ("LLM" OR "RAGAS" OR "DeepEval") {loc}',
            f'"Generative AI Engineer" {skills_text} ("Remote India" OR "Hyderabad") careers',
            f'"AI Backend Engineer" "FastAPI" "Python" ("AWS" OR "Bedrock") {loc}',
            f'"AI Engineer" "Hyderabad" ("hybrid" OR "remote") "apply now"'
        ]

        # 3. Startup & Fresh Hiring Portals
        startup_queries = [
            f'AI startup hiring "AI Engineer" ("Remote India" OR "Hyderabad") 2025 OR 2026',
            f'SaaS company "Generative AI Engineer" ("India" OR "Remote") career page',
            f'"LangGraph" OR "Agentic AI" developer jobs India remote',
            f'"LLM-as-a-Judge" OR "RAGAS" AI Engineer careers India'
        ]

        # Combine, shuffle subset, and deduplicate
        all_pools = ats_queries + stack_queries + startup_queries
        random.shuffle(all_pools)
        queries.extend(all_pools[:10])

        for role in roles[:3]:
            queries.append(f'"{role}" {skills_text} {loc} careers')

        return list(dict.fromkeys(queries))

    async def search_jobs(
        self,
        search_criteria: SearchCriteria,
        candidate_profile: Optional[CandidateProfileBase] = None
    ) -> JobResearchResponse:
        """
        Executes multi-query web research using OpenAI Responses API + Web Search.
        """
        queries = self.generate_search_queries(search_criteria)
        user_prompt = build_job_research_prompt(search_criteria, queries, candidate_profile)

        if not openai_client_wrapper.is_configured() or not settings.OPENAI_WEB_SEARCH_ENABLED:
            logger.warning("OpenAI Web Search is disabled or API key missing. Delegating to fallback providers.")
            return JobResearchResponse(jobs=[], search_queries=queries, total_found=0)

        try:
            response = await openai_client_wrapper.create_web_search_response(
                instructions=JOB_RESEARCH_INSTRUCTIONS,
                input_prompt=user_prompt,
                model=settings.effective_openai_model,
                context_size=settings.OPENAI_WEB_SEARCH_CONTEXT_SIZE
            )

            # Extract output text and citations
            raw_text = getattr(response, "output_text", "")
            if not raw_text and hasattr(response, "output"):
                for item in response.output:
                    if hasattr(item, "content"):
                        for part in item.content:
                            if hasattr(part, "text"):
                                raw_text += part.text + "\n"

            # Parse JSON from model output
            parsed_data = self._extract_json_from_text(raw_text)
            if parsed_data and "jobs" in parsed_data:
                jobs_list = []
                for j in parsed_data.get("jobs", []):
                    try:
                        job_obj = JobResearchResult(**j)
                        jobs_list.append(job_obj)
                    except Exception as err:
                        logger.warning(f"Error validating JobResearchResult ({err}): {j.get('title')}")

                logger.info(f"OpenAI Web Search extracted {len(jobs_list)} verified job postings.")
                return JobResearchResponse(
                    jobs=jobs_list,
                    search_queries=queries,
                    total_found=len(jobs_list)
                )

        except Exception as e:
            logger.error(f"OpenAI Web Research failed: {e}. Falling back to auxiliary search providers.")

        return JobResearchResponse(jobs=[], search_queries=queries, total_found=0)

    async def research_recruiter(
        self,
        company_name: str,
        job_title: str
    ) -> Optional[RecruiterResearchResult]:
        """
        Executes targeted recruiter and talent acquisition research via OpenAI Web Search (only for strong matches).
        """
        if not openai_client_wrapper.is_configured() or not settings.OPENAI_WEB_SEARCH_ENABLED:
            return None

        prompt = (
            f"Find publicly listed recruiting or talent acquisition partners for:\n"
            f"Company: {company_name}\n"
            f"Role: {job_title}\n\n"
            f"Search queries to consider:\n"
            f'• "{company_name}" "technical recruiter" linkedin\n'
            f'• "{company_name}" "talent acquisition" recruiter\n\n'
            f"Extract recruiter name, title, and public profile link. DO NOT GUESS EMAILS."
        )

        try:
            response = await openai_client_wrapper.create_web_search_response(
                instructions=RECRUITER_RESEARCH_INSTRUCTIONS,
                input_prompt=prompt,
                model=settings.effective_openai_model
            )

            raw_text = getattr(response, "output_text", "")
            parsed = self._extract_json_from_text(raw_text)
            if parsed:
                return RecruiterResearchResult(**parsed)
        except Exception as e:
            logger.info(f"Recruiter OpenAI research failed for {company_name}: {e}")

        return None

    def _extract_json_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        # Try direct JSON parsing
        try:
            return json.loads(text.strip())
        except Exception:
            pass

        # Try regex block parsing ```json ... ```
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except Exception:
                pass

        # Try finding outermost { ... }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except Exception:
                pass

        return None

openai_web_research = OpenAIWebResearchService()
