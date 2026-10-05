# System Architecture

The **Agentic Job Search & Application Platform** is designed as a distributed, multi-agent AI system with strong human-in-the-loop governance.

## Architecture Diagram

```text
                         ┌─────────────────────┐
                         │      Web UI          │
                         │ React / Vite / TS    │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │      FastAPI        │
                         │      Backend        │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Agent Supervisor    │
                         │     LangGraph       │
                         └──────────┬──────────┘
                                    │
       ┌────────────────────────────┼─────────────────────────────┐
       │                            │                             │
       ▼                            ▼                             ▼
 Job Research Agent         Candidate Agent              Recruiter Agent
       │                            │                             │
       ▼                            ▼                             ▼
 Web Search                  Resume Parser                Recruiter Search
 Company Careers             Skill Extraction             Contact Discovery
 Job Sources                 Profile Matching             Outreach
       │                            │                             │
       └────────────────────────────┼─────────────────────────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Job Matching Agent  │
                         │ Semantic + Determin.│
                         └──────────┬──────────┘
                                    │
                         ┌─────────────────────┐
                         │ Application Agent   │
                         └──────────┬──────────┘
                                    │
                         ┌──────────┴──────────┐
                         ▼                     ▼
                   Email MCP              LinkedIn Adapter
                         │                     │
                         └──────────┬──────────┘
                                    ▼
                          HUMAN APPROVAL GATE
                                    │
                                    ▼
                            Execute Action
                                    │
                                    ▼
                           Application Tracker
```

## Multi-Agent Specialization
1. **Supervisor**: Analyzes the natural language user prompt into typed `SearchCriteria`.
2. **Candidate Agent**: Ingests resume files and builds a structured, validated `CandidateProfile`.
3. **Job Research Agent**: Executes multi-query search strategies across verified career portals, normalizing and deduplicating openings with canonical MD5 hashes.
4. **Matching Agent**: Evaluates deterministic scores (Skills 30%, Experience 20%, Role 20%, Location 15%, Cloud 5%, Education 5%, Domain 5%) combined with LLM semantic reasoning.
5. **Recruiter Agent**: Identifies public talent acquisition contacts with verifiable source evidence, adhering to zero personal email hallucination.
6. **Application Agent**: Generates factual resume tailoring (zero experience fabrication), customized cover letters, and safe application answers.
7. **Outreach Agent**: Drafts concise personalized recruiter emails and compliant LinkedIn connection notes.
8. **Human Approval Gate**: Intercepts irreversible actions and presents full review packages.
