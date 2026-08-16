"""AGENTE 2 - ALGORITHM RESEARCH AGENT.

Duas funcoes: auditar um plano antes da producao (advogado do diabo) e
gerar hipoteses testaveis no formato HIPOTESE -> TESTE -> VARIAVEL -> METRICA.
"""

from __future__ import annotations

from .base import EVIDENCE_LEVEL, Agent, obj, score_0_10

AUDIT_SCHEMA = obj(
    {
        "shadowban_risk": {
            "type": "string",
            "enum": ["baixo", "medio", "alto"],
            "description": "Risk that the platform suppresses distribution.",
        },
        "shadowban_reasons": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Concrete low-originality signals found. Empty if none.",
        },
        "distribution_potential": score_0_10("1-10 likelihood of broad distribution."),
        "duration_assessment": obj(
            {
                "recommended_seconds": {"type": "integer", "minimum": 15, "maximum": 300},
                "reasoning": {"type": "string"},
            }
        ),
        "hook_assessment": obj(
            {
                "specific_enough": {"type": "boolean"},
                "seconds_to_payoff_signal": {"type": "number"},
                "notes": {"type": "string"},
            }
        ),
        "audio_assessment": obj(
            {
                "risk": {"type": "string", "enum": ["baixo", "medio", "alto"]},
                "notes": {"type": "string", "description": "Licensing and mute risk."},
            }
        ),
        "required_changes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Blocking. Production must not start until these are fixed.",
        },
        "optional_changes": {"type": "array", "items": {"type": "string"}},
        "evidence_level": EVIDENCE_LEVEL,
    }
)

HYPOTHESIS_SCHEMA = obj(
    {
        "hypotheses": {
            "type": "array",
            "minItems": 1,
            "items": obj(
                {
                    "hypothesis": {"type": "string", "description": "Falsifiable statement."},
                    "test": {"type": "string", "description": "What to produce, exactly."},
                    "variable": {
                        "type": "string",
                        "description": "The ONE thing that changes between groups.",
                    },
                    "metric": {"type": "string", "description": "What is measured, and how."},
                    "min_samples_per_group": {"type": "integer", "minimum": 3},
                    "channel": {"type": "string", "enum": ["finance", "tech_ai"]},
                    "evidence_level": EVIDENCE_LEVEL,
                }
            ),
        }
    }
)


def _validate_audit(result: dict) -> list[str]:
    problems: list[str] = []
    if result.get("shadowban_risk") == "alto" and not result.get("shadowban_reasons"):
        problems.append("risco alto declarado sem motivo listado")
    if result.get("required_changes") and result.get("distribution_potential", 0) >= 9:
        problems.append("potencial 9+ com mudancas bloqueantes pendentes e contraditorio")
    return problems


ALGORITHM_AUDIT = Agent(
    name="algorithm_audit",
    number=2,
    prompt_file="02_algorithm_research.md",
    schema=AUDIT_SCHEMA,
    validate=_validate_audit,
)

HYPOTHESIS_GENERATOR = Agent(
    name="hypothesis_generator",
    number=2,
    prompt_file="02_algorithm_research.md",
    schema=HYPOTHESIS_SCHEMA,
)
