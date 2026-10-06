# Human-In-The-Loop (HITL) Workflow & Safety Guarantees

## 1. Overview
The **AI Job Platform MCP** enforces strict Human-In-The-Loop (HITL) boundaries. Autonomous actions like sending emails or submitting applications are gated behind explicit approval checks stored authoritatively in SQL.

---

## 2. End-to-End Workflow

```text
1. Job Discovery (search_jobs)
   └── Fetches live jobs & creates SearchRun in SQL.

2. Deterministic Matching (match_jobs)
   └── Scores fit (Skills 30%, Exp 20%, Role 20%, Loc 15%, Cloud 5%, Edu 5%, Domain 5%).

3. Application Preparation (prepare_applications_batch)
   └── Generates factual resume tailoring, cover letters, and email drafts.
   └── Creates durable ApprovalRequest records in SQL with status PENDING.
   └── Sets SearchRun status to WAITING_FOR_APPROVAL.

4. Human Review (get_pending_approvals)
   └── ChatGPT retrieves the pending approval records.
   └── Displays an approval table to the user with match scores and email previews.

5. Explicit Human Confirmation (approve_applications)
   └── User says: "Approve all" or "Approve the top 10".
   └── ChatGPT invokes approve_applications(approval_ids=[...]).
   └── SQL status updates to APPROVED.

6. Authorized Outreach (send_approved_email)
   └── Dispatches email only for APPROVED applications.
   └── Enforces idempotency key: candidate_id:job_id:EMAIL_OUTREACH.
```

---

## 3. Safety Rules & Compliance

1. **No Automatic Email Dispatch:**
   The MCP server will throw an error if `send_approved_email` is called on an application whose status is not `APPROVED`.

2. **Idempotency Guarantees:**
   Every outreach action is guarded by `candidate_id:job_id:EMAIL_OUTREACH`. Multiple calls will NOT send duplicate emails.

3. **100% LinkedIn Platform Compliance:**
   No session-cookie hijacking, browser automation, or unauthorized scrapers. LinkedIn outreach is exposed through pre-formatted copy and deep links to recruiter profiles for manual confirmation.

4. **Zero Hallucination Policy:**
   Application artifacts only draw from the candidate's actual profile (Jashuva Billa, 2.9 years of experience). No fake degrees, certifications, or employers are generated.
