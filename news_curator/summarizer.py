from __future__ import annotations

import json
from typing import Any

from openai import APIError, OpenAI, RateLimitError


SYSTEM_PROMPT = """
あなたは個人向けニュースキュレーターです。
入力された記事を、日本語読者が読む価値を判断しやすい形に変換してください。
出力はJSONのみ。タグは2〜5個で、短く具体的なトピック名にしてください。
""".strip()


class SummarizationRateLimited(RuntimeError):
    """Raised when OpenAI rate limits or quota exhaustion should pause API summarization."""


def _fallback(title: str, summary: str, source: str) -> dict[str, Any]:
    tags = [source]
    if "AI" in title.upper() or "model" in title.lower():
        tags.append("Models")
    return {
        "jp_title": title,
        "jp_summary": summary[:300] or "要約はまだ生成されていません。OPENAI_API_KEYを設定して再取得してください。",
        "tags": tags[:5],
    }


def summarize_article(article: dict, api_key: str | None, model: str) -> dict[str, Any]:
    if not api_key:
        return _fallback(article["title"], article.get("summary") or article.get("content", ""), article["source"])

    client = OpenAI(api_key=api_key)
    user_payload = {
        "source": article["source"],
        "title": article["title"],
        "summary": article.get("summary", ""),
        "content": (article.get("content") or "")[:5000],
    }

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "この記事について、日本語タイトル、3行の日本語要約、タグを作成してください。\n"
                        f"{json.dumps(user_payload, ensure_ascii=False)}"
                    ),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
    except RateLimitError as exc:
        raise SummarizationRateLimited("OpenAI rate limit or quota was reached.") from exc
    except APIError:
        return _fallback(article["title"], article.get("summary") or article.get("content", ""), article["source"])

    try:
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
    except (json.JSONDecodeError, IndexError, AttributeError):
        return _fallback(article["title"], article.get("summary") or article.get("content", ""), article["source"])

    return {
        "jp_title": str(data.get("jp_title") or data.get("title") or article["title"]),
        "jp_summary": str(data.get("jp_summary") or data.get("summary") or ""),
        "tags": [str(tag).strip() for tag in data.get("tags", []) if str(tag).strip()][:5],
    }
