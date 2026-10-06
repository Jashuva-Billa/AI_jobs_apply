import sys
import asyncio
sys.path.insert(0, ".")
from dotenv import load_dotenv

load_dotenv()
load_dotenv("../.env")

from app.config.settings import settings
from app.integrations.llm.provider import llm_provider

print(f"Provider: {settings.effective_llm_provider}")
print(f"Model: {settings.effective_llm_model}")
print(f"Base URL: {settings.effective_llm_base_url}")
print(f"Key preview: {settings.effective_llm_api_key[:10]}...")

async def main():
    text = await llm_provider.generate_text(
        system_prompt="You are an AI assistant.",
        user_prompt="Say 'Gemini is successfully configured!' in exactly 4 words."
    )
    print("Generated Text:", text)

if __name__ == "__main__":
    asyncio.run(main())
