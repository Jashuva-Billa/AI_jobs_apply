import sys
import os
import asyncio
import logging
from sqlalchemy import text

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.config.database import AsyncSessionLocal, engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migrate_db")

async def run_migrations():
    """Applies safe column additions for MySQL database schema."""
    logger.info("Checking database schema and applying migrations...")
    async with engine.begin() as conn:
        # Check jobs table columns
        res = await conn.execute(text("SHOW COLUMNS FROM jobs"))
        job_cols = {row[0] for row in res.fetchall()}
        
        if "recruiter_email" not in job_cols:
            logger.info("Adding recruiter_email to jobs table...")
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN recruiter_email VARCHAR(255) NULL"))
        if "application_email" not in job_cols:
            logger.info("Adding application_email to jobs table...")
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN application_email VARCHAR(255) NULL"))
        if "contact_email" not in job_cols:
            logger.info("Adding contact_email to jobs table...")
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN contact_email VARCHAR(255) NULL"))

        # Check outreach_messages table columns
        res_o = await conn.execute(text("SHOW COLUMNS FROM outreach_messages"))
        outreach_cols = {row[0] for row in res_o.fetchall()}

        if "email_status" not in outreach_cols:
            logger.info("Adding email_status to outreach_messages table...")
            await conn.execute(text("ALTER TABLE outreach_messages ADD COLUMN email_status VARCHAR(64) DEFAULT 'NOT_FOUND'"))
        if "email_source" not in outreach_cols:
            logger.info("Adding email_source to outreach_messages table...")
            await conn.execute(text("ALTER TABLE outreach_messages ADD COLUMN email_source VARCHAR(64) NULL"))
        if "email_confidence" not in outreach_cols:
            logger.info("Adding email_confidence to outreach_messages table...")
            await conn.execute(text("ALTER TABLE outreach_messages ADD COLUMN email_confidence FLOAT DEFAULT 0.0"))
        if "recruiter_status" not in outreach_cols:
            logger.info("Adding recruiter_status to outreach_messages table...")
            await conn.execute(text("ALTER TABLE outreach_messages ADD COLUMN recruiter_status VARCHAR(64) DEFAULT 'NOT_FOUND'"))

    logger.info("Migrations completed successfully.")

if __name__ == "__main__":
    asyncio.run(run_migrations())
