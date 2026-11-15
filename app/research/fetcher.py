import httpx

from .verify import html_to_text

MAX_BYTES = 2_000_000
HEADERS = {"User-Agent": "CreatorOS-MVP/0.1 (personal research tool)"}


class FetchError(Exception):
    pass


async def fetch_page_text(url: str) -> dict:
    """Fetch ONE user-supplied page and return its visible text."""
    try:
        async with httpx.AsyncClient(
            timeout=20.0, follow_redirects=True, headers=HEADERS
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise FetchError("The page took too long to respond.") from exc
    except httpx.HTTPStatusError as exc:
        raise FetchError(f"The site returned HTTP {exc.response.status_code}.") from exc
    except httpx.HTTPError as exc:
        raise FetchError("Could not reach the page.") from exc

    content_type = response.headers.get("content-type", "").lower()
    if "html" not in content_type and "text/plain" not in content_type:
        raise FetchError(f"Unsupported content type: {content_type or 'unknown'}.")
    if len(response.content) > MAX_BYTES:
        raise FetchError("The page is too large to check.")

    title, text = html_to_text(response.text)
    return {"final_url": str(response.url), "title": title, "text": text}