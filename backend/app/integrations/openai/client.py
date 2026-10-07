import logging
import asyncio
from typing import Optional, Any
try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

from app.config.settings import settings

logger = logging.getLogger(__name__)

class OpenAIClientWrapper:
    """
    Optional legacy helper - NOT used in ChatGPT Web + MCP workflow.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, "OPENAI_API_KEY", None)
        self.client: Optional[Any] = AsyncOpenAI(api_key=self.api_key) if (AsyncOpenAI and self.api_key) else None

    def is_configured(self) -> bool:
        return self.client is not None and bool(self.api_key)

    async def create_web_search_response(
        self,
        instructions: str,
        input_prompt: str,
        model: Optional[str] = None,
        context_size: Optional[str] = None
    ) -> Any:
        """
        Executes a response request via OpenAI Responses API with the web_search tool.
        """
        if not self.is_configured():
            raise RuntimeError("OpenAI API key is not configured. Set OPENAI_API_KEY in environment or .env.")

        chosen_model = model or settings.effective_openai_model
        chosen_context = context_size or settings.OPENAI_WEB_SEARCH_CONTEXT_SIZE or "high"

        # Web Search Tool specification for OpenAI Responses API
        tools = [
            {
                "type": "web_search",
                "search_context_size": chosen_context
            }
        ]

        try:
            logger.info(f"Invoking OpenAI Responses API with model={chosen_model}, web_search (context={chosen_context})...")
            response = await self.client.responses.create(
                model=chosen_model,
                instructions=instructions,
                input=input_prompt,
                tools=tools
            )
            return response
        except Exception as e:
            logger.error(f"OpenAI Responses API error: {e}")
            raise

openai_client_wrapper = OpenAIClientWrapper()
