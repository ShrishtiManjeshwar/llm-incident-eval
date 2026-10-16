"""Ask Gemini to write a brief from the incident log. Standard library only."""

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PROMPT = """You are an on-call engineer. Read the incident log below and write a brief.

Return only a JSON object with exactly these fields:
- "cause": one or two sentences naming the most likely root cause.
- "evidence": a list of log line IDs (like "L123") that support the cause. Cite only IDs that appear in the log.
- "next_action": the one thing to do now.
- "detection": one check or alert that would have caught this before a customer did.

Do not invent log lines. Do not cite a line you did not read.

INCIDENT LOG
{incident}
"""


class AgentError(Exception):
    pass


def load_env():
    """Read KEY=value lines from .env without printing or logging them."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def write_brief(incident_text, temperature=0.7, retries=3):
    load_env()
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise AgentError("GEMINI_API_KEY is empty. Paste your key after the = in the .env file.")
    model = os.environ.get("GEMINI_MODEL", "gemini-flash-latest").strip()

    body = json.dumps(
        {
            "contents": [{"role": "user", "parts": [{"text": PROMPT.format(incident=incident_text)}]}],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
            },
        }
    ).encode()
    url = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent".format(model)
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )

    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = json.loads(response.read().decode())
            break
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503) and attempt < retries - 1:
                time.sleep(15 * (attempt + 1))
                continue
            detail = exc.read().decode(errors="replace")[:300]
            raise AgentError("Gemini returned HTTP {}: {}".format(exc.code, detail)) from exc
        except urllib.error.URLError as exc:
            raise AgentError("could not reach Gemini: {}".format(exc)) from exc

    try:
        parts = payload["candidates"][0]["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts)
    except (KeyError, IndexError) as exc:
        raise AgentError("unexpected Gemini response: {}".format(str(payload)[:300])) from exc

    usage = payload.get("usageMetadata", {})
    return {
        "model": model,
        "text": text,
        "prompt_tokens": usage.get("promptTokenCount", 0),
        "output_tokens": usage.get("candidatesTokenCount", 0),
    }


def parse_brief(text):
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None
