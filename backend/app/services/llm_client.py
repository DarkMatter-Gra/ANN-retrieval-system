"""豆包（火山方舟）大模型调用封装。使用 OpenAI 兼容的 chat/completions 接口。"""

import json

import httpx

from app.core.config import settings


class LLMNotConfiguredError(RuntimeError):
    pass


class LLMCallError(RuntimeError):
    pass


def _ensure_configured() -> None:
    if not settings.ark_api_key:
        raise LLMNotConfiguredError("ARK_API_KEY is not set")


def chat(messages: list[dict], temperature: float = 0.3, max_tokens: int = 1024) -> str:
    """发送一次对话请求，返回模型回复的文本内容。"""
    _ensure_configured()

    url = f"{settings.ark_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.ark_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.ark_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        raise LLMCallError(f"LLM HTTP {exc.response.status_code}: {exc.response.text}") from exc
    except httpx.HTTPError as exc:
        raise LLMCallError(f"LLM request failed: {exc}") from exc

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise LLMCallError(f"unexpected LLM response: {json.dumps(data)[:500]}") from exc


def chat_json(messages: list[dict], temperature: float = 0.0) -> dict:
    """要求模型返回 JSON，并解析成 dict。带基础容错。"""
    content = chat(messages, temperature=temperature)
    return _extract_json(content)


def _extract_json(text: str) -> dict:
    text = text.strip()
    # 去掉可能的 ```json ... ``` 包裹
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise LLMCallError(f"cannot parse JSON from LLM output: {text[:300]}")
