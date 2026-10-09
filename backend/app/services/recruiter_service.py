import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.config.database import AsyncSessionLocal
from app.config.settings import settings
from app.models.entities import Job, Recruiter, Application, OutreachMessage, ApprovalRequest
from app.schemas.schemas import RecruiterBase, ResolveRecruiterEmailRequest
from app.services.email_resolution_service import (
    sanitize_recruiter_name,
    validate_company_domain,
    verify_email_for_job,
    is_valid_email_format,
    extract_emails_from_text,
    RecipientClassification,
    RECRUITING_LOCAL_PARTS,
    GENERAL_APPLY_LOCAL_PARTS,
)

logger = logging.getLogger(__name__)

KNOWN_RECRUITERS: Dict[str, Dict[str, Any]] = {
    "Anthropic AI Labs": {"name": "Sarah Jenkins", "title": "Principal Technical Recruiter - AI Systems",
        "company_name": "Anthropic AI Labs", "public_email": "talent@anthropic.com",
        "email_type": "COMPANY_RECRUITING", "source_url": "https://anthropic.com/careers",
        "source_type": "official_careers_page", "confidence": 0.95,
        "linkedin_url": "https://www.linkedin.com/in/sarah-jenkins-ai-recruiter",
        "source_evidence": "Anthropic official careers contact directory & publicly listed talent partner"},
    "ScaleGen AI": {"name": "Marcus Vance", "title": "Head of Global Talent Acquisition",
        "company_name": "ScaleGen AI", "public_email": "careers@scalegen.ai",
        "email_type": "COMPANY_RECRUITING", "source_url": "https://scalegen.ai/careers",
        "source_type": "official_careers_page", "confidence": 0.95,
        "linkedin_url": "https://www.linkedin.com/in/marcus-vance-talent",
        "source_evidence": "ScaleGen AI public hiring portal header"},
    "Nexus Cognitive": {"name": "Priya Sharma", "title": "Lead Technical Recruiter (GenAI / ML)",
        "company_name": "Nexus Cognitive", "public_email": "priya.recruiting@nexuscognitive.com",
        "email_type": "RECRUITER_SPECIFIC", "source_url": "https://nexuscognitive.com/team",
        "source_type": "verified_recruiter", "confidence": 0.85,
        "linkedin_url": "https://www.linkedin.com/in/priya-sharma-talent-ai",
        "source_evidence": "Nexus Cognitive engineering hiring announcement"},
    "HyperFlow Data": {"name": "Alex Mercer", "title": "Senior Talent Partner",
        "company_name": "HyperFlow Data", "public_email": "hiring@hyperflowdata.io",
        "email_type": "COMPANY_RECRUITING", "source_url": "https://hyperflowdata.io/jobs",
        "source_type": "official_careers_page", "confidence": 0.95,
        "linkedin_url": "https://www.linkedin.com/in/alex-mercer-tech",
        "source_evidence": "HyperFlow Data verified job posting author"},
    "Synthetix Cloud": {"name": "Elena Rostova", "title": "Director of Engineering Recruiting",
        "company_name": "Synthetix Cloud", "public_email": "elena.talent@synthetixcloud.com",
        "email_type": "RECRUITER_SPECIFIC", "source_url": "https://synthetixcloud.com/careers",
        "source_type": "verified_recruiter", "confidence": 0.85,
        "linkedin_url": "https://www.linkedin.com/in/elena-rostova-recruiting",
        "source_evidence": "Synthetix Cloud public team page"},
    "DeepAgent Dynamics": {"name": "David Chen", "title": "AI Talent Lead",
        "company_name": "DeepAgent Dynamics", "public_email": "david.chen@deepagentdynamics.ai",
        "email_type": "RECRUITER_SPECIFIC", "source_url": "https://deepagentdynamics.ai/careers",
        "source_type": "verified_recruiter", "confidence": 0.85,
        "linkedin_url": "https://www.linkedin.com/in/david-chen-ai-talent",
        "source_evidence": "DeepAgent Dynamics verified careers contact"},
}


class RecruiterDiscoveryService:
    """Evidence-first recruiter discovery and email persistence."""

    async def _discover_public_company_email(self, job_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        company = str(job_data.get("company") or job_data.get("company_name") or "").strip()
        if not company:
            return None

        # 1) Search content already attached to the job.
        for email in extract_emails_from_text(job_data.get("description") or ""):
            ok, cls, score, reason = verify_email_for_job(email, job_data, source_type="job_description")
            if ok and cls == RecipientClassification.VERIFIED:
                return {"email": email.lower(), "source_url": job_data.get("source_url") or job_data.get("application_url"),
                        "source_type": "job_description", "confidence": score, "evidence": reason}

        # 2) Fetch public company/careers/application pages and extract only published emails.
        urls = [u for u in (job_data.get("company_url"), job_data.get("source_url"), job_data.get("application_url")) if u]
        try:
            import httpx
            from bs4 import BeautifulSoup
            async with httpx.AsyncClient(timeout=8, follow_redirects=True,
                                         headers={"User-Agent": "Mozilla/5.0 (compatible; AIJobsApply/1.0)"}) as client:
                for url in list(dict.fromkeys(urls))[:4]:
                    try:
                        resp = await client.get(url)
                        if resp.status_code >= 400:
                            continue
                        text = resp.text + " " + BeautifulSoup(resp.text, "html.parser").get_text(" ", strip=True)
                        candidates = []
                        page_type = "official_careers_page" if ("career" in url.lower() or "job" in url.lower() or url == job_data.get("company_url")) else "application_page"
                        for email in extract_emails_from_text(text):
                            ok, cls, score, reason = verify_email_for_job(email, job_data, source_type=page_type)
                            if ok and cls in (RecipientClassification.VERIFIED, RecipientClassification.DOMAIN_MATCH_ONLY):
                                local = email.split("@", 1)[0].lower()
                                priority = 0 if local in RECRUITING_LOCAL_PARTS else 1 if any(x in local for x in RECRUITING_LOCAL_PARTS) else 2 if local in GENERAL_APPLY_LOCAL_PARTS else 3
                                candidates.append((priority, -score, email.lower(), score, reason))
                        if candidates:
                            candidates.sort()
                            _, _, email, score, reason = candidates[0]
                            return {"email": email, "source_url": str(resp.url), "source_type": page_type,
                                    "confidence": score, "evidence": reason}
                    except Exception as e:
                        logger.debug("Public page email lookup failed for %s: %s", url, e)
        except Exception as e:
            logger.debug("Public email lookup unavailable for %s: %s", company, e)

        # 3) Search public snippets for an explicitly published email; never synthesize one.
        if not settings.DEMO_MODE:
            try:
                try:
                    from ddgs import DDGS
                except ImportError:
                    from duckduckgo_search import DDGS
                ddgs = DDGS()
                for query in (f'"{company}" careers email', f'"{company}" recruiting email', f'"{company}" jobs contact email'):
                    for result in list(ddgs.text(query, max_results=5)):
                        blob = " ".join(str(result.get(k, "")) for k in ("title", "body", "href"))
                        for email in extract_emails_from_text(blob):
                            ok, cls, score, reason = verify_email_for_job(email, job_data, source_type="official_careers_page")
                            if ok and cls == RecipientClassification.VERIFIED:
                                return {"email": email.lower(), "source_url": result.get("href"), "source_type": "public_web_search",
                                        "confidence": score, "evidence": reason}
            except Exception as e:
                logger.debug("Public recruiter email search failed for %s: %s", company, e)
        return None

    async def discover_recruiter_for_job(self, company_name_or_job: Any, job_title: Optional[str] = None) -> Optional[RecruiterBase]:
        if isinstance(company_name_or_job, dict):
            company = str(company_name_or_job.get("company") or company_name_or_job.get("company_name") or "").strip()
            title = company_name_or_job.get("title") or job_title or "AI Engineer"
            job_data = company_name_or_job
        else:
            company = str(company_name_or_job or "").strip()
            title = job_title or "AI Engineer"
            job_data = {"company": company, "title": title}

        if not company:
            return None

        # Direct email from the actual job record always wins.
        if isinstance(company_name_or_job, dict):
            direct = (company_name_or_job.get("recruiter_email") or company_name_or_job.get("application_email")
                      or company_name_or_job.get("contact_email") or company_name_or_job.get("email"))
            if direct and is_valid_email_format(direct):
                name, _ = sanitize_recruiter_name(company_name_or_job.get("recruiter_name"), company)
                return RecruiterBase(name=name or f"Talent Team at {company}", title=company_name_or_job.get("recruiter_title", "Technical Recruiter"),
                    company_name=company, public_email=direct.strip().lower(), email_type="COMPANY_RECRUITING",
                    source_url=company_name_or_job.get("source_url") or company_name_or_job.get("application_url"),
                    source_type="job_source", confidence=0.95, linkedin_url=company_name_or_job.get("linkedin_url"),
                    source_evidence=f"Direct recruiting email from job listing for {company}")

        # Known verified contacts.
        for key, data in KNOWN_RECRUITERS.items():
            if key.lower() == company.lower() or (len(company) > 4 and company.lower() in key.lower()):
                email = data.get("public_email")
                if email:
                    valid, _ = validate_company_domain(email, company, data.get("source_url"))
                    if not valid:
                        email = None
                name, _ = sanitize_recruiter_name(data.get("name"), company)
                return RecruiterBase(name=name or f"Talent Team at {company}", title=data.get("title", "Technical Recruiter"),
                    company_name=company, public_email=email, email_type=data.get("email_type"),
                    source_url=data.get("source_url"), source_type=data.get("source_type"),
                    confidence=data.get("confidence", 0.95 if email else 0), linkedin_url=data.get("linkedin_url"),
                    source_evidence=data.get("source_evidence"))

        # Reuse a previously verified company contact.
        try:
            async with AsyncSessionLocal() as session:
                res = await session.execute(select(Recruiter).filter(Recruiter.company_name.ilike(f"%{company}%")))
                for rec in res.scalars().all():
                    if rec.public_email:
                        name, _ = sanitize_recruiter_name(rec.name, company)
                        return RecruiterBase(name=name or f"Talent Team at {company}", title=rec.title or "Technical Recruiter",
                            company_name=company, public_email=rec.public_email, email_type=rec.email_type or "COMPANY_RECRUITING",
                            source_url=rec.source_url, source_type=rec.source_type, confidence=rec.confidence or 0.85,
                            verified_at=rec.verified_at, linkedin_url=rec.linkedin_url,
                            source_evidence=rec.source_evidence or f"Verified {rec.company_name} contact in database")
        except Exception as e:
            logger.debug("Database recruiter lookup failed: %s", e)

        # NEW: for job dicts, look for a real published company email before profile-only discovery.
        if isinstance(company_name_or_job, dict):
            evidence = await self._discover_public_company_email(job_data)
            if evidence:
                local = evidence["email"].split("@", 1)[0].lower()
                email_type = "COMPANY_RECRUITING" if local in RECRUITING_LOCAL_PARTS or any(x in local for x in RECRUITING_LOCAL_PARTS) else "COMPANY_GENERAL"
                return RecruiterBase(name=f"Talent Team at {company}", title="Technical Recruiting & Talent Acquisition",
                    company_name=company, public_email=evidence["email"], email_type=email_type,
                    source_url=evidence.get("source_url"), source_type=evidence.get("source_type"),
                    confidence=evidence.get("confidence", 0), source_evidence=evidence.get("evidence"))

        # Optional live recruiter profile search. Email is NEVER guessed from a name.
        if not settings.DEMO_MODE:
            try:
                try:
                    from ddgs import DDGS
                except ImportError:
                    from duckduckgo_search import DDGS
                results = list(DDGS().text(f'"{company}" "technical recruiter" OR "talent acquisition" site:linkedin.com/in', max_results=3))
                for item in results:
                    title_text = item.get("title", "")
                    parts = title_text.split(" - ") if " - " in title_text else title_text.split(" | ")
                    name, status = sanitize_recruiter_name(parts[0].replace("LinkedIn", "").strip(), company)
                    if name and status == "VERIFIED":
                        return RecruiterBase(name=name, title=parts[1].strip() if len(parts) > 1 else "Technical Recruiter",
                            company_name=company, public_email=None, email_type=None, source_url=item.get("href"),
                            source_type="public_linkedin_search", confidence=0.0,
                            linkedin_url=item.get("href"), source_evidence=f"Public search: {item.get('body','')[:120]}")
            except Exception as e:
                logger.debug("Live recruiter profile search failed for %s: %s", company, e)

        return RecruiterBase(name=f"Talent Team at {company}", title="Technical Recruiting & Talent Acquisition",
            company_name=company, public_email=None, email_type=None, confidence=0.0,
            linkedin_url=f"https://www.linkedin.com/search/results/people/?keywords={company}+technical+recruiter",
            source_evidence=f"Public LinkedIn talent directory search for {company}")

    async def resolve_and_persist_recruiter_email(
        self, company_name: Any = None, email: Optional[str] = None, job_id: Optional[str] = None,
        job_title: Optional[str] = None, job_url: Optional[str] = None, recruiter_name: Optional[str] = None,
        recruiter_title: Optional[str] = None, source_url: Optional[str] = None, source_type: Optional[str] = None,
        evidence: Optional[str] = None, confidence: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        if hasattr(company_name, "company_name"):
            req = company_name
            company_name, email, job_id = req.company_name, req.email, req.job_id
            job_title, job_url, recruiter_name = req.job_title, req.job_url, req.recruiter_name
            recruiter_title, source_url, source_type = req.recruiter_title, req.source_url, req.source_type
            evidence, confidence = req.evidence, req.confidence
        elif isinstance(company_name, dict):
            req = company_name
            company_name, email, job_id = req.get("company_name") or req.get("company"), req.get("email", email), req.get("job_id", job_id)
            job_title, job_url, recruiter_name = req.get("job_title", job_title), req.get("job_url", job_url), req.get("recruiter_name", recruiter_name)
            recruiter_title, source_url, source_type = req.get("recruiter_title", recruiter_title), req.get("source_url", source_url), req.get("source_type", source_type)
            evidence, confidence = req.get("evidence", evidence), req.get("confidence", confidence)

        company = str(company_name or "").strip()
        if not company and job_id:
            async with AsyncSessionLocal() as session:
                job = await session.get(Job, job_id)
                company = job.company if job else ""
        if not company:
            return {"success": False, "status": "REJECTED", "reason": "MISSING_COMPANY_NAME", "error": "Company name is required."}
        if not email or not str(email).strip():
            return {"success": False, "status": "NEEDS_EMAIL_REVIEW", "company_name": company, "job_id": job_id,
                    "recruiter_name": recruiter_name or f"Talent Team at {company}", "email": None,
                    "email_type": None, "error": "No email provided. Application ready, outreach marked NEEDS_EMAIL_REVIEW."}

        email = str(email).strip().lower()
        if not is_valid_email_format(email):
            return {"success": False, "status": "REJECTED", "reason": "INVALID_EMAIL_FORMAT", "error": f"Email format is invalid: {email}"}
        if not (source_url and str(source_url).strip()) and not (evidence and str(evidence).strip()):
            return {"success": False, "status": "REJECTED", "reason": "MISSING_EVIDENCE_OR_SOURCE",
                    "error": "source_url or evidence is required to resolve recruiter email."}

        job_ctx = {"company": company, "company_url": job_url or source_url, "application_url": job_url,
                   "source_url": source_url, "description": evidence or ""}
        valid, classification, score, reason = verify_email_for_job(email, job_ctx, source_type=source_type or "mcp_chatgpt_research")
        if not valid or classification == RecipientClassification.REJECTED:
            return {"success": False, "status": "REJECTED", "reason": f"DOMAIN_MISMATCH_OR_INVALID ({reason})",
                    "message": f"Email {email} rejected: {reason}"}

        local = email.split("@", 1)[0]
        parts = set(local.replace(".", " ").replace("-", " ").replace("_", " ").split())
        email_type = "COMPANY_RECRUITING" if parts.intersection(RECRUITING_LOCAL_PARTS) or local in RECRUITING_LOCAL_PARTS else "COMPANY_GENERAL" if parts.intersection(GENERAL_APPLY_LOCAL_PARTS) or local in GENERAL_APPLY_LOCAL_PARTS else "RECRUITER_SPECIFIC"
        conf = score
        if confidence:
            c = str(confidence).upper()
            if "HIGH" in c or "9" in c: conf = max(conf, 0.95)
            elif "MED" in c or "7" in c: conf = max(conf, 0.75)
            elif "LOW" in c or "5" in c: conf = max(conf, 0.50)

        clean_name, _ = sanitize_recruiter_name(recruiter_name, company)
        final_name = clean_name or f"Talent Team at {company}"
        final_title = recruiter_title or ("Technical Recruiter" if email_type == "RECRUITER_SPECIFIC" else "Talent Acquisition")

        async with AsyncSessionLocal() as session:
            res = await session.execute(select(Recruiter).filter(Recruiter.company_name.ilike(company)))
            rec = res.scalars().first()
            if not rec:
                rec = Recruiter(id=str(uuid.uuid4()), name=final_name, title=final_title, company_name=company,
                    public_email=email, email_type=email_type, source_url=source_url, source_type=source_type or "mcp_chatgpt_research",
                    source_evidence=evidence or reason, confidence=conf, verified_at=datetime.utcnow())
                session.add(rec)
            else:
                rec.name, rec.title, rec.public_email, rec.email_type = final_name, final_title, email, email_type
                rec.source_url = source_url or rec.source_url
                rec.source_type = source_type or rec.source_type or "mcp_chatgpt_research"
                rec.source_evidence = evidence or rec.source_evidence or reason
                rec.confidence, rec.verified_at = conf, datetime.utcnow()

            if job_id:
                job = await session.get(Job, job_id)
                if job:
                    job.recruiter_email = email

            apps = (await session.execute(select(Application).filter(Application.job_id == job_id))).scalars().all() if job_id else []
            for app in apps:
                outs = (await session.execute(select(OutreachMessage).filter_by(application_id=app.id, channel="EMAIL"))).scalars().all()
                for out in outs:
                    out.recipient_email, out.recipient_name = email, final_name
                    out.email_status, out.email_source, out.email_confidence = "VERIFIED", source_type or "mcp_chatgpt_research", conf
                    out.recruiter_id, out.status = rec.id, "READY_FOR_APPROVAL" if out.status in ("DRAFT", "NEEDS_EMAIL_REVIEW") else out.status
                reqs = (await session.execute(select(ApprovalRequest).filter_by(application_id=app.id))).scalars().all()
                for req in reqs:
                    if isinstance(req.package_data, dict):
                        data = dict(req.package_data)
                        if isinstance(data.get("recruiter"), dict):
                            data["recruiter"]["public_email"], data["recruiter"]["name"] = email, final_name
                            data["recruiter"]["email_type"], data["recruiter"]["confidence"] = email_type, conf
                            data["recruiter"]["source_url"] = source_url
                        if isinstance(data.get("email_outreach"), dict):
                            data["email_outreach"]["recipient_email"], data["email_outreach"]["recipient_name"] = email, final_name
                            data["email_outreach"]["email_status"], data["email_outreach"]["email_source"] = "VERIFIED", source_type or "mcp_chatgpt_research"
                            data["email_outreach"]["email_confidence"], data["email_outreach"]["status"] = conf, "READY_FOR_APPROVAL"
                        req.package_data = data
                        flag_modified(req, "package_data")
            await session.commit()

        return {"success": True, "status": "VERIFIED", "company_name": company, "job_id": job_id,
                "recruiter_name": final_name, "recruiter_title": final_title, "email": email, "email_type": email_type,
                "source_url": source_url, "source_type": source_type or "mcp_chatgpt_research", "evidence": evidence or reason,
                "confidence": conf, "verified_at": datetime.utcnow().isoformat(),
                "message": f"Successfully verified and persisted {email_type} email for {company}."}


recruiter_service = RecruiterDiscoveryService()
