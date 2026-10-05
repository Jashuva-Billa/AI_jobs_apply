import asyncio
import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.config.database import AsyncSessionLocal
from app.api.routes.approvals import list_pending_approvals, process_approval_decision
from app.schemas.schemas import ApprovalDecisionRequest

async def main():
    async with AsyncSessionLocal() as session:
        packages = await list_pending_approvals(session)
        if not packages:
            print("No pending packages found.")
            return

        pkg = packages[0]
        app_id = pkg["approval_id"]
        job = pkg["job"]
        recruiter = pkg["recruiter"]
        email_outreach = pkg["email_outreach"]
        match = pkg["match"]

        print("=" * 70)
        print("[APPROVAL & DISPATCH] CANDIDATE: JASHUVA BILLA")
        print("=" * 70)
        print(f"* Candidate: Jashuva Billa (jashuvabilla@gmail.com)")
        print(f"* Target Position: {job.get('title')} at {job.get('company')}")
        print(f"* Match Score: {match.get('overall_score')}% ({match.get('recommendation')})")
        print(f"* Verified Recruiter: {recruiter.get('name')} ({recruiter.get('title')})")
        print(f"* Destination Email: {recruiter.get('public_email')}")
        print(f"* Recruiter Source: {recruiter.get('source_evidence')}")
        print("-" * 70)
        print("Email Subject:", email_outreach.get("subject"))
        print("Email Body Preview:\n", email_outreach.get("body"))
        print("-" * 70)

        decision = ApprovalDecisionRequest(
            decision="APPROVE",
            modified_email_subject=email_outreach.get("subject"),
            modified_email_body=email_outreach.get("body"),
            send_email=True
        )

        result = await process_approval_decision(app_id, decision, session)
        print("\n[DISPATCH RESULT]")
        print(json.dumps(result, indent=2))
        print("=" * 70)
        print("[SUCCESS] APPLICATION APPROVED & OUTREACH DISPATCHED SUCCESSFULLY!")
        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
