"""Pure helpers for content planning: prompts, strict parsing and an unsupported-number check.

Nothing here talks to the database, the network or the model, so it is fast to test.
"""

import json
import re

MAX_EVIDENCE_CHARS = 350
MIN_SCRIPT_CHARS = 200
MAX_SCRIPT_CHARS = 8000


class PlanningError(Exception):
    """The model's answer was unusable. Nothing should be saved."""


def evidence_summary(rows: list[tuple[str, int, str]]) -> str:
    """rows = (criterion, score, observation). One short bullet per row."""
    lines = []
    for criterion, score, observation in rows:
        text = " ".join(observation.split())[:MAX_EVIDENCE_CHARS]
        lines.append(f"- {criterion} (score {score}/10): {text}")
    return "\n".join(lines)


def build_ideas_prompt(niche_name: str, evidence: str, count: int) -> str:
    return f"""You are a content planning assistant for a creator who makes educational videos.

Niche: {niche_name}

Reviewed evidence about this niche (written by a human reviewer, treat as the only facts available):
{evidence}

Propose {count} different video ideas for this niche. Base them on the evidence above.
Do not invent statistics, prices, commission rates, names or websites.

Answer with JSON only, in exactly this shape:
{{"ideas": [{{"title": "<video title>", "hook": "<one sentence that opens the video>", "outline": ["<short point>", "<short point>", "<short point>"]}}]}}

Each outline needs 3 to 6 short points."""


def build_script_prompt(niche_name: str, title: str, hook: str, outline: list[str], evidence: str) -> str:
    points = "\n".join(f"{i}. {p}" for i, p in enumerate(outline, start=1))
    return f"""You are a scriptwriter for a creator who makes calm, honest educational videos.

Niche: {niche_name}
Video title: {title}
Opening hook: {hook}
Outline:
{points}

Reviewed evidence (the ONLY facts you may use):
{evidence}

Write the spoken script in plain text, about 400 to 600 words, following the outline.
Use only facts from the reviewed evidence. If you need a number or fact that is not listed, write [NEEDS SOURCE] instead of inventing one.
Do not promise earnings or results. Do not use markdown headings."""


def parse_ideas(raw: str, max_ideas: int) -> list[dict]:
    """Return the valid ideas (at most max_ideas). Raises PlanningError if none are valid."""
    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise PlanningError("The model did not return valid JSON.") from exc
    items = data.get("ideas") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise PlanningError("The model answer did not contain an 'ideas' list.")

    valid = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title, hook, outline = item.get("title"), item.get("hook"), item.get("outline")
        if not (isinstance(title, str) and 5 <= len(title.strip()) <= 200):
            continue
        if not (isinstance(hook, str) and 10 <= len(hook.strip()) <= 500):
            continue
        if not (isinstance(outline, list) and 2 <= len(outline) <= 8):
            continue
        points = [p.strip() for p in outline if isinstance(p, str) and 3 <= len(p.strip()) <= 300]
        if len(points) != len(outline):
            continue
        valid.append({"title": title.strip(), "hook": hook.strip(), "outline": points})
        if len(valid) == max_ideas:
            break
    if not valid:
        raise PlanningError("The model returned no usable ideas.")
    return valid


def clean_script(raw: str) -> str:
    text = (raw or "").strip()
    if not MIN_SCRIPT_CHARS <= len(text) <= MAX_SCRIPT_CHARS:
        raise PlanningError(
            f"The script must be {MIN_SCRIPT_CHARS} to {MAX_SCRIPT_CHARS} characters; got {len(text)}."
        )
    return text


_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?%?")


def _numbers(text: str) -> set[str]:
    found = set()
    for match in _NUMBER.findall(text):
        found.add(match.replace(",", "").rstrip("."))
    return found


def find_unsupported_numbers(script: str, *allowed_texts: str) -> list[str]:
    """Numbers used in the script that appear in none of the allowed texts.

    Bare whole numbers from 0 to 10 are ignored (list numbers, "3 tips"). A small model that
    invents a statistic such as "47%" or "12,000 subscribers" will show up here.
    """
    allowed = set()
    for text in allowed_texts:
        allowed |= _numbers(text)
    unsupported = []
    for match in _NUMBER.finditer(script):  # in the order they appear in the script
        number = match.group().replace(",", "").rstrip(".")
        if "." not in number and number.isdigit() and int(number) <= 10:
            continue  # a bare small whole number, such as a list number
        if number not in allowed and number not in unsupported:
            unsupported.append(number)
    return unsupported
