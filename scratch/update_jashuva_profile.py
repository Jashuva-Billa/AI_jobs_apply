import requests
import json

BASE_URL = "http://localhost:8000/api"

profile_payload = {
    "name": "Jashuva Billa",
    "email": "jashuvabilla@gmail.com",
    "phone": "+91 9618751495",
    "location": "Hyderabad, India",
    "years_of_experience": 2.0,
    "summary": "AI Engineer specializing in Generative AI, LangGraph multi-agent orchestration, RAG pipelines, MCP tool execution, and AWS deployment.",
    "skills": [
        "Python", "SQL", "Generative AI", "LLMs", "RAG", "Agentic AI", "Multi-Agent Systems",
        "LangGraph", "LangChain", "MCP", "Milvus", "Semantic Search", "BM25", "Hybrid Retrieval",
        "Reciprocal Rank Fusion (RRF)", "Cross-Encoder Reranking", "Docling", "Sentence Transformers",
        "RAGAS", "DeepEval", "Bedrock Guardrails", "FastAPI", "PostgreSQL", "Redis", "AWS Bedrock",
        "EKS", "ECR", "Lambda", "Docker", "Langfuse", "OpenTelemetry"
    ],
    "technical_skills": ["Python", "SQL", "FastAPI", "Docker", "Git"],
    "cloud_skills": ["AWS Bedrock", "EKS", "ECR", "Lambda", "API Gateway", "S3", "SageMaker", "CloudWatch"],
    "frameworks": ["LangGraph", "LangChain", "MCP"],
    "models": ["GPT-4o", "Claude 3.5 Sonnet", "Llama 3", "all-MiniLM-L6-v2", "E5"],
    "databases": ["PostgreSQL", "Milvus", "Redis/ElastiCache"],
    "certifications": [],
    "education": [
        {
            "degree": "Bachelor of Technology in Computer Science",
            "institution": "Jawaharlal Nehru Technological University Hyderabad",
            "year": "2019 - 2023"
        }
    ],
    "work_experience": [
        {
            "title": "AI Engineer",
            "company": "Innovapath IT solutions",
            "duration": "Feb 2024 - Present",
            "description": "Built enterprise Generative AI and Agentic AI assistants using RAG, LangGraph orchestration, domain agents, tool calling, memory, and policy-driven execution. Designed stateful LangGraph workflows with intent routing, conditional branching, reflection loops, checkpointing, and resumability. Implemented MCP-based tool execution, hybrid RAG (Milvus + BM25 + RRF), context engineering, AI safety guardrails, and AWS containerized deployments.",
            "technologies": ["Python", "LangGraph", "RAG", "MCP", "Milvus", "FastAPI", "AWS", "Langfuse"]
        }
    ],
    "projects": [
        {
            "name": "Enterprise Agentic Copilot & Multi-Agent Orchestrator",
            "description": "Multi-agent architecture coordinating triage, knowledge/troubleshooting, service, billing, and policy agents through LangGraph with MCP tools.",
            "technologies": ["Python", "LangGraph", "MCP", "FastAPI", "Milvus", "Docker"]
        }
    ],
    "preferred_roles": ["AI Engineer", "GenAI Engineer", "Agentic AI Engineer", "LLM Engineer", "Machine Learning Engineer"],
    "preferred_locations": ["Hyderabad", "Bangalore", "Remote", "India"],
    "remote_preference": True,
    "work_authorization": "Indian Citizen / Authorized for remote global employment"
}

# 1. Update Profile
print("Updating Candidate Profile on Backend API...")
resp = requests.put(f"{BASE_URL}/candidates/profile", json=profile_payload)
print(f"Profile Update Status: {resp.status_code}")
if resp.status_code == 200:
    print(f"Candidate Updated: {resp.json().get('name')} | {resp.json().get('email')}")

# 2. Trigger Multi-Agent Run with Jashuva's directive
prompt = (
    "Find remote AI Engineer, GenAI Engineer, and Agentic AI roles requiring 1-3 years of experience. "
    "Focus on Python, RAG, LangGraph, Agentic AI, MCP, AWS, and Milvus. I am based in India and open to remote positions. "
    "Find strong opportunities and recruiter information, and prepare a tailored application package."
)

print("\nTriggering Multi-Agent Run for Jashuva Billa...")
agent_resp = requests.post(f"{BASE_URL}/agent/run", json={"prompt": prompt})
print(f"Agent Run Status: {agent_resp.status_code}")
if agent_resp.status_code == 200:
    data = agent_resp.json()
    print(f"Jobs Discovered: {data.get('jobs_found')}")
    print(f"Matches Evaluated: {data.get('matches_count')}")
    print(f"Approval Required: {data.get('approval_required')}")
    sel = data.get("selected_job", {})
    print(f"Top Matched Role: {sel.get('title')} at {sel.get('company')} (Match Score: {sel.get('match', {}).get('overall_score')}%)")

# 3. Fetch Pending Approvals
app_resp = requests.get(f"{BASE_URL}/approvals")
if app_resp.status_code == 200:
    approvals = app_resp.json()
    print(f"\nTotal Pending Approval Packages: {len(approvals)}")
    for idx, a in enumerate(approvals):
        j = a.get("job", {})
        m = a.get("match", {})
        r = a.get("recruiter", {})
        print(f"\n--- Package {idx+1}: {j.get('title')} @ {j.get('company')} ({m.get('overall_score')}% Match) ---")
        print(f"Recruiter: {r.get('name')} ({r.get('title')}) - {r.get('public_email') or 'No public email (LinkedIn prep ready)'}")
        print(f"Email Subject: {a.get('email_outreach', {}).get('subject')}")
        print(f"Tailored Summary: {a.get('package_data', {}).get('tailored_resume_summary')}")
