
import httpx

OLLAMA_URL = "http://localhost:11434"
MODEL_NAME = "qwen2.5:1.5b"


async def generate_response(prompt: str, json_mode: bool = False) -> str:
    """
    Send a prompt to the locally running Ollama model
    and return its generated response.

    With json_mode=True Ollama is asked to return valid JSON. The caller must still
    validate the content: valid JSON is not the same as a correct answer.
    """

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
    }
    if json_mode:
        payload["format"] = "json"

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json=payload,
            )

            response.raise_for_status()
            result = response.json()

            return result.get("response", "")

    except httpx.ConnectError as exc:
        raise RuntimeError(
            "Cannot connect to Ollama. Make sure Ollama is running."
        ) from exc

    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Ollama returned an HTTP error: {exc.response.status_code}"
        ) from exc
