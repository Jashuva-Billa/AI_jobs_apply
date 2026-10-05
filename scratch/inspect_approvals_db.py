import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.config.database import AsyncSessionLocal
from app.models.entities import ApprovalRequest, Application, CandidateProfile, Job, OutreachMessage
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as session:
        cands = (await session.execute(select(CandidateProfile))).scalars().all()
        print(f"Candidates ({len(cands)}):", [c.name for c in cands])
        
        apps = (await session.execute(select(Application))).scalars().all()
        print(f"Applications ({len(apps)}):", [(a.id, a.status.value) for a in apps])
        
        reqs = (await session.execute(select(ApprovalRequest))).scalars().all()
        print(f"Approval Requests ({len(reqs)}):", [(r.id, r.status.value, r.application_id) for r in reqs])

        outreaches = (await session.execute(select(OutreachMessage))).scalars().all()
        print(f"Outreach Messages ({len(outreaches)}):", [(o.id, o.channel, o.recipient_email, o.status) for o in outreaches])

if __name__ == "__main__":
    asyncio.run(main())
