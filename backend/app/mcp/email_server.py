from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any, List
from app.integrations.email.provider import email_provider

class SendEmailParams(BaseModel):
    to_email: str
    subject: str
    body: str
    idempotency_key: Optional[str] = None

class CreateDraftParams(BaseModel):
    to_email: str
    subject: str
    body: str

class EmailMCPTool:
    @staticmethod
    async def create_draft(params: CreateDraftParams) -> Dict[str, Any]:
        return await email_provider.create_draft(
            to_email=params.to_email,
            subject=params.subject,
            body=params.body
        )

    @staticmethod
    async def send_email(params: SendEmailParams) -> Dict[str, Any]:
        return await email_provider.send_email(
            to_email=params.to_email,
            subject=params.subject,
            body=params.body,
            idempotency_key=params.idempotency_key
        )

email_mcp_tool = EmailMCPTool()
