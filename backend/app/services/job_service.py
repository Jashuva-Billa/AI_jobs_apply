import re
import hashlib
import logging
from typing import List, Dict, Any, Tuple
from app.schemas.schemas import SearchCriteria, JobBase, JobResponse
from app.integrations.web.search import web_job_search
from app.integrations.llm.provider import llm_provider

logger = logging.getLogger(__name__)

class JobResearchService:
    """Handles multi-query generation, web/career portal searching, normalization, and deduplication."""

    def generate_search_queries(self, criteria: SearchCriteria) -> List[str]:
        """Generates multiple search strategies based on roles and skills."""
        queries = []
        roles = criteria.roles or ["AI Engineer", "GenAI Engineer", "ML Engineer", "LLM Engineer"]
        top_skills = criteria.skills[:3] if criteria.skills else ["Python", "RAG", "LangGraph"]
        skill_suffix = " " + " ".join(top_skills)

        for role in roles:
            queries.append(f"{role}{skill_suffix}")
            queries.append(f"{role} remote India")
            queries.append(f"{role} company careers")
        
        # Add specialized queries
        queries.append("Agentic AI Engineer remote")
        queries.append("RAG LangGraph Engineer")
        return list(dict.fromkeys(queries)) # Deduplicate queries

    def normalize_string(self, text: str) -> str:
        if not text:
            return ""
        return re.sub(r"[^a-zA-Z0-9]", "", text).lower()

    def generate_canonical_id(self, company: str, title: str, location: str, app_url: str = "") -> str:
        """Generates deterministic canonical hash: company + normalized job title + location."""
        norm_company = self.normalize_string(company)
        norm_title = self.normalize_string(title)
        norm_loc = "remote" if "remote" in location.lower() else self.normalize_string(location)
        raw_key = f"{norm_company}_{norm_title}_{norm_loc}"
        return hashlib.md5(raw_key.encode("utf-8")).hexdigest()

    async def search_and_deduplicate(self, criteria: SearchCriteria) -> Tuple[List[Dict[str, Any]], int, int]:
        """
        Executes multi-query search, extracts structured jobs, normalizes, and deduplicates.
        Returns: (deduplicated_jobs, total_raw_count, duplicates_removed_count)
        """
        queries = self.generate_search_queries(criteria)
        logger.info(f"Generated {len(queries)} search strategies: {queries[:3]}...")

        raw_jobs = await web_job_search.search_jobs(
            queries=queries,
            locations=criteria.locations,
            remote_only=criteria.remote_required,
            criteria=criteria
        )
        total_raw = len(raw_jobs)

        # Deduplicate using canonical ID and link aggregation
        seen_map: Dict[str, Dict[str, Any]] = {}
        duplicates_removed = 0

        for item in raw_jobs:
            canonical_id = self.generate_canonical_id(
                company=item.get("company", ""),
                title=item.get("title", ""),
                location=item.get("location", "Remote"),
                app_url=item.get("application_url", "")
            )

            if canonical_id in seen_map:
                duplicates_removed += 1
                existing = seen_map[canonical_id]
                source_urls = existing.get("source_urls", [])
                new_src = item.get("source_url") or item.get("application_url")
                if new_src and new_src not in source_urls:
                    source_urls.append(new_src)
                existing["source_urls"] = source_urls
            else:
                item_copy = item.copy()
                item_copy["canonical_job_id"] = canonical_id
                src = item_copy.get("source_url") or item_copy.get("application_url")
                item_copy["source_urls"] = [src] if src else []
                seen_map[canonical_id] = item_copy

        deduplicated = list(seen_map.values())
        logger.info(f"Search complete: Found {total_raw} jobs, removed {duplicates_removed} duplicates, {len(deduplicated)} unique.")
        return deduplicated, total_raw, duplicates_removed

job_service = JobResearchService()
