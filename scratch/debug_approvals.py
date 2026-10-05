import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.config.database import AsyncSessionLocal
from app.api.routes.approvals import list_pending_approvals

async def main():
    async with AsyncSessionLocal() as session:
        packages = await list_pending_approvals(session)
        print("Direct function call packages count:", len(packages))
        for p in packages:
            print("Package:", p.get("job", {}).get("title"), "at", p.get("job", {}).get("company"))

if __name__ == "__main__":
    asyncio.run(main())
