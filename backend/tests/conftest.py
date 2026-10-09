import os
import sys
import pytest
import pytest_asyncio

# Ensure backend root is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config.database import Base, engine
from app.main import app, seed_initial_data, run_safe_migrations

@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_test_database():
    """Initializes schema before running each test on current event loop."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await run_safe_migrations()
    await seed_initial_data()
    yield
    await engine.dispose()
