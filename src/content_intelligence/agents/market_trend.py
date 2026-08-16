"""AGENTE 1 - MARKET & TREND AGENT.

Parte A (semanal): NICHE SCORE em 8 dimensoes.
Parte B (diaria): 3-5 angulos com potencial nesta semana.
"""

from __future__ import annotations

from ..config import NICHE_DIMENSIONS
from .base import EVIDENCE_LEVEL, Agent, obj, score_0_10

_NICHE_DIMENSIONS_SCHEMA = obj(
    {
        "demand": score_0_10("Search + watch demand today."),
        "growth": score_0_10("Direction and speed of demand over 12 months."),
        "monetization": score_0_10("RPM, affiliate and sponsorship potential."),
        "competition": score_0_10("INVERTED: 10 = almost no credible competitor."),
        "production_ease": score_0_10("How cheaply a good video can be made."),
        "viral_potential": score_0_10("Share/save-driven reach potential."),
        "long_term_potential": score_0_10("Evergreen value beyond this quarter."),
        "expansion_potential": score_0_10("Room for adjacent sub-niches later."),
    }
)
assert set(_NICHE_DIMENSIONS_SCHEMA["properties"]) == set(NICHE_DIMENSIONS)

NICHE_SCHEMA = obj(
    {
        "niches": {
            "type": "array",
            "minItems": 1,
            "items": obj(
                {
                    "name": {"type": "string", "description": "Specific sub-niche, not a category."},
                    "channel": {"type": "string", "enum": ["finance", "tech_ai"]},
                    "dimensions": _NICHE_DIMENSIONS_SCHEMA,
                    "rationale": {
                        "type": "string",
                        "description": "Why these scores. Cite what you observed.",
                    },
                    "monetization_notes": {
                        "type": "string",
                        "description": "Concrete revenue paths: RPM band, affiliate programs, sponsor types.",
                    },
                    "evidence_level": EVIDENCE_LEVEL,
                }
            ),
        }
    }
)

TREND_SCHEMA = obj(
    {
        "opportunities": {
            "type": "array",
            "minItems": 1,
            "items": obj(
                {
                    "title": {"type": "string", "description": "The angle, in one line."},
                    "angle": {
                        "type": "string",
                        "description": "The lateral take nobody is covering. Not '5 tips about X'.",
                    },
                    "evidence": {
                        "type": "string",
                        "description": "What makes you believe this is rising now.",
                    },
                    "trend_stage": {
                        "type": "string",
                        "enum": [
                            "EMERGENTE",
                            "EM_ACELERACAO",
                            "SATURADA",
                            "EM_DECLINIO",
                            "EVERGREEN",
                        ],
                    },
                    "saturation": score_0_10("10 = thousands of near-identical videos exist."),
                    "suggested_format": {"type": "string"},
                    "audience": {
                        "type": "string",
                        "description": "Specific viewer, not 'people interested in money'.",
                    },
                    "niche_name": {"type": "string"},
                    "channel": {"type": "string", "enum": ["finance", "tech_ai"]},
                    "components": obj(
                        {
                            "demand": score_0_10("Audience demand for this angle."),
                            "trend": score_0_10("Momentum right now."),
                            "monetization": score_0_10("Revenue potential of this angle."),
                            "competition": score_0_10("PENALTY: 10 = crowded."),
                            "risk": score_0_10("PENALTY: policy, accuracy or brand risk."),
                        }
                    ),
                    "evidence_level": EVIDENCE_LEVEL,
                }
            ),
        }
    }
)


def _validate_trends(result: dict) -> list[str]:
    problems: list[str] = []
    for i, opp in enumerate(result.get("opportunities", [])):
        title = (opp.get("title") or "").lower()
        # Regra de ouro anti-generico do Agente 1.
        if any(bad in title for bad in ("5 tips", "5 dicas", "top 10 ", "did you know")):
            problems.append(f"opportunity[{i}]: titulo generico ({opp.get('title')!r})")
        if opp.get("saturation", 0) >= 9 and opp.get("trend_stage") != "EVERGREEN":
            problems.append(f"opportunity[{i}]: saturacao {opp['saturation']} sem ser evergreen")
    return problems


MARKET_INTELLIGENCE = Agent(
    name="market_intelligence",
    number=1,
    prompt_file="01_market_trend.md",
    schema=NICHE_SCHEMA,
)

TREND_HUNTER = Agent(
    name="trend_hunter",
    number=1,
    prompt_file="01_market_trend.md",
    schema=TREND_SCHEMA,
    validate=_validate_trends,
)
