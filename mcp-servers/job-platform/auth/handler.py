import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class MCPAuthHandler:
    """
    Manages authentication and access control for the MCP Server.
    Supports development mode, static API key verification, and OAuth tokens.
    """
    def __init__(self):
        self.auth_mode = os.getenv("MCP_AUTH_MODE", "development").lower()
        self.secret_token = os.getenv("MCP_SECRET_TOKEN") or os.getenv("SECRET_KEY", "mcp-default-secret-token")

    def verify_token(self, token: Optional[str]) -> bool:
        if self.auth_mode == "development":
            return True
        
        if not token:
            return False
            
        clean_token = token.replace("Bearer ", "").strip()
        return clean_token == self.secret_token

    def get_auth_metadata(self) -> Dict[str, Any]:
        return {
            "mode": self.auth_mode,
            "status": "DEVELOPMENT_PERMISSIVE" if self.auth_mode == "development" else "PROTECTED"
        }

mcp_auth = MCPAuthHandler()
