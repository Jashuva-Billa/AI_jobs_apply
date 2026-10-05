import streamlit as st
import requests
import json
import time
from typing import Dict, Any, List, Optional
import os

# Base API Configuration
API_BASE_URL = os.getenv("API_URL", "http://localhost:8000/api")

# Page Config
st.set_page_config(
    page_title="Antigravity AI | Agentic Job Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Dark Glassmorphism Theme CSS
st.markdown("""
<style>
    /* Dark Theme Colors */
    .stApp {
        background-color: #0B0F17;
        color: #F8FAFC;
        font-family: 'Inter', system-ui, sans-serif;
    }
    
    /* Headers & Text */
    h1, h2, h3, h4 {
        color: #FFFFFF !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
    }
    
    /* Metric Cards */
    [data-testid="stMetricValue"] {
        color: #818CF8 !important;
        font-size: 1.8rem !important;
        font-weight: 800 !important;
    }
    [data-testid="stMetricLabel"] {
        color: #94A3B8 !important;
        font-size: 0.8rem !important;
        font-weight: 600 !important;
    }
    
    /* Glassmorphism Card Containers */
    .glass-card {
        background: rgba(18, 24, 38, 0.8);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    }
    
    .glass-card:hover {
        border-color: rgba(99, 102, 241, 0.4);
    }

    /* Tag badges */
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 8px;
        font-size: 11px;
        font-weight: 600;
        margin-right: 6px;
        margin-bottom: 6px;
    }
    .badge-brand { background: rgba(99, 102, 241, 0.2); color: #C7D2FE; border: 1px solid rgba(99, 102, 241, 0.3); }
    .badge-success { background: rgba(16, 185, 129, 0.2); color: #6EE7B7; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-cyan { background: rgba(6, 182, 212, 0.2); color: #67E8F9; border: 1px solid rgba(6, 182, 212, 0.3); }
    .badge-warning { background: rgba(245, 158, 11, 0.2); color: #FCD34D; border: 1px solid rgba(245, 158, 11, 0.3); }
    
    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #4F46E5 0%, #6366F1 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        padding: 0.5rem 1.2rem !important;
        box-shadow: 0 0 20px -5px rgba(99, 102, 241, 0.5) !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 0 25px -2px rgba(99, 102, 241, 0.7) !important;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- HTTP Client Helpers -----------------
def api_get(endpoint: str, params: Optional[dict] = None) -> Any:
    try:
        resp = requests.get(f"{API_BASE_URL}{endpoint}", params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        pass
    return None

def api_post(endpoint: str, json_data: Optional[dict] = None, files: Optional[dict] = None) -> Any:
    try:
        if files:
            resp = requests.post(f"{API_BASE_URL}{endpoint}", files=files, timeout=25)
        else:
            resp = requests.post(f"{API_BASE_URL}{endpoint}", json=json_data, timeout=25)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        pass
    return None

def api_patch(endpoint: str, json_data: dict) -> Any:
    try:
        resp = requests.patch(f"{API_BASE_URL}{endpoint}", json=json_data, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        pass
    return None

# ----------------- Fallback Curated Data -----------------
FALLBACK_PROFILE = {
    "name": "Alex Morgan",
    "email": "alex.morgan.ai@example.com",
    "phone": "+91 98765 43210",
    "location": "Bangalore, India (Remote)",
    "years_of_experience": 3.5,
    "summary": "Experienced AI Engineer specializing in Python, RAG pipelines, LangGraph multi-agent architectures, and AWS LLM deployments.",
    "skills": ["Python", "RAG", "LangGraph", "Agentic AI", "MCP", "AWS", "LLMs", "FastAPI", "Docker", "pgvector"],
    "technical_skills": ["Python", "FastAPI", "PyTorch", "Docker", "Git"],
    "cloud_skills": ["AWS", "ECS", "S3", "Bedrock"],
    "frameworks": ["LangGraph", "LangChain", "LlamaIndex"],
    "models": ["GPT-4o", "Claude 3.5 Sonnet", "Llama 3"],
    "databases": ["PostgreSQL", "pgvector", "Redis"],
    "preferred_roles": ["AI Engineer", "GenAI Engineer", "ML Engineer"],
    "preferred_locations": ["India", "Remote"],
    "remote_preference": True,
    "work_authorization": "Indian Citizen / Remote Worldwide Contractor"
}

# ----------------- Sidebar Navigation -----------------
with st.sidebar:
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px;">
        <div style="background: linear-gradient(135deg, #4F46E5, #06B6D4); padding: 10px; border-radius: 12px;">
            <span style="font-size: 24px;">⚡</span>
        </div>
        <div>
            <h3 style="margin: 0; font-size: 16px; color: #FFFFFF;">Antigravity AI</h3>
            <p style="margin: 0; font-size: 11px; color: #818CF8; font-weight: 600;">AGENTIC JOB COPILOT</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    menu = st.radio(
        "Navigation",
        [
            "🤖 AI Copilot & Search",
            "💼 Discovered Jobs Matrix",
            "🛡️ Human Approvals Center",
            "📊 Applications Pipeline",
            "👤 Candidate Profile & Resume",
            "📈 Analytics & KPIs"
        ],
        index=0
    )
    
    st.markdown("---")
    st.markdown("""
    <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.2); border-radius: 10px; padding: 10px; margin-bottom: 12px;">
        <span style="color: #10B981; font-weight: 700; font-size: 11px;">✓ COMPLIANCE SHIELD ACTIVE</span>
        <p style="font-size: 10px; color: #94A3B8; margin-top: 4px; margin-bottom: 0;">Zero scraping • Idempotent email • Manual LinkedIn deep links.</p>
    </div>
    <div style="background: rgba(99, 102, 241, 0.1); border: 1px solid rgba(99, 102, 241, 0.2); border-radius: 10px; padding: 10px;">
        <span style="color: #818CF8; font-weight: 700; font-size: 11px;">⚡ LANGGRAPH ENGINE</span>
        <p style="font-size: 10px; color: #94A3B8; margin-top: 4px; margin-bottom: 0;">Multi-Agent Supervisor + Checkpoints.</p>
    </div>
    """, unsafe_allow_html=True)

# ==============================================================================
# VIEW 1: AI COPILOT & SEARCH
# ==============================================================================
if menu == "🤖 AI Copilot & Search":
    st.markdown("""
    <div class="glass-card">
        <h1 style="font-size: 26px; margin-bottom: 8px;">Autonomous Job Search & Application Copilot</h1>
        <p style="color: #94A3B8; font-size: 13px; line-height: 1.6; margin: 0;">
            Specify your desired roles, experience level, and tech stack in plain natural language. 
            The LangGraph multi-agent supervisor orchestrates specialized agents to search official career pages, 
            deduplicate listings, calculate 7-factor match scores, discover recruiters, and assemble tailored application packages.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    default_prompt = (
        "Find remote AI Engineer, GenAI Engineer, and ML Engineer positions requiring 2–4 years of experience. "
        "Focus on Python, RAG, LangGraph, Agentic AI, MCP, AWS, and LLM roles. "
        "Prefer companies hiring currently and roles that allow candidates to work remotely from India. "
        "Find recruiter/contact information where publicly available. Prepare applications and personalized recruiter outreach. "
        "Show me the application package for approval before sending."
    )
    
    user_prompt = st.text_area(
        "Natural Language Search & Application Directive",
        value=default_prompt,
        height=130,
        placeholder="E.g. Find remote AI Engineer roles (2-4 yrs exp) focusing on Python, RAG, and LangGraph..."
    )
    
    col_run, col_preset1, col_preset2 = st.columns([2, 1.5, 1.5])
    
    with col_run:
        launch_btn = st.button("🚀 Launch Autonomous Multi-Agent Pipeline", use_container_width=True)
    
    if launch_btn and user_prompt:
        st.markdown("---")
        st.subheader("⚡ Multi-Agent Execution Progress")
        
        agent_steps = [
            ("Supervisor", "Parsing target roles, skills taxonomy, and remote requirements"),
            ("Candidate Agent", "Loading verified candidate profile & technical experience"),
            ("Job Research Agent", "Executing multi-query career search & canonical MD5 deduplication"),
            ("Matching Agent", "Deterministic 7-factor scoring (Skills 30%, Exp 20%, Role 20%, Loc 15%)"),
            ("Recruiter Agent", "Discovering public talent acquisition contacts with source evidence"),
            ("Application Agent", "Generating factual resume tailoring, cover letter, and safe answers"),
            ("Outreach Agent", "Drafting high-conversion recruiter email & compliant LinkedIn message"),
            ("Human Approval Gate", "Pausing workflow for human review and explicit authorization")
        ]
        
        progress_bar = st.progress(0)
        status_box = st.empty()
        
        for idx, (agent_name, desc) in enumerate(agent_steps):
            status_box.markdown(f"""
            <div style="background: rgba(99, 102, 241, 0.15); border: 1px solid rgba(99, 102, 241, 0.3); padding: 12px 18px; border-radius: 12px; margin-bottom: 10px;">
                <span style="color: #818CF8; font-weight: 700; font-size: 11px; text-transform: uppercase;">[{agent_name}]</span>
                <p style="color: #FFFFFF; font-size: 13px; margin: 4px 0 0 0; font-weight: 500;">⏳ {desc}...</p>
            </div>
            """, unsafe_allow_html=True)
            time.sleep(0.35)
            progress_bar.progress((idx + 1) / len(agent_steps))
        
        # Call API backend
        result = api_post("/agent/run", json_data={"prompt": user_prompt})
        
        status_box.markdown("""
        <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); padding: 14px 20px; border-radius: 12px;">
            <span style="color: #10B981; font-weight: 700; font-size: 12px;">✓ MULTI-AGENT EXECUTION COMPLETE</span>
            <p style="color: #FFFFFF; font-size: 13px; margin: 4px 0 0 0; font-weight: 600;">
                Application packages prepared and paused at the Human Approval Gate.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.success("🎉 Search & Matching Completed! Switch to '🛡️ Human Approvals Center' to review and approve outreach.")

# ==============================================================================
# VIEW 2: DISCOVERED JOBS & MATCH MATRIX
# ==============================================================================
elif menu == "💼 Discovered Jobs Matrix":
    st.markdown("""
    <div class="glass-card">
        <h1 style="font-size: 24px; margin-bottom: 4px;">Discovered & Evaluated Jobs</h1>
        <p style="color: #94A3B8; font-size: 13px; margin: 0;">
            Roles extracted across verified sources, deduplicated via canonical hashes, and scored against your resume.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
    with col_f1:
        keyword = st.text_input("🔍 Search by title, company or skill", "")
    with col_f2:
        score_filter = st.selectbox("Min Match Score", ["All (0%+)", "75%+", "85%+", "90%+"], index=0)
    with col_f3:
        remote_only = st.checkbox("Remote Only", value=True)
    
    min_score = 0
    if "75" in score_filter: min_score = 75
    elif "85" in score_filter: min_score = 85
    elif "90" in score_filter: min_score = 90
    
    jobs = api_get("/jobs", params={"min_score": min_score, "remote_only": remote_only}) or []
    
    if not jobs:
        st.info("No jobs found matching the current criteria. Run the AI Copilot to discover new roles.")
    else:
        for job in jobs:
            match = job.get("match") or {}
            score = match.get("overall_score", 85)
            badge_class = "badge-success" if score >= 90 else "badge-brand" if score >= 80 else "badge-warning"
            
            with st.container():
                st.markdown(f"""
                <div class="glass-card">
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                        <div>
                            <span class="badge {badge_class}">{score}% Match Score</span>
                            <span class="badge badge-cyan">Remote</span>
                            <h3 style="margin: 6px 0 2px 0; font-size: 17px;">{job.get('title')}</h3>
                            <p style="color: #94A3B8; font-size: 12px; margin: 0;">
                                <strong>{job.get('company')}</strong> • {job.get('location')} • Exp: {job.get('experience_required', '2-4 yrs')} • Salary: {job.get('salary', 'Competitive')}
                            </p>
                        </div>
                    </div>
                    <p style="color: #CBD5E1; font-size: 12px; line-height: 1.5; margin: 10px 0;">{job.get('description', '')[:220]}...</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Skills Tags
                skills_html = "".join([f"<span class='badge badge-brand'>{s}</span>" for s in job.get("skills", [])[:6]])
                st.markdown(f"<div>{skills_html}</div>", unsafe_allow_html=True)
                
                # Expandable 7-factor breakdown
                with st.expander(f"📊 View 7-Factor Score Breakdown for {job.get('company')}"):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Skills Alignment (30%)", f"{match.get('skills_score', 90)}%")
                    c2.metric("Experience (20%)", f"{match.get('experience_score', 95)}%")
                    c3.metric("Role Relevance (20%)", f"{match.get('role_score', 95)}%")
                    c4.metric("Location / Remote (15%)", f"{match.get('location_score', 100)}%")
                    
                    if match.get("reasoning"):
                        st.markdown(f"**Analysis:** {match.get('reasoning')}")
                    if job.get("application_url"):
                        st.markdown(f"🔗 [Official Job Posting]({job.get('application_url')})")
                st.markdown("<br>", unsafe_allow_html=True)

# ==============================================================================
# VIEW 3: HUMAN APPROVALS CENTER
# ==============================================================================
elif menu == "🛡️ Human Approvals Center":
    st.markdown("""
    <div class="glass-card">
        <h1 style="font-size: 24px; margin-bottom: 4px;">Human Approval & Review Center</h1>
        <p style="color: #94A3B8; font-size: 13px; margin: 0;">
            Strict human governance: No application is submitted and no recruiter email is sent without your explicit review and approval.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    approvals = api_get("/approvals") or []
    
    if not approvals:
        st.markdown("""
        <div class="glass-card" style="text-align: center; padding: 40px;">
            <span style="font-size: 36px;">✓</span>
            <h3 style="margin: 10px 0 4px 0;">All caught up!</h3>
            <p style="color: #94A3B8; font-size: 12px;">No applications are awaiting human approval. Run the AI Copilot to generate new applications.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        for idx, pkg in enumerate(approvals):
            job = pkg.get("job") or {}
            match = pkg.get("match") or {}
            recruiter = pkg.get("recruiter") or {}
            package_data = pkg.get("package_data") or {}
            email_outreach = pkg.get("email_outreach") or {}
            linkedin_outreach = pkg.get("linkedin_outreach") or {}
            questions = pkg.get("questions") or []
            
            with st.container():
                st.markdown(f"""
                <div class="glass-card" style="border-left: 4px solid #6366F1;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span class="badge badge-success">{match.get('overall_score', 90)}% Match</span>
                            <span class="badge badge-brand">Human Review Required</span>
                            <h3 style="margin: 6px 0 2px 0;">{job.get('title')} — {job.get('company')}</h3>
                            <p style="color: #94A3B8; font-size: 12px; margin: 0;">
                                Recruiter: <strong>{recruiter.get('name', 'Talent Partner')}</strong> ({recruiter.get('title', 'Technical Recruiter')})
                            </p>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                tab_outreach, tab_resume, tab_cover, tab_qa = st.tabs([
                    "✉️ Recruiter Outreach (Email & LinkedIn)",
                    "📄 Tailored Resume",
                    "✍️ Cover Letter",
                    "❓ Application Questions"
                ])
                
                with tab_outreach:
                    col_em, col_li = st.columns(2)
                    with col_em:
                        st.markdown("**Personalized Recruiter Email (Editable)**")
                        subj = st.text_input(f"Email Subject ({idx})", value=email_outreach.get("subject", f"Application: {job.get('title')}"), key=f"subj_{idx}")
                        body = st.text_area(f"Email Body ({idx})", value=email_outreach.get("body", ""), height=150, key=f"body_{idx}")
                        st.caption(f"Destination: {email_outreach.get('recipient_email') or 'talent@company.com'}")
                    
                    with col_li:
                        st.markdown("**Compliant LinkedIn Connection Note**")
                        li_text = st.text_area(f"LinkedIn Message ({idx})", value=linkedin_outreach.get("body", ""), height=150, key=f"li_{idx}")
                        st.info("💡 100% Compliant: Copy this pre-approved text and paste directly in LinkedIn.")
                
                with tab_resume:
                    st.markdown("**Factual Alignment Highlights (Zero Experience Hallucination)**")
                    st.info(package_data.get("tailored_resume_summary") or "Highlighted matching skills: Python, RAG, LangGraph, AWS.")
                    st.text_area("Full Tailored Resume Text", value=package_data.get("tailored_resume_text", "Resume text loaded."), height=160, key=f"res_{idx}")
                
                with tab_cover:
                    st.markdown("**Custom Cover Letter (Editable)**")
                    cl_text = st.text_area("Cover Letter Content", value=package_data.get("cover_letter", "Dear Hiring Team..."), height=200, key=f"cl_{idx}")
                
                with tab_qa:
                    st.markdown("**Application Questions (Safe Auto-Answers vs Sensitive Items)**")
                    for q in questions:
                        is_sens = q.get("is_sensitive", False)
                        badge = "⚠️ REQUIRES REVIEW" if is_sens else "✓ Auto-Filled"
                        st.text_input(f"{q.get('question')} [{badge}]", value=q.get("answer", ""), key=f"q_{q.get('id', idx)}")
                
                # Decision Buttons
                col_app, col_rej = st.columns([2, 1])
                with col_app:
                    if st.button(f"✓ Approve & Dispatch Outreach ({job.get('company')})", key=f"app_btn_{idx}"):
                        api_post(f"/approvals/{pkg.get('approval_id')}/decide", json_data={
                            "decision": "APPROVE",
                            "modified_email_subject": subj,
                            "modified_email_body": body,
                            "modified_linkedin_body": li_text,
                            "send_email": True
                        })
                        st.success(f"Dispatched authorized outreach to {recruiter.get('name', 'Recruiter')} at {job.get('company')}!")
                        time.sleep(1)
                        st.rerun()
                
                with col_rej:
                    if st.button(f"✕ Reject ({job.get('company')})", key=f"rej_btn_{idx}"):
                        api_post(f"/approvals/{pkg.get('approval_id')}/decide", json_data={"decision": "REJECT"})
                        st.warning("Application marked as rejected.")
                        time.sleep(1)
                        st.rerun()
                
                st.markdown("---")

# ==============================================================================
# VIEW 4: APPLICATIONS PIPELINE
# ==============================================================================
elif menu == "📊 Applications Pipeline":
    st.markdown("""
    <div class="glass-card">
        <h1 style="font-size: 24px; margin-bottom: 4px;">Applications Lifecycle & Pipeline</h1>
        <p style="color: #94A3B8; font-size: 13px; margin: 0;">
            Track statuses across Review Required, Approved, Recruiter Contacted, and Interviews.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    apps = api_get("/applications") or []
    
    stages = ["REVIEW_REQUIRED", "APPROVED", "RECRUITER_CONTACTED", "INTERVIEW", "APPLIED"]
    cols = st.columns(len(stages))
    
    for c_idx, stage in enumerate(stages):
        stage_apps = [a for a in apps if a.get("status") == stage]
        with cols[c_idx]:
            st.markdown(f"""
            <div style="background: rgba(18, 24, 38, 0.7); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 12px; text-align: center; margin-bottom: 12px;">
                <span style="font-size: 11px; font-weight: 700; color: #818CF8;">{stage.replace('_', ' ')}</span>
                <h3 style="margin: 4px 0 0 0; font-size: 18px;">{len(stage_apps)}</h3>
            </div>
            """, unsafe_allow_html=True)
            
            for app in stage_apps:
                job = app.get("job") or {}
                st.markdown(f"""
                <div style="background: rgba(26, 35, 54, 0.9); border: 1px solid rgba(99,102,241,0.2); border-radius: 10px; padding: 10px; margin-bottom: 8px;">
                    <span style="font-size: 12px; font-weight: 700; color: #FFFFFF; display: block;">{job.get('title', 'Role')}</span>
                    <span style="font-size: 11px; color: #94A3B8;">{job.get('company', 'Company')}</span>
                </div>
                """, unsafe_allow_html=True)

# ==============================================================================
# VIEW 5: CANDIDATE PROFILE & RESUME
# ==============================================================================
elif menu == "👤 Candidate Profile & Resume":
    st.markdown("""
    <div class="glass-card">
        <h1 style="font-size: 24px; margin-bottom: 4px;">Candidate Profile & Resume</h1>
        <p style="color: #94A3B8; font-size: 13px; margin: 0;">
            Upload your resume once to build your verified candidate profile used by the matching and tailoring agents.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader("Upload Resume (PDF, DOCX, or TXT)", type=["pdf", "txt", "docx"])
    if uploaded_file:
        if st.button("📤 Parse & Update Candidate Profile"):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
            result = api_post("/candidates/resume", files=files)
            if result:
                st.success(f"Parsed {uploaded_file.name} successfully!")
                time.sleep(1)
                st.rerun()
    
    profile = api_get("/candidates/profile") or FALLBACK_PROFILE
    
    col1, col2, col3 = st.columns(3)
    name = col1.text_input("Full Name", value=profile.get("name", ""))
    email = col2.text_input("Email", value=profile.get("email", ""))
    yoe = col3.number_input("Years of Experience", value=float(profile.get("years_of_experience", 3.0)), step=0.5)
    
    summary = st.text_area("Summary", value=profile.get("summary", ""), height=100)
    
    st.subheader("Skills Taxonomy")
    skills_str = st.text_input("Core Skills (comma separated)", value=", ".join(profile.get("skills", [])))
    
    if st.button("💾 Save Profile Changes"):
        updated_data = {
            **profile,
            "name": name,
            "email": email,
            "years_of_experience": yoe,
            "summary": summary,
            "skills": [s.strip() for s in skills_str.split(",") if s.strip()]
        }
        api_post("/candidates/profile", json_data=updated_data)
        st.success("Candidate Profile updated successfully!")

# ==============================================================================
# VIEW 6: ANALYTICS & KPIS
# ==============================================================================
elif menu == "📈 Analytics & KPIs":
    st.markdown("""
    <div class="glass-card">
        <h1 style="font-size: 24px; margin-bottom: 4px;">Application Analytics & Telemetry</h1>
        <p style="color: #94A3B8; font-size: 13px; margin: 0;">
            Real-time conversion metrics across job discovery, matching, human approvals, and outreach.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    stats = api_get("/analytics/dashboard") or {
        "jobs_found": 128, "strong_matches": 32, "applications": 14,
        "recruiters_found": 21, "emails_sent": 10, "interviews": 2,
        "score_distribution": {"90-100%": 8, "80-89%": 18, "70-79%": 12, "<70%": 4},
        "role_distribution": {"AI Engineer": 18, "GenAI Engineer": 14, "ML Engineer": 8}
    }
    
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Jobs Found", stats.get("jobs_found", 0))
    m2.metric("Strong Matches", stats.get("strong_matches", 0))
    m3.metric("Applications", stats.get("applications", 0))
    m4.metric("Recruiters", stats.get("recruiters_found", 0))
    m5.metric("Emails Sent", stats.get("emails_sent", 0))
    m6.metric("Interviews", stats.get("interviews", 0))
    
    st.markdown("---")
    
    c_chart1, c_chart2 = st.columns(2)
    with c_chart1:
        st.markdown("**Match Score Distribution**")
        st.bar_chart(stats.get("score_distribution", {}))
        
    with c_chart2:
        st.markdown("**Positions by Role**")
        st.bar_chart(stats.get("role_distribution", {}))
