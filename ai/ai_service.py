from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


SYSTEM_PROMPT = (
    "You are Jarvis, a helpful desktop assistant. Answer clearly and concisely in "
    "the user's language, using Hindi or Hinglish when appropriate. "
    "Never claim you performed an action on the computer; app launching and web "
    "search are handled separately by the application."
)


def ask_ai(user_text: str, history: list[dict[str, str]]) -> str:
    """Send a chat-completions request to the configured AI provider."""
    api_key = os.getenv("AI_API_KEY", "").strip()
    if not api_key:
        return (
            "AI chat ke liye .env file mein AI_API_KEY set karein. "
            "App launching aur web search bina API key ke kaam karte hain."
        )

    base_url = os.getenv("AI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
    model = os.getenv("AI_MODEL", "gpt-4o-mini").strip()
    if not base_url.startswith(("https://", "http://")) or not model:
        return "AI configuration invalid hai: AI_BASE_URL aur AI_MODEL check karein."

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history[-10:])
    messages.append({"role": "user", "content": user_text})
    payload = json.dumps({"model": model, "messages": messages}).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return f"AI service ne error diya (HTTP {exc.code}). API key/model check karein."
    except (urllib.error.URLError, TimeoutError) as exc:
        return f"AI service se connect nahi hua: {exc}"
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "AI service ka response samajh nahi aaya."

    try:
        answer = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return "AI service ka response samajh nahi aaya."
    if not isinstance(answer, str) or not answer.strip():
        return "AI service ne khaali jawab diya."
    return answer.strip()
