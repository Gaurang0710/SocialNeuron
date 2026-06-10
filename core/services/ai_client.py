import requests
from django.conf import settings


def ask_ollama(prompt):
    try:
        url = settings.OLLAMA_URL
        is_chat_endpoint = url.rstrip("/").endswith("/api/chat")
        if not is_chat_endpoint and not url.rstrip("/").endswith("/api/generate"):
            url = url.rstrip("/") + "/api/generate"
        payload = {
            "model": settings.OLLAMA_MODEL,
            "stream": False,
        }
        if is_chat_endpoint:
            payload["messages"] = [{"role": "user", "content": prompt}]
        else:
            payload["prompt"] = prompt

        response = requests.post(
            url,
            json=payload,
            timeout=settings.OLLAMA_TIMEOUT,
        )
        response.raise_for_status()

        data = response.json()
        if is_chat_endpoint:
            return data.get("message", {}).get("content", "").strip()
        return data.get("response", "").strip()
    except requests.RequestException as exc:
        return (
            "Error: Could not connect to local Ollama. "
            f"Make sure Ollama is running and the '{settings.OLLAMA_MODEL}' model is available. "
            f"Details: {exc}"
        )
    except ValueError:
        return "Error: Ollama returned an invalid JSON response."
