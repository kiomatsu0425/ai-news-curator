from __future__ import annotations

import json
from typing import Any

from openai import OpenAI


SYSTEM_PROMPT = """
あなたは個人ニュースキュレーターです。
入力された記事候補を、日本語で読む価値を判断しやすい形に変換してください。
出力はJSONのみ。タグは2〜5個で、粒度を広くしすぎないでください。
""".strip()


def _fallback(title: str, summary: str, source: str) -> dict[str, Any]:
    tags = [source]
    if "AI" in title.upper() or "model" in title.lower():
        tags.append("Models")
    return {
        "jp_title": title,
        "jp_summary": summary[:300] or "要約未生成です。OPENAI_API_KEYを設定して再取得してください。",
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
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "次の記事を日本語タイトル、3行要約、タグにしてください。\n"
                    f"{json.dumps(user_payload, ensure_ascii=False)}"
                ),
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    raw = response.choices[0].message.content or "{}"
    data = json.loads(raw)
    return {
        "jp_title": str(data.get("jp_title") or data.get("title") or article["title"]),
        "jp_summary": str(data.get("jp_summary") or data.get("summary") or ""),
        "tags": [str(tag).strip() for tag in data.get("tags", []) if str(tag).strip()][:5],
    }

