import logging
import json
import uuid
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
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
    db: AsyncSession
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

    # Execute LangGraph workflow
    final_state = await job_application_graph.ainvoke(initial_state)
    end_time = datetime.utcnow()
    latency = (end_time - start_time).total_seconds() * 1000

    # Persist Jobs, Matches, Recruiters, and Applications to Database
    async with AsyncSessionLocal() as session:
        run_record = await session.get(AgentRun, run_id)
        if run_record:
            run_record.status = "COMPLETED"
            run_record.current_step = final_state.get("current_step", "COMPLETED")
            run_record.latency_ms = latency
            run_record.completed_at = end_time
            run_record.summary = {
                "discovered": len(final_state.get("discovered_jobs", [])),
                "matched": len(final_state.get("matched_jobs", [])),
                "ranked": len(final_state.get("ranked_jobs", [])),
                "recruiter_found": bool(final_state.get("recruiter")),
                "approval_pending": True
            }

        # Save all event logs
        for ev in final_state.get("events", []):
            session.add(AgentEvent(
                run_id=run_id,
                agent_name=ev.get("agent_name", "Supervisor"),
                step=ev.get("step", "general"),
                event_type="INFO",
                message=ev.get("message", ""),
                payload=ev.get("payload", {})
            ))

        # Save jobs & matches
        candidate_id = candidate_data.get("id")
        if not candidate_id:
            res = await session.execute(select(CandidateProfile).limit(1))
            cand = res.scalars().first()
            candidate_id = cand.id if cand else "default_candidate"

        for j in final_state.get("ranked_jobs", []):
            canonical_id = j.get("canonical_job_id") or str(uuid.uuid4())
            # Check existing job
            res_j = await session.execute(select(Job).filter_by(canonical_job_id=canonical_id))
            existing_job = res_j.scalars().first()
            if not existing_job:
                job_entity = Job(
                    canonical_job_id=canonical_id,
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
                await session.flush()
            else:
                job_entity = existing_job

            # Save Match
            match_data = j.get("match", {})
            res_m = await session.execute(select(JobMatch).filter_by(job_id=job_entity.id, candidate_id=candidate_id))
            if not res_m.scalars().first() and match_data:
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

        # Save Selected Application and Recruiter if available
        selected_job_data = final_state.get("selected_job")
        if selected_job_data:
            res_sel = await session.execute(select(Job).filter_by(company=selected_job_data.get("company"), title=selected_job_data.get("title")))
            sel_job = res_sel.scalars().first()
            if sel_job:
                # Recruiter
                recruiter_entity = None
                recruiter_data = final_state.get("recruiter")
                if recruiter_data:
                    res_rec = await session.execute(select(Recruiter).filter_by(company_name=recruiter_data.get("company_name")))
                    recruiter_entity = res_rec.scalars().first()
                    if not recruiter_entity:
                        recruiter_entity = Recruiter(
                            name=recruiter_data.get("name", "Recruiter"),
                            title=recruiter_data.get("title", "Recruiter"),
                            company_name=recruiter_data.get("company_name", sel_job.company),
                            public_email=recruiter_data.get("public_email"),
                            linkedin_url=recruiter_data.get("linkedin_url"),
                            source_evidence=recruiter_data.get("source_evidence")
                        )
                        session.add(recruiter_entity)
                        await session.flush()

                # Application record
                idempotency_key = f"{candidate_id}_{sel_job.id}_apply"
                res_app = await session.execute(select(Application).filter_by(idempotency_key=idempotency_key))
                app_entity = res_app.scalars().first()
                if not app_entity:
                    app_entity = Application(
                        candidate_id=candidate_id,
                        job_id=sel_job.id,
                        status=ApplicationStatus.REVIEW_REQUIRED,
                        idempotency_key=idempotency_key,
                        notes=f"Prepared application package for {sel_job.company}"
                    )
                    session.add(app_entity)
                    await session.flush()

                    # Save questions
                    pkg = final_state.get("application_package", {})
                    for q in pkg.get("questions", []):
                        session.add(ApplicationQuestion(
                            application_id=app_entity.id,
                            question=q.get("question", ""),
                            answer=q.get("answer", ""),
                            is_sensitive=q.get("is_sensitive", False),
                            needs_user_input=q.get("needs_user_input", False),
                            status=q.get("status", "AUTO_GENERATED")
                        ))

                    # Save Outreach drafts
                    outreach_data = final_state.get("outreach", {})
                    if outreach_data.get("email"):
                        em = outreach_data["email"]
                        session.add(OutreachMessage(
                            application_id=app_entity.id,
                            recruiter_id=recruiter_entity.id if recruiter_entity else None,
                            channel="EMAIL",
                            subject=em.get("subject"),
                            body=em.get("body", ""),
                            recipient_email=em.get("recipient_email"),
                            recipient_name=em.get("recipient_name"),
                            status="DRAFT"
                        ))
                    if outreach_data.get("linkedin"):
                        li = outreach_data["linkedin"]
                        session.add(OutreachMessage(
                            application_id=app_entity.id,
                            recruiter_id=recruiter_entity.id if recruiter_entity else None,
                            channel="LINKEDIN",
                            subject=li.get("subject"),
                            body=li.get("body", ""),
                            recipient_name=li.get("recipient_name"),
                            status="MANUAL_REQUIRED"
                        ))

                    # Save Approval Request
                    session.add(ApprovalRequest(
                        application_id=app_entity.id,
                        status=ApprovalStatus.PENDING,
                        action_type="SUBMIT_AND_OUTREACH",
                        package_data=pkg
                    ))

        await session.commit()
    return final_state

@router.post("/run")
async def run_agent(
    request: AgentPromptRequest,
    db: AsyncSession = Depends(get_db)
):
    """Trigger the multi-agent job search, matching, and application preparation workflow."""
    # Get candidate profile
    cand_res = await db.execute(select(CandidateProfile).limit(1))
    cand = cand_res.scalars().first()
    cand_dict = {c.name: getattr(cand, c.name) for c in cand.__table__.columns} if cand else {}

    run_id = str(uuid.uuid4())
    run_record = AgentRun(
        id=run_id,
        user_prompt=request.prompt,
        status="RUNNING",
        current_step="parse_prompt"
    )
    db.add(run_record)
    await db.commit()

    # Run workflow
    final_state = await execute_agent_workflow(run_id, request.prompt, cand_dict, db)
    return {
        "run_id": run_id,
        "status": "COMPLETED",
        "jobs_found": len(final_state.get("discovered_jobs", [])),
        "matches_count": len(final_state.get("matched_jobs", [])),
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
    # Fetch candidate
    cand_res = await db.execute(select(CandidateProfile).limit(1))
    cand = cand_res.scalars().first()
    cand_dict = {c.name: getattr(cand, c.name) for c in cand.__table__.columns} if cand else {}

    run_id = str(uuid.uuid4())
    run_record = AgentRun(
        id=run_id,
        user_prompt=request.prompt,
        status="RUNNING",
        current_step="START"
    )
    db.add(run_record)
    await db.commit()

    async def event_generator():
        yield f"data: {json.dumps({'event': 'start', 'run_id': run_id, 'message': 'Agent initialized. Analyzing your search prompt...'})}\n\n"
        await asyncio.sleep(0.3)

        # Step 1: Parse Prompt
        yield f"data: {json.dumps({'event': 'step', 'step': 'parse_prompt', 'agent': 'Supervisor', 'message': 'Parsing target roles, skills, and remote requirements...'})}\n\n"
        await asyncio.sleep(0.4)

        # Step 2: Search jobs
        yield f"data: {json.dumps({'event': 'step', 'step': 'search_jobs', 'agent': 'JobResearchAgent', 'message': 'Executing multi-query search across verified company portals and career APIs...'})}\n\n"
        await asyncio.sleep(0.6)

        # Step 3: Match jobs
        yield f"data: {json.dumps({'event': 'step', 'step': 'match_jobs', 'agent': 'MatchingAgent', 'message': 'Evaluating deterministic skills (30%), experience (20%), and role alignment (20%)...'})}\n\n"
        await asyncio.sleep(0.5)

        # Step 4: Recruiter discovery
        yield f"data: {json.dumps({'event': 'step', 'step': 'discover_recruiters', 'agent': 'RecruiterAgent', 'message': 'Discovering public talent acquisition partners and verified LinkedIn directories...'})}\n\n"
        await asyncio.sleep(0.4)

        # Step 5: Application Package & Outreach
        yield f"data: {json.dumps({'event': 'step', 'step': 'prepare_application', 'agent': 'ApplicationAgent', 'message': 'Generating factual resume tailoring, cover letter, and personalized recruiter outreach...'})}\n\n"
        
        # Execute workflow and persist
        final_state = await execute_agent_workflow(run_id, request.prompt, cand_dict, db)

        yield f"data: {json.dumps({
            'event': 'complete',
            'run_id': run_id,
            'summary': {
                'jobs_found': len(final_state.get('discovered_jobs', [])),
                'strong_matches': len([j for j in final_state.get('ranked_jobs', []) if j.get('match', {}).get('overall_score', 0) >= 80]),
                'selected_job': final_state.get('selected_job'),
                'recruiter': final_state.get('recruiter'),
                'approval_required': True
            }
        })}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/runs/{run_id}")
async def get_agent_run(run_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch run status and full event traces for observability."""
    res = await db.execute(select(AgentRun).filter_by(id=run_id))
    run = res.scalars().first()
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found")
    
    events_res = await db.execute(select(AgentEvent).filter_by(run_id=run_id).order_by(AgentEvent.timestamp.asc()))
    events = events_res.scalars().all()

    return {
        "id": run.id,
        "user_prompt": run.user_prompt,
        "status": run.status,
        "current_step": run.current_step,
        "summary": run.summary,
        "latency_ms": run.latency_ms,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "events": [
            {
                "id": ev.id,
                "agent_name": ev.agent_name,
                "step": ev.step,
                "message": ev.message,
                "payload": ev.payload,
                "timestamp": ev.timestamp
            }
            for ev in events
        ]
    }
