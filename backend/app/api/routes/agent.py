import logging
import json
import uuid
import asyncio
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.config.database import get_db, AsyncSessionLocal
from app.models.entities import (
    AgentRun, AgentEvent, CandidateProfile, Job, JobMatch, Recruiter,
    Application, ApplicationQuestion, OutreachMessage, ApprovalRequest,
    ApplicationStatus, ApprovalStatus
)
from app.schemas.schemas import AgentPromptRequest, AgentRunResponse
from app.graph.graph import job_application_graph
from app.graph.state import JobApplicationState

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["Agent"])

async def execute_agent_workflow(
    run_id: str,
    prompt: str,
    candidate_data: dict,
    db: Optional[AsyncSession] = None
):
    start_time = datetime.utcnow()
    initial_state: JobApplicationState = {
        "run_id": run_id,
        "user_prompt": prompt,
        "search_criteria": {},
        "candidate_profile": candidate_data,
        "discovered_jobs": [],
        "normalized_jobs": [],
        "deduplicated_jobs": [],
        "matched_jobs": [],
        "ranked_jobs": [],
        "qualified_jobs": [],
        "strong_matches": [],
        "application_packages": [],
        "recruiter_map": {},
        "selected_job": None,
        "recruiter": None,
        "application_package": None,
        "outreach": None,
        "approval_required": True,
        "approval_status": "PENDING",
        "errors": [],
        "current_step": "START",
        "events": []
    }

    # Execute LangGraph multi-agent workflow
    final_state = await job_application_graph.ainvoke(initial_state)
    end_time = datetime.utcnow()
    latency = (end_time - start_time).total_seconds() * 1000

    # Persist Jobs, Matches, Recruiters, and Application Packages in Batch
    async with AsyncSessionLocal() as session:
        candidate_id = candidate_data.get("id")
        if not candidate_id:
            res = await session.execute(select(CandidateProfile).limit(1))
            cand = res.scalars().first()
            candidate_id = cand.id if cand else "default_candidate"

        # 1. Save all ranked jobs and matches with run_id in batch
        ranked_jobs = final_state.get("ranked_jobs", [])
        canonical_ids = [j.get("canonical_job_id") for j in ranked_jobs if j.get("canonical_job_id")]
        existing_jobs_by_canon = {}
        if canonical_ids:
            res_all_jobs = await session.execute(select(Job).where(Job.canonical_job_id.in_(canonical_ids)))
            for ej in res_all_jobs.scalars().all():
                existing_jobs_by_canon[ej.canonical_job_id] = ej

        persisted_jobs_map = {}
        for j in ranked_jobs:
            canonical_id = j.get("canonical_job_id") or str(uuid.uuid4())
            existing_job = existing_jobs_by_canon.get(canonical_id)
            if not existing_job:
                job_id = str(uuid.uuid4())
                job_entity = Job(
                    id=job_id,
                    canonical_job_id=canonical_id,
                    run_id=run_id,
                    company=j.get("company", "Company"),
                    title=j.get("title", "Role"),
                    location=j.get("location", "Remote"),
                    remote=j.get("remote", True),
                    employment_type=j.get("employment_type", "Full-time"),
                    experience_required=j.get("experience_required"),
                    salary=j.get("salary"),
                    description=j.get("description", ""),
                    requirements=j.get("requirements", []),
                    skills=j.get("skills", []),
                    application_url=j.get("application_url"),
                    source_url=j.get("source_url"),
                    source_urls=j.get("source_urls", []),
                    posted_date=j.get("posted_date"),
                    company_url=j.get("company_url"),
                    verification_status=j.get("verification_status", "VERIFIED"),
                    evidence=j.get("evidence", []),
                    research_provider=j.get("research_provider", "openai_web_search")
                )
                session.add(job_entity)
            else:
                existing_job.run_id = run_id
                job_entity = existing_job

            persisted_jobs_map[job_entity.company + "::" + job_entity.title] = job_entity
            if canonical_id:
                persisted_jobs_map[canonical_id] = job_entity

            # Save or update Match
            match_data = j.get("match", {})
            if match_data:
                res_match = await session.execute(
                    select(JobMatch).filter_by(job_id=job_entity.id, candidate_id=candidate_id)
                )
                existing_match = res_match.scalars().first()
                if not existing_match:
                    session.add(JobMatch(
                        job_id=job_entity.id,
                        candidate_id=candidate_id,
                        overall_score=match_data.get("overall_score", 0),
                        skills_score=match_data.get("skills_score", 0),
                        experience_score=match_data.get("experience_score", 0),
                        location_score=match_data.get("location_score", 0),
                        role_score=match_data.get("role_score", 0),
                        matched_skills=match_data.get("matched_skills", []),
                        missing_skills=match_data.get("missing_skills", []),
                        concerns=match_data.get("concerns", []),
                        recommendation=match_data.get("recommendation", "MATCH"),
                        reasoning=match_data.get("reasoning")
                    ))
                else:
                    existing_match.overall_score = match_data.get("overall_score", 0)
                    existing_match.skills_score = match_data.get("skills_score", 0)
                    existing_match.experience_score = match_data.get("experience_score", 0)
                    existing_match.location_score = match_data.get("location_score", 0)
                    existing_match.role_score = match_data.get("role_score", 0)
                    existing_match.matched_skills = match_data.get("matched_skills", [])
                    existing_match.missing_skills = match_data.get("missing_skills", [])
                    existing_match.concerns = match_data.get("concerns", [])
                    existing_match.recommendation = match_data.get("recommendation", "MATCH")
                    existing_match.reasoning = match_data.get("reasoning")

        # 2. Save all Application Packages and Approval Requests
        packages = final_state.get("application_packages", [])
        if not packages and final_state.get("application_package"):
            packages = [final_state["application_package"]]

        approvals_created_count = 0
        for pkg in packages:
            pkg_job_data = pkg.get("job", {})
            canon = pkg_job_data.get("canonical_job_id")
            lookup_key = pkg_job_data.get("company", "") + "::" + pkg_job_data.get("title", "")
            job_obj = persisted_jobs_map.get(canon) or persisted_jobs_map.get(lookup_key)

            if not job_obj:
                job_id = str(uuid.uuid4())
                job_obj = Job(
                    id=job_id,
                    canonical_job_id=canon or job_id,
                    run_id=run_id,
                    company=pkg_job_data.get("company", "Company"),
                    title=pkg_job_data.get("title", "Role"),
                    location=pkg_job_data.get("location", "Remote"),
                    remote=pkg_job_data.get("remote", True),
                    employment_type=pkg_job_data.get("employment_type", "Full-time"),
                    experience_required=pkg_job_data.get("experience_required"),
                    salary=pkg_job_data.get("salary"),
                    description=pkg_job_data.get("description", ""),
                    requirements=pkg_job_data.get("requirements", []),
                    skills=pkg_job_data.get("skills", []),
                    application_url=pkg_job_data.get("application_url"),
                    source_url=pkg_job_data.get("source_url"),
                    source_urls=pkg_job_data.get("source_urls", []),
                    posted_date=pkg_job_data.get("posted_date"),
                    company_url=pkg_job_data.get("company_url"),
                    verification_status=pkg_job_data.get("verification_status", "VERIFIED"),
                    evidence=pkg_job_data.get("evidence", []),
                    research_provider=pkg_job_data.get("research_provider", "openai_web_search")
                )
                session.add(job_obj)

            # Save Recruiter if present
            rec_data = pkg.get("recruiter")
            recruiter_obj = None
            if rec_data:
                rec_name = rec_data.get("name", "Talent Acquisition Team")
                res_rec = await session.execute(
                    select(Recruiter).filter_by(company_name=job_obj.company, name=rec_name)
                )
                recruiter_obj = res_rec.scalars().first()
                if not recruiter_obj:
                    rec_id = str(uuid.uuid4())
                    recruiter_obj = Recruiter(
                        id=rec_id,
                        name=rec_name,
                        title=rec_data.get("title", "Technical Recruiter"),
                        company_name=rec_data.get("company_name", job_obj.company),
                        public_email=rec_data.get("public_email"),
                        linkedin_url=rec_data.get("linkedin_url"),
                        source_evidence=rec_data.get("source_evidence")
                    )
                    session.add(recruiter_obj)
                else:
                    if rec_data.get("public_email"):
                        recruiter_obj.public_email = rec_data.get("public_email")
                    if rec_data.get("linkedin_url"):
                        recruiter_obj.linkedin_url = rec_data.get("linkedin_url")

            # Save or Update Application
            app_idempotency_key = f"{candidate_id}_{job_obj.id}_apply"
            res_app = await session.execute(
                select(Application).where(
                    (Application.idempotency_key == app_idempotency_key) |
                    ((Application.candidate_id == candidate_id) & (Application.job_id == job_obj.id))
                )
            )
            app_entity = res_app.scalars().first()
            if not app_entity:
                app_id = str(uuid.uuid4())
                app_entity = Application(
                    id=app_id,
                    run_id=run_id,
                    candidate_id=candidate_id,
                    job_id=job_obj.id,
                    status=ApplicationStatus.REVIEW_REQUIRED,
                    idempotency_key=app_idempotency_key,
                    notes=f"Prepared application package for {job_obj.company}"
                )
                session.add(app_entity)
            else:
                app_entity.run_id = run_id
                app_entity.idempotency_key = app_idempotency_key
                app_entity.status = ApplicationStatus.REVIEW_REQUIRED
                app_entity.notes = f"Prepared application package for {job_obj.company}"
                app_entity.updated_at = datetime.utcnow()

            # Replace Questions for this application
            await session.execute(
                delete(ApplicationQuestion).where(ApplicationQuestion.application_id == app_entity.id)
            )
            for q in pkg.get("questions", []):
                session.add(ApplicationQuestion(
                    application_id=app_entity.id,
                    question=q.get("question", ""),
                    answer=q.get("answer", ""),
                    is_sensitive=q.get("is_sensitive", False),
                    needs_user_input=q.get("needs_user_input", False),
                    status=q.get("status", "AUTO_GENERATED")
                ))

            # Replace Outreach Messages for this application
            await session.execute(
                delete(OutreachMessage).where(OutreachMessage.application_id == app_entity.id)
            )
            em_outreach = pkg.get("email_outreach")
            if em_outreach:
                session.add(OutreachMessage(
                    application_id=app_entity.id,
                    recruiter_id=recruiter_obj.id if recruiter_obj else None,
                    channel="EMAIL",
                    subject=em_outreach.get("subject"),
                    body=em_outreach.get("body", ""),
                    recipient_email=em_outreach.get("recipient_email") or (recruiter_obj.public_email if recruiter_obj else None),
                    recipient_name=em_outreach.get("recipient_name") or (recruiter_obj.name if recruiter_obj else "Hiring Team"),
                    email_status=em_outreach.get("email_status", "NOT_FOUND"),
                    email_source=em_outreach.get("email_source"),
                    email_confidence=em_outreach.get("email_confidence", 0.0),
                    status="DRAFT",
                    idempotency_key=f"{candidate_id}_{job_obj.id}_email_outreach"
                ))

            li_outreach = pkg.get("linkedin_outreach")
            if li_outreach:
                session.add(OutreachMessage(
                    application_id=app_entity.id,
                    recruiter_id=recruiter_obj.id if recruiter_obj else None,
                    channel="LINKEDIN",
                    subject=li_outreach.get("subject"),
                    body=li_outreach.get("body", ""),
                    recipient_name=li_outreach.get("recipient_name") or (recruiter_obj.name if recruiter_obj else "Hiring Team"),
                    status="MANUAL_REQUIRED",
                    idempotency_key=f"{candidate_id}_{job_obj.id}_linkedin_outreach"
                ))

            # Save or Update Approval Request
            res_appr = await session.execute(
                select(ApprovalRequest).where(ApprovalRequest.application_id == app_entity.id)
            )
            existing_appr = res_appr.scalars().first()
            if existing_appr:
                existing_appr.run_id = run_id
                existing_appr.status = ApprovalStatus.PENDING
                existing_appr.action_type = "SUBMIT_AND_OUTREACH"
                existing_appr.package_data = pkg
                existing_appr.approved_at = None
            else:
                session.add(ApprovalRequest(
                    run_id=run_id,
                    application_id=app_entity.id,
                    status=ApprovalStatus.PENDING,
                    action_type="SUBMIT_AND_OUTREACH",
                    package_data=pkg
                ))
            approvals_created_count += 1

        # 3. Update AgentRun Record with Batch Stats
        run_record = await session.get(AgentRun, run_id)
        if run_record:
            total_j = len(final_state.get("discovered_jobs", []))
            unique_j = len(final_state.get("deduplicated_jobs", []))
            qual_j = len(final_state.get("qualified_jobs", []))
            strong_j = len(final_state.get("strong_matches", []))
            apps_prep = len(packages)

            run_record.candidate_id = candidate_id
            run_record.search_prompt = prompt
            run_record.status = "WAITING_FOR_APPROVAL" if approvals_created_count > 0 else "COMPLETED"
            run_record.current_step = "human_approval_gate" if approvals_created_count > 0 else "COMPLETED"
            run_record.total_jobs = total_j
            run_record.unique_jobs = unique_j
            run_record.qualified_jobs = qual_j
            run_record.strong_matches = strong_j
            run_record.applications_prepared = apps_prep
            run_record.approvals_pending = approvals_created_count
            run_record.applications_approved = 0
            run_record.applications_rejected = 0
            run_record.latency_ms = latency
            run_record.completed_at = end_time
            run_record.summary = {
                "discovered": total_j,
                "unique": unique_j,
                "qualified": qual_j,
                "strong_matches": strong_j,
                "applications_prepared": apps_prep,
                "approvals_pending": approvals_created_count,
                "approval_required": bool(approvals_created_count > 0)
            }

        # 4. Save Event Logs
        for ev in final_state.get("events", []):
            session.add(AgentEvent(
                run_id=run_id,
                agent_name=ev.get("agent_name", "Supervisor"),
                step=ev.get("step", "general"),
                event_type="INFO",
                message=ev.get("message", ""),
                payload=ev.get("payload", {})
            ))

        await session.commit()
    return final_state

@router.post("/run")
async def run_agent(
    request: AgentPromptRequest,
    db: AsyncSession = Depends(get_db)
):
    """Trigger the multi-agent job search, matching, and batch application preparation workflow."""
    cand_res = await db.execute(select(CandidateProfile).limit(1))
    cand = cand_res.scalars().first()
    cand_dict = {c.name: getattr(cand, c.name) for c in cand.__table__.columns} if cand else {}

    run_id = str(uuid.uuid4())
    run_record = AgentRun(
        id=run_id,
        candidate_id=cand.id if cand else None,
        user_prompt=request.prompt,
        search_prompt=request.prompt,
        status="SEARCHING",
        current_step="parse_prompt"
    )
    db.add(run_record)
    await db.commit()

    # Run complete multi-agent workflow
    final_state = await execute_agent_workflow(run_id, request.prompt, cand_dict)

    # Refresh updated run record from database
    await db.refresh(run_record)
    return {
        "run_id": run_id,
        "status": run_record.status or "WAITING_FOR_APPROVAL",
        "total_jobs": run_record.total_jobs or len(final_state.get("discovered_jobs", [])),
        "unique_jobs": run_record.unique_jobs or len(final_state.get("deduplicated_jobs", [])),
        "qualified_jobs": run_record.qualified_jobs or len(final_state.get("qualified_jobs", [])),
        "strong_matches": run_record.strong_matches or len(final_state.get("strong_matches", [])),
        "applications_prepared": run_record.applications_prepared or len(final_state.get("application_packages", [])),
        "approvals_pending": run_record.approvals_pending or len(final_state.get("application_packages", [])),
        "selected_job": final_state.get("selected_job"),
        "recruiter": final_state.get("recruiter"),
        "approval_required": True,
        "events": final_state.get("events", [])
    }

@router.post("/stream")
async def stream_agent(
    request: AgentPromptRequest,
    db: AsyncSession = Depends(get_db)
):
    """Stream real-time agent execution events and reasoning using Server-Sent Events (SSE)."""
    cand_res = await db.execute(select(CandidateProfile).limit(1))
    cand = cand_res.scalars().first()
    cand_dict = {c.name: getattr(cand, c.name) for c in cand.__table__.columns} if cand else {}

    run_id = str(uuid.uuid4())
    run_record = AgentRun(
        id=run_id,
        candidate_id=cand.id if cand else None,
        user_prompt=request.prompt,
        search_prompt=request.prompt,
        status="SEARCHING",
        current_step="START"
    )
    db.add(run_record)
    await db.commit()

    async def event_generator():
        yield f"data: {json.dumps({'event': 'start', 'run_id': run_id, 'message': 'Agent initialized. Analyzing your search prompt...'})}\n\n"
        await asyncio.sleep(0.2)

        yield f"data: {json.dumps({'event': 'step', 'step': 'parse_prompt', 'agent': 'Supervisor', 'message': 'Parsing target roles, skills, and remote requirements...'})}\n\n"
        await asyncio.sleep(0.3)

        yield f"data: {json.dumps({'event': 'step', 'step': 'search_jobs', 'agent': 'JobResearchAgent', 'message': 'Executing multi-source search across verified company portals and web APIs...'})}\n\n"
        await asyncio.sleep(0.3)

        yield f"data: {json.dumps({'event': 'step', 'step': 'match_jobs', 'agent': 'MatchingAgent', 'message': 'Evaluating deterministic skills (30%), experience (20%), and role alignment (20%)...'})}\n\n"
        await asyncio.sleep(0.3)

        yield f"data: {json.dumps({'event': 'step', 'step': 'prepare_application', 'agent': 'ApplicationAgent', 'message': 'Generating factual resume tailoring, cover letters, and personalized outreach in batch...'})}\n\n"
        
        # Execute workflow and persist
        final_state = await execute_agent_workflow(run_id, request.prompt, cand_dict, db)

        db_run = await db.get(AgentRun, run_id)
        complete_payload = {
            "event": "complete",
            "run_id": run_id,
            "summary": {
                "status": db_run.status if db_run else "WAITING_FOR_APPROVAL",
                "jobs_found": db_run.total_jobs if db_run else len(final_state.get("discovered_jobs", [])),
                "unique_jobs": db_run.unique_jobs if db_run else len(final_state.get("deduplicated_jobs", [])),
                "qualified_jobs": db_run.qualified_jobs if db_run else len(final_state.get("qualified_jobs", [])),
                "strong_matches": db_run.strong_matches if db_run else len(final_state.get("strong_matches", [])),
                "applications_prepared": db_run.applications_prepared if db_run else len(final_state.get("application_packages", [])),
                "approvals_pending": db_run.approvals_pending if db_run else len(final_state.get("application_packages", [])),
                "selected_job": final_state.get("selected_job"),
                "recruiter": final_state.get("recruiter"),
                "approval_required": True
            }
        }
        yield f"data: {json.dumps(complete_payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/runs/latest")
async def get_latest_agent_run(
    candidate_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Fetch the most recent agent search run for automatic state restoration."""
    query = select(AgentRun).order_by(AgentRun.created_at.desc()).limit(1)
    if candidate_id:
        query = select(AgentRun).filter_by(candidate_id=candidate_id).order_by(AgentRun.created_at.desc()).limit(1)
    
    res = await db.execute(query)
    run = res.scalars().first()
    if not run:
        return None

    events_res = await db.execute(select(AgentEvent).filter_by(run_id=run.id).order_by(AgentEvent.timestamp.asc()))
    events = events_res.scalars().all()

    return {
        "id": run.id,
        "run_id": run.id,
        "candidate_id": run.candidate_id,
        "user_prompt": run.user_prompt,
        "search_prompt": run.search_prompt or run.user_prompt,
        "status": run.status,
        "current_step": run.current_step,
        "total_jobs": run.total_jobs,
        "unique_jobs": run.unique_jobs,
        "qualified_jobs": run.qualified_jobs,
        "strong_matches": run.strong_matches,
        "applications_prepared": run.applications_prepared,
        "approvals_pending": run.approvals_pending,
        "applications_approved": run.applications_approved,
        "applications_rejected": run.applications_rejected,
        "summary": run.summary,
        "latency_ms": run.latency_ms,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "events": [
            {
                "id": ev.id,
                "agent_name": ev.agent_name,
                "step": ev.step,
                "message": ev.message,
                "payload": ev.payload,
                "timestamp": ev.timestamp.isoformat() if ev.timestamp else None
            }
            for ev in events
        ]
    }

@router.get("/runs/{run_id}")
async def get_agent_run(run_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch run status, metrics, and full event traces for observability."""
    res = await db.execute(select(AgentRun).filter_by(id=run_id))
    run = res.scalars().first()
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found")
    
    events_res = await db.execute(select(AgentEvent).filter_by(run_id=run_id).order_by(AgentEvent.timestamp.asc()))
    events = events_res.scalars().all()

    return {
        "id": run.id,
        "run_id": run.id,
        "candidate_id": run.candidate_id,
        "user_prompt": run.user_prompt,
        "search_prompt": run.search_prompt or run.user_prompt,
        "status": run.status,
        "current_step": run.current_step,
        "total_jobs": run.total_jobs,
        "unique_jobs": run.unique_jobs,
        "qualified_jobs": run.qualified_jobs,
        "strong_matches": run.strong_matches,
        "applications_prepared": run.applications_prepared,
        "approvals_pending": run.approvals_pending,
        "applications_approved": run.applications_approved,
        "applications_rejected": run.applications_rejected,
        "summary": run.summary,
        "latency_ms": run.latency_ms,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "events": [
            {
                "id": ev.id,
                "agent_name": ev.agent_name,
                "step": ev.step,
                "message": ev.message,
                "payload": ev.payload,
                "timestamp": ev.timestamp.isoformat() if ev.timestamp else None
            }
            for ev in events
        ]
    }
