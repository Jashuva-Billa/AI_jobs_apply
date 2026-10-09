import re
import logging
from typing import Dict, Any, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Application, Job, ApprovalRequest, ApplicationStatus, ApprovalStatus

logger = logging.getLogger(__name__)

def normalize_title(title: str) -> str:
    """Normalizes job title for deduplication comparison."""
    if not title:
        return ""
    clean = title.lower()
    clean = re.sub(r'[\(\[\{].*?[\)\]\}]', '', clean)
    clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', clean)
    words = [w for w in clean.split() if w not in {"senior", "sr", "lead", "staff", "principal", "junior", "jr", "remote", "fulltime", "full", "time"}]
    return " ".join(words).strip()

class DuplicateProtectionService:
    """Protects candidate pipeline from duplicate application preparation or dispatch."""

    async def check_duplicate_job(
        self,
        session: AsyncSession,
        candidate_id: str,
        job_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Checks if a job has already been processed for the candidate.
        Checks:
        1. Exact job_id match in applications
        2. canonical_job_id match
        3. source_url / application_url match
        4. company + normalized title match

        Returns:
        (is_duplicate: bool, existing_application_id: Optional[str], reason: Optional[str])
        """
        job_id = job_data.get("id")
        canonical_id = job_data.get("canonical_job_id")
        company = (job_data.get("company") or "").strip().lower()
        title = job_data.get("title") or ""
        norm_title = normalize_title(title)
        app_url = job_data.get("application_url")
        src_url = job_data.get("source_url")

        # 1. Check existing applications for candidate
        query = select(Application, Job).join(Job, Application.job_id == Job.id).filter(
            Application.candidate_id == candidate_id
        )
        res = await session.execute(query)
        records = res.all()

        for app_rec, job_rec in records:
            if job_id and app_rec.job_id == job_id:
                status_str = app_rec.status.value if hasattr(app_rec.status, "value") else str(app_rec.status)
                return True, app_rec.id, f"Exact job_id '{job_id}' already has application {app_rec.id} ({status_str})"

            # Check Canonical ID match
            if canonical_id and job_rec.canonical_job_id == canonical_id:
                return True, app_rec.id, f"Canonical ID '{canonical_id}' already processed in application {app_rec.id}"

            # Check URLs
            if src_url and job_rec.source_url and src_url == job_rec.source_url:
                return True, app_rec.id, f"Source URL '{src_url}' already processed in application {app_rec.id}"

            if app_url and job_rec.application_url and app_url == job_rec.application_url:
                return True, app_rec.id, f"Application URL '{app_url}' already processed in application {app_rec.id}"

            # Check Company + Normalized Title
            rec_comp = (job_rec.company or "").strip().lower()
            rec_norm_title = normalize_title(job_rec.title or "")
            if company and rec_comp == company and norm_title and rec_norm_title == norm_title:
                return True, app_rec.id, f"Company '{company}' with matching role '{norm_title}' already exists in application {app_rec.id}"

        return False, None, None

duplicate_protection = DuplicateProtectionService()
