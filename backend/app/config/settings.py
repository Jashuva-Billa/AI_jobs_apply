from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Agentic Job Search & Application Platform"
    API_V1_STR: str = "/api"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    DEMO_MODE: bool = False
    DRY_RUN: bool = False
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./jobs_platform.db"
    
    # LLM Architecture: ChatGPT Web is the AI reasoning layer via MCP.
    # No backend LLM API keys (OpenAI / Gemini) are required.
    LLM_PROVIDER: str = "chatgpt_mcp"
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    
    # Web Search & Data Providers
    OPENAI_WEB_SEARCH_ENABLED: bool = False
    
    # Observability
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_HOST: Optional[str] = "https://cloud.langfuse.com"
    
    # Security & Encryption
    SECRET_KEY: str = "agentic-secret-key-for-local-development-change-in-production-123456"
    ALLOWED_HOSTS: str = "localhost,127.0.0.1,celery-ecosystem-suspense.ngrok-free.dev"
    MCP_PUBLIC_URL: Optional[str] = None
    MCP_ALLOWED_ORIGINS: Optional[str] = None
    
    # OAuth Credentials
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    MICROSOFT_CLIENT_ID: Optional[str] = None
    MICROSOFT_CLIENT_SECRET: Optional[str] = None
    
    # Email Settings
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: str = "candidate@example.com"
    
    # AWS Settings (Optional)
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET: Optional[str] = None
    
    # Matching Thresholds (7-Factor Deterministic Model)
    STRONG_MATCH_THRESHOLD: float = 85.0
    MATCH_THRESHOLD: float = 75.0
    POSSIBLE_MATCH_THRESHOLD: float = 65.0
    
    # Bounded Concurrency for Batch Processing
    MAX_CONCURRENT_APPLICATIONS: int = 10
    MAX_CONCURRENT_RECRUITER_RESEARCH: int = 5
    
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

