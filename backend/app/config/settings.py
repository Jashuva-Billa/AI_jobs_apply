from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Agentic Job Search & Application Platform"
    API_V1_STR: str = "/api"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    DEMO_MODE: bool = False
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./jobs_platform.db"
    
    # LLM Provider Configuration (Gemini Primary, OpenAI Optional)
    LLM_PROVIDER: str = "gemini" # "gemini" or "openai"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.8-flash"
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"
    LLM_MODEL: Optional[str] = None # Backward compatibility
    LLM_TEMPERATURE: float = 0.2
    
    # OpenAI Web Search Configuration (Optional)
    OPENAI_WEB_SEARCH_ENABLED: bool = True
    OPENAI_WEB_SEARCH_CONTEXT_SIZE: str = "high" # low, medium, high
    
    # Observability
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_HOST: Optional[str] = "https://cloud.langfuse.com"
    
    # Security & Encryption
    SECRET_KEY: str = "agentic-secret-key-for-local-development-change-in-production-123456"
    
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
    
    # Matching Thresholds
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

    @property
    def effective_llm_provider(self) -> str:
        if self.GEMINI_API_KEY and self.LLM_PROVIDER == "gemini":
            return "gemini"
        if self.OPENAI_API_KEY:
            return "openai"
        if self.GEMINI_API_KEY:
            return "gemini"
        return "gemini"

    @property
    def effective_llm_api_key(self) -> Optional[str]:
        if self.effective_llm_provider == "gemini":
            return self.GEMINI_API_KEY
        return self.OPENAI_API_KEY or self.GEMINI_API_KEY

    @property
    def effective_llm_base_url(self) -> Optional[str]:
        if self.effective_llm_provider == "gemini":
            return self.GEMINI_BASE_URL
        return None

    @property
    def effective_llm_model(self) -> str:
        if self.effective_llm_provider == "gemini":
            return self.GEMINI_MODEL
        return self.OPENAI_MODEL or self.LLM_MODEL or "gpt-4o"

    @property
    def effective_openai_model(self) -> str:
        return self.OPENAI_MODEL or self.LLM_MODEL or "gpt-4o"

settings = Settings()
