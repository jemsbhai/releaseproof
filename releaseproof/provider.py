"""A bounded Nebius chat call and an explicitly synthetic deterministic fixture."""
from __future__ import annotations

import json
import os
import http.client
import urllib.error
import urllib.request

MODEL_CATALOG = [
    {"id": "nvidia/Nemotron-3_5-Lightning", "label": "Nemotron 3.5 Lightning", "input_per_million": 0.06, "output_per_million": 0.24},
    {"id": "nvidia/nemotron-3-super-120b-a12b", "label": "Nemotron 3 Super", "input_per_million": 0.30, "output_per_million": 0.90},
    {"id": "nvidia/Nemotron-3-Ultra-550b-a55b", "label": "Nemotron 3 Ultra", "input_per_million": 1.0, "output_per_million": 3.0},
]
MODEL_BY_ID = {m["id"]: m for m in MODEL_CATALOG}
PROVIDER_URL = "https://api.tokenfactory.nebius.com/v1/chat/completions"
MAX_RESPONSE_BYTES = 65_536
MAX_COMPLETION_BYTES = 8_192
GENERATION_SETTINGS = {"temperature": 0, "response_format": {"type": "json_object"},
                       "chat_template_kwargs": {"enable_thinking": False}}


class ProviderFailure(RuntimeError):
    """Sanitized error, with conservative accounting after an uncertain dispatch."""


def fixture(issue: dict, *, injected_drift: bool = False) -> dict:
    """Keyword fixture, independent of expected labels; not an AI quality measurement."""
    title, body = issue["title"].lower(), issue["body"].lower()
    text = title + " " + body
    security = ("vulnerability", "credential", "leak", "exposed", "unauthorized", "bypass",
                "sql injection", "xss", "api key", "secret", "cross-tenant", "malicious", "ignore previous",
                "access token", "token theft", "session hijack", "security")
    feature = ("feature request", "please add", "would like", "request support", "enhancement", "dark mode", "could you add")
    question = ("how do", "how can", "where can", "is it possible", "documentation", "question", "what is")
    ambiguous = "not enough evidence" in body or "request clarification" in body
    injection = any(word in body for word in ("forged", "system override", "untrusted instruction"))
    if title.startswith(("how do", "where do", "how can", "where can")) or ambiguous:
        label, route = "question", "support"
    elif any(word in title for word in security) or any(word in text for word in ("skip its authorization", "without signing in", "session token in its response")):
        label, route = "security", "security"
    elif any(word in text for word in feature):
        label, route = "feature", "product"
    elif any(word in text for word in question):
        label, route = "question", "support"
    else:
        label, route = "bug", "engineering"
    if injected_drift:
        label, route = "question", "support"
    needs_review = label == "security" or injection or ambiguous
    draft = ("Thank you for the report. A security maintainer must review this privately before any response."
             if needs_review else "Thank you for the report. We have prepared a draft for the responsible team to review.")
    return {"label": label, "route": route, "draft": draft, "needs_review": needs_review}


def live(request: dict) -> dict:
    key = os.environ.get("NEBIUS_API_KEY") or os.environ.get("NEBIUS_TOKEN_FACTORY_API_KEY")
    if not key:
        raise ProviderFailure("Nebius API key is not configured on the server.")
    body = {"model": request["model"], "messages": request["messages"],
            **GENERATION_SETTINGS, "max_tokens": request["max_tokens"]}
    req = urllib.request.Request(PROVIDER_URL, data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=55) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ProviderFailure("Provider response exceeded the 64 KiB evidence limit; reservation is retained conservatively.")
        data = json.loads(raw)
    except urllib.error.HTTPError as exc:
        raise ProviderFailure(f"Nebius returned HTTP {exc.code}. No automatic retry was made.") from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, http.client.HTTPException):
        raise ProviderFailure("Nebius request failed or timed out. No automatic retry was made; reserved cost is retained conservatively.") from None
    if not isinstance(data, dict):
        raise ProviderFailure("Nebius returned an invalid response object; reserved cost is retained conservatively.")
    choices = data.get("choices", [])
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ProviderFailure("Nebius returned no completion; reserved cost is retained conservatively.")
    choice = choices[0]
    usage = data.get("usage", {})
    if not isinstance(usage, dict):
        raise ProviderFailure("Nebius returned incomplete usage; reserved cost is retained conservatively.")
    prompt_tokens, completion_tokens = usage.get("prompt_tokens"), usage.get("completion_tokens")
    if any(isinstance(n, bool) or not isinstance(n, int) or n < 0 for n in (prompt_tokens, completion_tokens)):
        raise ProviderFailure("Nebius returned incomplete usage; reserved cost is retained conservatively.")
    message = choice.get("message")
    if not isinstance(message, dict):
        raise ProviderFailure("Nebius returned an invalid completion; reserved cost is retained conservatively.")
    content = message.get("content") or ""
    if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_COMPLETION_BYTES:
        raise ProviderFailure("Completion exceeded the 8 KiB evidence limit; reservation is retained conservatively.")
    return {"text": content,
            "finish_reason": choice.get("finish_reason"),
            "usage": {"input_tokens": prompt_tokens, "output_tokens": completion_tokens},
            "provider_request_id": data.get("id"), "model": data.get("model", request["model"])}
