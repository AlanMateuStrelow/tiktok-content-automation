"""AGENTE 7 - PUBLISHING & SCHEDULING AGENT.

A parte mecanica (janela, fila, buffer, deteccao de similaridade) e codigo
deterministico em `scheduler.py`. O que sobra para o modelo e a caption e as
hashtags -- que o Agente 6 depois checa por especificidade.
"""

from __future__ import annotations

from .base import EVIDENCE_LEVEL, Agent, obj

SCHEMA = obj(
    {
        "caption": {
            "type": "string",
            "maxLength": 300,
            "description": "Specific to this video's claim. Not a restatement of the hook.",
        },
        "hashtags": {
            "type": "array",
            "minItems": 3,
            "maxItems": 8,
            "items": {"type": "string"},
            "description": "Content-specific. Never #fyp/#viral/#foryou.",
        },
        "pinned_comment": {
            "type": "string",
            "description": "Source link or follow-up question. Empty string if not useful.",
        },
        "evidence_level": EVIDENCE_LEVEL,
    }
)

BANNED_HASHTAGS = {
    "fyp",
    "foryou",
    "foryoupage",
    "viral",
    "viralvideo",
    "trending",
    "explore",
    "tiktok",
}


def _validate(result: dict) -> list[str]:
    problems: list[str] = []
    for tag in result.get("hashtags", []):
        if tag.lstrip("#").lower() in BANNED_HASHTAGS:
            problems.append(f"hashtag generica sem criterio: {tag}")
    caption = result.get("caption", "")
    if len(caption.strip()) < 20:
        problems.append("caption curta demais para dizer algo especifico")
    return problems


PUBLISHING = Agent(
    name="publishing",
    number=7,
    prompt_file="07_publishing.md",
    schema=SCHEMA,
    validate=_validate,
)
