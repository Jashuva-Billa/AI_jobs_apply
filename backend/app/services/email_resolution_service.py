import re
import urllib.parse
import logging
from typing import Dict, Any, Optional, List, Tuple, Set
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Standard known ATS / Recruiting platform domains
ALLOWED_ATS_DOMAINS = {
    "greenhouse.io",
    "boards.greenhouse.io",
    "lever.co",
    "jobs.lever.co",
    "workday.com",
    "myworkdayjobs.com",
    "ashbyhq.com",
    "jobs.ashbyhq.com",
    "smartrecruiters.com",
    "jobs.smartrecruiters.com",
    "bamboohr.com",
    "workable.com",
    "apply.workable.com",
    "breezy.hr",
    "recruitee.com",
    "rippling-ats.com",
    "icims.com",
    "jobvite.com",
    "jazzhr.com",
    "applytojob.com",
}

# Suspicious / spam keywords in recruiter names (e.g. SEO junk, movie torrents, ads)
SPAM_NAME_KEYWORDS = {
    "download", "movie", "movies", "torrent", "hindi", "bollywood", "hollywood",
    "watch", "stream", "free", "full hd", "mp4", "mkv", "720p", "1080p", "vegamovies",
    "crack", "keygen", "serial", "apk", "mod", "cheats", "seo", "backlink", "casino",
    "poker", "slots", "dating", "viagra", "pharmacy", "cheap", "buy now", "click here",
    "http", "https", "www", ".com", ".org", ".net", ".io", ".co", ".in", ".xyz"
}

# Known corporate aliases & parent/subsidiary mappings (controlled alias mechanism)
KNOWN_COMPANY_ALIASES = {
    "google": {"google.com", "deepmind.com", "alphabet.com"},
    "deepmind": {"deepmind.com", "google.com"},
    "meta": {"meta.com", "facebook.com", "fb.com", "instagram.com"},
    "facebook": {"meta.com", "facebook.com", "fb.com"},
    "microsoft": {"microsoft.com", "linkedin.com", "github.com"},
    "amazon": {"amazon.com", "aws.amazon.com", "amazon.jobs"},
    "apple": {"apple.com", "jobs.apple.com"},
    "anthropic": {"anthropic.com"},
    "openai": {"openai.com"},
    "scale ai": {"scale.com", "scalegen.ai"},
    "scalegen": {"scalegen.ai", "scale.com"},
}

# Local-part keywords for recruiting priority
RECRUITING_LOCAL_PARTS = {"recruiting", "recruitment", "careers", "career", "jobs", "job", "talent", "hiring", "hr", "people"}
GENERAL_APPLY_LOCAL_PARTS = {"apply", "contact", "join", "team"}
GENERIC_LOCAL_PARTS = {"info", "support", "help", "sales", "marketing", "hello", "general", "admin", "office"}

# Strict regex for email extraction
EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')

# Public consumer mailboxes that cannot be official company addresses
PUBLIC_CONSUMER_MAILBOXES = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "icloud.com", "proton.me", "protonmail.com", "aol.com", "zoho.com"
}

class RecipientClassification:
    VERIFIED = "VERIFIED"
    DOMAIN_MATCH_ONLY = "DOMAIN_MATCH_ONLY"
    UNVERIFIED = "UNVERIFIED"
    NOT_FOUND = "NOT_FOUND"
    REJECTED = "REJECTED"
    BLOCKED_INVALID_RECIPIENT = "BLOCKED_INVALID_RECIPIENT"

class EmailResolutionResult(BaseModel):
    email: Optional[str] = None
    status: str = RecipientClassification.NOT_FOUND # VERIFIED, DOMAIN_MATCH_ONLY, UNVERIFIED, NOT_FOUND, REJECTED
    email_type: Optional[str] = "COMPANY_RECRUITING"
    source: Optional[str] = None # job_source, job_description, application_page, official_careers_page, verified_recruiter, manual
    source_url: Optional[str] = None
    company: str = ""
    confidence: float = 0.0
    recruiter_name: Optional[str] = None
    recruiter_status: str = "NOT_FOUND" # VERIFIED, UNVERIFIED, NOT_FOUND
    validation_reason: Optional[str] = None
    send_allowed: bool = False

def normalize_domain(domain_or_url: Optional[str]) -> str:
    """
    Extracts and normalizes clean host domain.
    Strips http/https, www, port, paths, query strings, and trailing slashes.
    """
    if not domain_or_url:
        return ""
    text = domain_or_url.strip().lower()
    if "://" not in text and not text.startswith("//"):
        text = "https://" + text
    try:
        parsed = urllib.parse.urlparse(text)
        netloc = parsed.netloc or parsed.path
        # Strip port if present
        netloc = netloc.split(":")[0]
        # Strip leading www., www2.
        if netloc.startswith("www."):
            netloc = netloc[4:]
        elif netloc.startswith("www2."):
            netloc = netloc[5:]
        return netloc.strip().rstrip("/")
    except Exception:
        return ""

def clean_company_slug(company_name: str) -> str:
    """Generates simplified alphanumeric slug from company name."""
    if not company_name:
        return ""
    # Remove common corporate suffixes
    clean = re.sub(r'\b(inc|corp|corporation|llc|ltd|limited|technologies|tech|ai|labs|group|solutions|software|systems)\b', '', company_name, flags=re.IGNORECASE)
    clean = re.sub(r'[^a-zA-Z0-9]', '', clean).lower()
    return clean

def is_valid_email_format(email: Optional[str]) -> bool:
    """Checks strict RFC-compliant email syntax."""
    if not email or not isinstance(email, str):
        return False
    email = email.strip()
    if len(email) < 6 or len(email) > 254:
        return False
    if ".." in email or email.startswith(".") or email.endswith("."):
        return False
    parts = email.split("@")
    if len(parts) != 2:
        return False
    local, domain = parts
    if not local or not domain or "." not in domain:
        return False
    if len(domain.split(".")[-1]) < 2:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+$', email))

def sanitize_recruiter_name(raw_name: Optional[str], company_name: Optional[str] = None) -> Tuple[Optional[str], str]:
    """
    Sanitizes candidate recruiter names.
    Rejects SEO spam titles (e.g. Vegamovies, download sites, search junk), URLs, and malformed strings.
    Returns: (cleaned_name or None, status: 'VERIFIED' | 'UNVERIFIED' | 'NOT_FOUND')
    """
    if not raw_name or not isinstance(raw_name, str):
        return None, "NOT_FOUND"

    name = raw_name.strip()

    # Check for empty or generic placeholder
    if not name or name.lower() in {"hiring team", "talent team", "recruiter", "talent acquisition", "none", "null", "n/a"}:
        return None, "NOT_FOUND"

    # Check for spam keywords first
    lower_name = name.lower()
    for kw in SPAM_NAME_KEYWORDS:
        if kw in lower_name:
            logger.warning(f"Rejected spam recruiter name containing '{kw}': {name}")
            return None, "NOT_FOUND"

    # Split on pipe / dash delimiters to isolate person name: "Sarah Jenkins - Technical Recruiter | LinkedIn"
    parts = re.split(r'[\s]+[|\-–—][\s]+', name)
    if parts:
        name = parts[0].strip()

    # Strip bracketed text or URLs
    name = re.sub(r'\(.*?\)|\[.*?\]|\{.*?\}', '', name).strip()

    # Remove trailing LinkedIn / titles
    name = re.sub(r'\s+(LinkedIn|Technical Recruiter|Talent Partner|Recruiter|HR Manager|Lead Recruiter|Staff Recruiter)$', '', name, flags=re.IGNORECASE).strip()

    # Length check: real human names are rarely > 40 chars or < 2 chars
    if len(name) > 40 or len(name) < 2:
        logger.warning(f"Rejected recruiter name '{name}' due to invalid length ({len(name)})")
        return None, "NOT_FOUND"

    # Verify name consists of 2-4 clean alphabetic words
    words = [w for w in name.split() if w.isalpha() or (w.replace(".", "").isalpha())]
    if len(words) < 2 or len(words) > 4:
        logger.warning(f"Rejected recruiter name with suspicious word count ({len(words)}): '{name}'")
        return None, "NOT_FOUND"

    # Must start with uppercase letters
    cleaned = " ".join(words)
    if not re.match(r'^[A-Z][a-zA-Z.\'-]+(?:\s+[A-Z][a-zA-Z.\'-]+)+$', cleaned):
        return None, "NOT_FOUND"

    return cleaned, "VERIFIED"

def verify_email_for_job(
    email: str,
    job_data: Dict[str, Any],
    source_type: Optional[str] = None
) -> Tuple[bool, str, float, str]:
    """
    Validates company domain and calculates deterministic evidence score for an email against a job.
    
    Deterministic Evidence Scoring:
    +1.00 official job description explicitly provides email
    +0.95 official careers page provides email
    +0.90 official application page provides email
    +0.85 verified recruiter contact
    +0.75 company domain + recruiting keyword
    +0.50 company-domain match only
    +0.00 no evidence
    
    Thresholds:
    >= 0.85 -> VERIFIED
    0.50-0.84 -> DOMAIN_MATCH_ONLY
    0.01-0.49 -> UNVERIFIED
    0 -> NOT_FOUND
    Contradiction / Mismatch -> REJECTED
    
    Returns:
    (is_valid: bool, classification: str, confidence: float, reason: str)
    """
    if not is_valid_email_format(email):
        return False, RecipientClassification.REJECTED, 0.0, "INVALID_SYNTAX"

    company_name = job_data.get("company") or job_data.get("company_name") or ""
    company_url = job_data.get("company_url")
    application_url = job_data.get("application_url")
    source_url = job_data.get("source_url")
    job_description = job_data.get("description") or ""

    email_clean = email.strip().lower()
    email_local, email_domain = email_clean.split("@")
    email_domain = normalize_domain(email_domain)

    # 1. Hardcoded / Blocked Check
    if email_clean == "talent@techcorp.com" and "techcorp" not in company_name.lower():
        return False, RecipientClassification.REJECTED, 0.0, "BLOCKED_HARDCODED_TECHCORP_FALLBACK"

    # 2. Public Consumer Mailbox Check
    if email_domain in PUBLIC_CONSUMER_MAILBOXES:
        return False, RecipientClassification.REJECTED, 0.0, f"REJECTED_PUBLIC_MAILBOX ({email_domain})"

    # 3. Explicit ATS Domain Rule:
    # An ATS domain (greenhouse.io, lever.co, etc.) establishes application portal infrastructure,
    # but does NOT prove an arbitrary email (e.g. jobs@greenhouse.io) belongs to this company.
    for ats in ALLOWED_ATS_DOMAINS:
        if email_domain == ats or email_domain.endswith("." + ats):
            if ats not in company_name.lower():
                return False, RecipientClassification.REJECTED, 0.0, f"REJECTED_ATS_INFRASTRUCTURE_EMAIL ({email_domain} is ATS infrastructure, not employer mailbox)"

    # 4. Domain Ownership Matching
    is_domain_match = False
    domain_match_reason = ""

    # A. Check company_url
    if company_url:
        comp_domain = normalize_domain(company_url)
        if comp_domain and (email_domain == comp_domain or email_domain.endswith("." + comp_domain) or comp_domain.endswith("." + email_domain)):
            is_domain_match = True
            domain_match_reason = f"MATCHED_COMPANY_URL ({comp_domain})"

    # B. Check application_url (if custom domain, not generic ATS)
    if not is_domain_match and application_url:
        app_domain = normalize_domain(application_url)
        if app_domain and app_domain not in ALLOWED_ATS_DOMAINS:
            if email_domain == app_domain or email_domain.endswith("." + app_domain) or app_domain.endswith("." + email_domain):
                is_domain_match = True
                domain_match_reason = f"MATCHED_APPLICATION_URL ({app_domain})"

    # C. Check source_url
    if not is_domain_match and source_url:
        src_domain = normalize_domain(source_url)
        if src_domain and src_domain not in ALLOWED_ATS_DOMAINS:
            if email_domain == src_domain or email_domain.endswith("." + src_domain) or src_domain.endswith("." + email_domain):
                is_domain_match = True
                domain_match_reason = f"MATCHED_SOURCE_URL ({src_domain})"

    # D. Check controlled company aliases
    if not is_domain_match:
        for alias_key, alias_domains in KNOWN_COMPANY_ALIASES.items():
            if alias_key in company_name.lower() or company_name.lower() in alias_key:
                if any(email_domain == ad or email_domain.endswith("." + ad) for ad in alias_domains):
                    is_domain_match = True
                    domain_match_reason = f"MATCHED_CONTROLLED_ALIAS ({alias_key})"
                    break

    # E. Check fuzzy company name slug
    if not is_domain_match:
        comp_slug = clean_company_slug(company_name)
        domain_slug = re.sub(r'[^a-zA-Z0-9]', '', email_domain.split(".")[0]).lower()
        if comp_slug and domain_slug and (comp_slug in domain_slug or domain_slug in comp_slug):
            is_domain_match = True
            domain_match_reason = f"MATCHED_COMPANY_SLUG ({comp_slug} ~ {domain_slug})"

    if not is_domain_match:
        return False, RecipientClassification.REJECTED, 0.0, f"DOMAIN_MISMATCH ({email_domain} does not match {company_name})"

    # 5. Deterministic Evidence Scoring
    local_tokens = set(re.split(r'[._+-]', email_local))
    has_recruiting_keyword = bool(local_tokens.intersection(RECRUITING_LOCAL_PARTS) or email_local in RECRUITING_LOCAL_PARTS)
    is_in_description = bool(job_description and email_clean in job_description.lower())
    
    score = 0.0
    evidence_desc = ""

    if is_in_description and has_recruiting_keyword:
        score = 1.00
        evidence_desc = f"Official job description explicitly provides recruiting email ({domain_match_reason})"
    elif is_in_description:
        score = 0.95
        evidence_desc = f"Official job description provides contact email ({domain_match_reason})"
    elif source_type == "official_careers_page":
        score = 0.95
        evidence_desc = f"Official careers page provides email ({domain_match_reason})"
    elif source_type == "application_page":
        score = 0.90
        evidence_desc = f"Official application page provides email ({domain_match_reason})"
    elif source_type == "verified_recruiter":
        score = 0.85
        evidence_desc = f"Verified recruiter contact ({domain_match_reason})"
    elif job_data.get("recruiter_email") == email_clean or job_data.get("application_email") == email_clean:
        score = 0.95 if has_recruiting_keyword else 0.85
        evidence_desc = f"Job source provided direct application email ({domain_match_reason})"
    elif has_recruiting_keyword:
        score = 0.75
        evidence_desc = f"Company domain + recruiting keyword match ({domain_match_reason})"
    else:
        score = 0.50
        evidence_desc = f"Company domain match only ({domain_match_reason})"

    # Classify based on strict thresholds
    if score >= 0.85:
        classification = RecipientClassification.VERIFIED
    elif score >= 0.50:
        classification = RecipientClassification.DOMAIN_MATCH_ONLY
    elif score > 0.0:
        classification = RecipientClassification.UNVERIFIED
    else:
        classification = RecipientClassification.NOT_FOUND

    return True, classification, score, evidence_desc

def validate_company_domain(
    email: str,
    company_name: str,
    company_url: Optional[str] = None,
    application_url: Optional[str] = None,
    source_url: Optional[str] = None
) -> Tuple[bool, str]:
    """Backward-compatible helper wrapping verify_email_for_job."""
    job_data = {
        "company": company_name,
        "company_url": company_url,
        "application_url": application_url,
        "source_url": source_url
    }
    is_valid, classification, score, reason = verify_email_for_job(email, job_data)
    return (is_valid and classification in [RecipientClassification.VERIFIED, RecipientClassification.DOMAIN_MATCH_ONLY]), reason

def extract_emails_from_text(text: Optional[str]) -> List[str]:
    """Finds all unique valid email addresses in a block of text."""
    if not text:
        return []
    matches = EMAIL_REGEX.findall(text)
    seen = set()
    cleaned = []
    for m in matches:
        m_clean = m.strip().rstrip(".,;:)")
        if is_valid_email_format(m_clean) and m_clean.lower() not in seen:
            seen.add(m_clean.lower())
            cleaned.append(m_clean)
    return cleaned

class EmailResolutionService:
    """
    Dynamic recruiter email resolution and verification pipeline.
    Resolves contacts strictly per job/company with multi-tier fallback, deterministic evidence scoring,
    and zero cross-job leaks.
    """

    def resolve_recruiter_contact(
        self,
        job_data: Dict[str, Any],
        recruiter_candidate: Optional[Any] = None
    ) -> EmailResolutionResult:
        """
        Executes priority-based email resolution for a specific job:
        1. Job Source direct fields (recruiter_email, application_email, contact_email)
        2. Job Description text regex extraction
        3. Official Application / Career page metadata
        4. Verified recruiter candidate object tied with evidence to this company
        Fallback: Returns NOT_FOUND with zero email and zero confidence.
        """
        company_name = job_data.get("company") or job_data.get("company_name") or ""
        company_url = job_data.get("company_url")
        application_url = job_data.get("application_url")
        source_url = job_data.get("source_url")
        job_description = job_data.get("description") or ""

        # Extract raw recruiter candidate info if provided
        raw_rec_name = None
        raw_rec_email = None
        raw_rec_evidence = None
        if recruiter_candidate:
            if isinstance(recruiter_candidate, dict):
                raw_rec_name = recruiter_candidate.get("name")
                raw_rec_email = recruiter_candidate.get("public_email") or recruiter_candidate.get("email")
                raw_rec_evidence = recruiter_candidate.get("source_evidence")
            else:
                raw_rec_name = getattr(recruiter_candidate, "name", None)
                raw_rec_email = getattr(recruiter_candidate, "public_email", None) or getattr(recruiter_candidate, "email", None)
                raw_rec_evidence = getattr(recruiter_candidate, "source_evidence", None)

        clean_rec_name, rec_status = sanitize_recruiter_name(raw_rec_name, company_name)

        # -------------------------------------------------------------
        # Priority 1: Job Source Data Fields
        # -------------------------------------------------------------
        source_candidates = [
            (job_data.get("recruiter_email"), "job_source"),
            (job_data.get("application_email"), "job_source"),
            (job_data.get("contact_email"), "job_source"),
            (job_data.get("email"), "job_source"),
        ]

        for cand_email, src_name in source_candidates:
            if cand_email and is_valid_email_format(cand_email):
                is_valid, classification, score, reason = verify_email_for_job(cand_email, job_data)
                if is_valid and classification in [RecipientClassification.VERIFIED, RecipientClassification.DOMAIN_MATCH_ONLY]:
                    return EmailResolutionResult(
                        email=cand_email.strip().lower(),
                        status=classification,
                        source=src_name,
                        source_url=source_url or application_url or company_url,
                        company=company_name,
                        confidence=score,
                        recruiter_name=clean_rec_name,
                        recruiter_status=rec_status,
                        validation_reason=f"Priority 1: {reason}",
                        send_allowed=(classification == RecipientClassification.VERIFIED)
                    )

        # -------------------------------------------------------------
        # Priority 2: Job Description Regex Extraction
        # -------------------------------------------------------------
        if job_description:
            desc_emails = extract_emails_from_text(job_description)
            if desc_emails:
                valid_candidates = []
                for em in desc_emails:
                    is_valid, classification, score, reason = verify_email_for_job(em, job_data)
                    if is_valid and classification != RecipientClassification.REJECTED:
                        valid_candidates.append((score, classification, em, reason))

                if valid_candidates:
                    valid_candidates.sort(key=lambda x: x[0], reverse=True)
                    best_score, best_class, best_email, best_reason = valid_candidates[0]
                    return EmailResolutionResult(
                        email=best_email.strip().lower(),
                        status=best_class,
                        source="job_description",
                        source_url=source_url or application_url,
                        company=company_name,
                        confidence=best_score,
                        recruiter_name=clean_rec_name,
                        recruiter_status=rec_status,
                        validation_reason=f"Priority 2: {best_reason}",
                        send_allowed=(best_class == RecipientClassification.VERIFIED)
                    )

        # -------------------------------------------------------------
        # Priority 3: Official Application / Career Page Metadata
        # -------------------------------------------------------------
        if application_url and "@" in application_url:
            app_emails = extract_emails_from_text(application_url)
            for em in app_emails:
                is_valid, classification, score, reason = verify_email_for_job(em, job_data, source_type="application_page")
                if is_valid and classification in [RecipientClassification.VERIFIED, RecipientClassification.DOMAIN_MATCH_ONLY]:
                    return EmailResolutionResult(
                        email=em.strip().lower(),
                        status=classification,
                        source="application_page",
                        source_url=application_url,
                        company=company_name,
                        confidence=score,
                        recruiter_name=clean_rec_name,
                        recruiter_status=rec_status,
                        validation_reason=f"Priority 3: {reason}",
                        send_allowed=(classification == RecipientClassification.VERIFIED)
                    )

        # -------------------------------------------------------------
        # Priority 4: Verified Recruiter Contact from Discovery
        # -------------------------------------------------------------
        if raw_rec_email and is_valid_email_format(raw_rec_email):
            is_valid, classification, score, reason = verify_email_for_job(raw_rec_email, job_data, source_type="verified_recruiter")
            if is_valid and classification != RecipientClassification.REJECTED:
                return EmailResolutionResult(
                    email=raw_rec_email.strip().lower(),
                    status=classification,
                    source="verified_recruiter",
                    source_url=source_url or company_url,
                    company=company_name,
                    confidence=score,
                    recruiter_name=clean_rec_name,
                    recruiter_status="VERIFIED" if clean_rec_name else "NOT_FOUND",
                    validation_reason=f"Priority 4: {reason}",
                    send_allowed=(classification == RecipientClassification.VERIFIED)
                )

        # -------------------------------------------------------------
        # Fallback: No Email Found (Strictly Never Invent / Leak Emails)
        # -------------------------------------------------------------
        return EmailResolutionResult(
            email=None,
            status=RecipientClassification.NOT_FOUND,
            source=None,
            source_url=None,
            company=company_name,
            confidence=0.0,
            recruiter_name=clean_rec_name,
            recruiter_status=rec_status,
            validation_reason="No verified employer or recruiter email discovered",
            send_allowed=False
        )

def validate_recipient_before_send(
    job_data: Dict[str, Any],
    recipient_email: Optional[str],
    email_status: Optional[str] = None,
    email_source: Optional[str] = None,
    candidate_id: Optional[str] = None,
    application_id: Optional[str] = None
) -> Tuple[bool, str, str]:
    """
    Final Centralized Pre-Send Safety Gate.
    Every email dispatch path MUST call this function.
    
    Returns:
    (send_allowed: bool, safety_status: str, block_reason: str)
    """
    if not job_data:
        return False, RecipientClassification.BLOCKED_INVALID_RECIPIENT, "Job record missing"

    company = job_data.get("company", "").strip()
    if not company:
        return False, RecipientClassification.BLOCKED_INVALID_RECIPIENT, "Company name missing"

    if not recipient_email or not is_valid_email_format(recipient_email):
        return False, RecipientClassification.BLOCKED_INVALID_RECIPIENT, "Invalid or missing recipient email syntax"

    target_email = recipient_email.strip().lower()

    # Block hardcoded leak
    if target_email == "talent@techcorp.com" and "techcorp" not in company.lower():
        return False, RecipientClassification.BLOCKED_INVALID_RECIPIENT, f"Blocked hardcoded talent@techcorp.com on {company}"

    # Verify domain & classification
    is_valid, classification, score, reason = verify_email_for_job(target_email, job_data)
    
    if not is_valid or classification != RecipientClassification.VERIFIED:
        return False, RecipientClassification.BLOCKED_INVALID_RECIPIENT, f"Recipient email status '{classification}' is not VERIFIED ({reason})"

    if score < 0.85:
        return False, RecipientClassification.BLOCKED_INVALID_RECIPIENT, f"Evidence score {score:.2f} is below safety threshold 0.85"

    return True, "READY_TO_SEND", f"Verified recipient for {company} (Score: {score:.2f})"

email_resolution_service = EmailResolutionService()
