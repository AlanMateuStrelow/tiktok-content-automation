"""AGENTE 3 - LOW-QUALITY DETECTOR (pre-producao).

Avalia o conceito/roteiro planejado, nunca o video pronto (isso e o Agente 6).
Barrar aqui custa um prompt; barrar depois custa a producao inteira.
"""

from __future__ import annotations

from .base import EVIDENCE_LEVEL, Agent, obj, score_0_100

SCHEMA = obj(
    {
        "quality_score": score_0_100("Content quality of the planned script."),
        "retention_risk": score_0_100("Higher = more likely the viewer drops off."),
        "viral_potential": score_0_100("Share/save-driven reach potential."),
        "drop_off_points": {
            "type": "array",
            "items": obj(
                {
                    "at_second": {"type": "number", "minimum": 0},
                    "reason": {"type": "string"},
                    "fix": {"type": "string"},
                }
            ),
            "description": "Predicted abandonment points, from the script structure.",
        },
        "issues": {
            "type": "array",
            "items": obj(
                {
                    "category": {
                        "type": "string",
                        "enum": [
                            "weak_hook",
                            "long_intro",
                            "generic_information",
                            "no_novelty",
                            "no_payoff",
                            "broken_promise",
                            "no_tension",
                        ],
                    },
                    "detail": {"type": "string"},
                    "blocking": {"type": "boolean"},
                }
            ),
        },
        "verdict": {"type": "string", "enum": ["AVANCAR", "REESCREVER"]},
        "evidence_level": EVIDENCE_LEVEL,
    }
)


def _validate(result: dict) -> list[str]:
    problems: list[str] = []
    blocking = [i for i in result.get("issues", []) if i.get("blocking")]
    if result.get("verdict") == "AVANCAR" and blocking:
        problems.append("verdito AVANCAR com problema bloqueante listado")
    if result.get("verdict") == "REESCREVER" and not result.get("issues"):
        problems.append("verdito REESCREVER sem apontar o problema exato")
    return problems


LOW_QUALITY_DETECTOR = Agent(
    name="low_quality_detector",
    number=3,
    prompt_file="03_low_quality_detector.md",
    schema=SCHEMA,
    validate=_validate,
)
