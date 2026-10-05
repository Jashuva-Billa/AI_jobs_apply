import asyncio
from sqlalchemy import text
from app.config.database import engine

async def migrate():
    print("Migrating MySQL Database Schema...")
    async with engine.begin() as conn:
        # Agent Runs table columns
        agent_run_cols = [
            ("candidate_id", "VARCHAR(64) NULL"),
            ("search_prompt", "TEXT NULL"),
            ("total_jobs", "INT DEFAULT 0"),
            ("unique_jobs", "INT DEFAULT 0"),
            ("qualified_jobs", "INT DEFAULT 0"),
            ("strong_matches", "INT DEFAULT 0"),
            ("applications_prepared", "INT DEFAULT 0"),
            ("approvals_pending", "INT DEFAULT 0"),
            ("applications_approved", "INT DEFAULT 0"),
            ("applications_rejected", "INT DEFAULT 0"),
            ("created_at", "DATETIME NULL"),
            ("started_at", "DATETIME NULL"),
            ("completed_at", "DATETIME NULL"),
        ]
        for col_name, col_type in agent_run_cols:
            try:
                await conn.execute(text(f"ALTER TABLE agent_runs ADD COLUMN {col_name} {col_type};"))
                print(f"Added column agent_runs.{col_name}")
            except Exception as e:
                print(f"Skipping agent_runs.{col_name} ({e})")

        # Jobs table
        try:
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN run_id VARCHAR(64) NULL;"))
            print("Added column jobs.run_id")
        except Exception as e:
            print(f"Skipping jobs.run_id ({e})")

        # Applications table
        try:
            await conn.execute(text("ALTER TABLE applications ADD COLUMN run_id VARCHAR(64) NULL;"))
            print("Added column applications.run_id")
        except Exception as e:
            print(f"Skipping applications.run_id ({e})")

        # Approval Requests table
        try:
            await conn.execute(text("ALTER TABLE approval_requests ADD COLUMN run_id VARCHAR(64) NULL;"))
            print("Added column approval_requests.run_id")
        except Exception as e:
            print(f"Skipping approval_requests.run_id ({e})")

    print("Migration complete.")

if __name__ == "__main__":
    asyncio.run(migrate())
