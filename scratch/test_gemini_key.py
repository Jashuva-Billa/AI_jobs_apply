import asyncio
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()
load_dotenv("../.env")

api_key = os.getenv("GEMINI_API_KEY")
print(f"Loaded key: {api_key[:10]}... (len={len(api_key) if api_key else 0})")

async def main():
    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    models_to_test = ["gemini-3.8-flash", "gemini-3.8-pro", "gemini-2.5-flash", "models/gemini-3.8-flash"]
    for m in models_to_test:
        try:
            print(f"Testing model {m}...")
            response = await client.chat.completions.create(
                model=m,
                messages=[{"role": "user", "content": "Hello, answer in 5 words."}]
            )
            print(f"SUCCESS with {m}:", response.choices[0].message.content)
            break
        except Exception as e:
            print(f"Failed {m}:", e)

if __name__ == "__main__":
    asyncio.run(main())
