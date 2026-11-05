
import asyncio
from app.ai.ollama_client import generate_response


async def main():
    prompt = """
    You are the CreatorOS AI assistant.

    Give three practical video ideas for a beginner
    programming education YouTube channel.

    Keep the answer concise.
    """

    result = await generate_response(prompt)

    print("\nCREATOROS AI RESPONSE:\n")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
