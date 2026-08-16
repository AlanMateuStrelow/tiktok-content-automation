"""AGENTE 8 - ANALYTICS & LEARNING AGENT.

Le metricas reais + vereditos do sistema de morte (calculados em codigo) e
devolve: o que exatamente venceu, aprendizados rotulados epistemicamente,
variacoes do vencedor e os proximos experimentos.
"""

from __future__ import annotations

from .base import EVIDENCE_LEVEL, Agent, obj

SCHEMA = obj(
    {
        "what_won": obj(
            {
                "dimension": {
                    "type": "string",
                    "enum": [
                        "tema",
                        "hook",
                        "formato",
                        "narrativa",
                        "edicao",
                        "duracao",
                        "timing",
                        "emocao",
                        "intencao_comercial",
                        "indeterminado",
                    ],
                    "description": "Use 'indeterminado' when the data cannot separate causes.",
                },
                "reasoning": {"type": "string"},
                "evidence_level": EVIDENCE_LEVEL,
            }
        ),
        "variations": {
            "type": "array",
            "minItems": 1,
            "maxItems": 5,
            "items": obj(
                {
                    "description": {"type": "string"},
                    "what_changes": {"type": "string", "description": "The single varied element."},
                }
            ),
            "description": "Variations of the winner. Never a blind copy.",
        },
        "learnings": {
            "type": "array",
            "minItems": 1,
            "items": obj(
                {
                    "topic": {"type": "string"},
                    "statement": {"type": "string"},
                    "evidence_level": EVIDENCE_LEVEL,
                    "supporting_video_ids": {"type": "array", "items": {"type": "string"}},
                }
            ),
        },
        "next_experiments": {
            "type": "array",
            "items": obj(
                {
                    "hypothesis": {"type": "string"},
                    "test": {"type": "string"},
                    "variable": {"type": "string"},
                    "metric": {"type": "string"},
                    "channel": {"type": "string", "enum": ["finance", "tech_ai"]},
                }
            ),
        },
        "strategy_updates": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Concrete changes to feed back into agents 1, 2 and 4.",
        },
    }
)


def _validate(result: dict) -> list[str]:
    problems: list[str] = []
    for i, learning in enumerate(result.get("learnings", [])):
        level = learning.get("evidence_level")
        # Um aprendizado so vira FATO com video de suporte identificado.
        if level == "FATO" and not learning.get("supporting_video_ids"):
            problems.append(f"learnings[{i}]: rotulado FATO sem video de suporte")
    won = result.get("what_won", {})
    if won.get("dimension") != "indeterminado" and won.get("evidence_level") == "FATO":
        problems.append(
            "what_won rotulado FATO: atribuicao de causa a partir de performance e CORRELACAO"
        )
    return problems


ANALYTICS_LEARNING = Agent(
    name="analytics_learning",
    number=8,
    prompt_file="08_analytics_learning.md",
    schema=SCHEMA,
    validate=_validate,
)
