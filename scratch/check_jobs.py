import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.config.database import AsyncSessionLocal
from app.models.entities import Job, Application, ApprovalRequest
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as session:
        jobs = (await session.execute(select(Job))).scalars().all()
        print(f"Jobs ({len(jobs)}):")
        for j in jobs:
            print(f"  ID: {j.id} | {j.title} @ {j.company}")
        
        apps = (await session.execute(select(Application))).scalars().all()
        print(f"\nApplications ({len(apps)}):")
        for a in apps:
            print(f"  App ID: {a.id} | Job ID: {a.job_id} | Status: {a.status}")

        reqs = (await session.execute(select(ApprovalRequest))).scalars().all()
        print(f"\nApproval Requests ({len(reqs)}):")
        for r in reqs:
            print(f"  Req ID: {r.id} | App ID: {r.application_id} | Status: {r.status}")

if __name__ == "__main__":
    asyncio.run(main())
