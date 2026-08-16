"""AGENTE 4 - SCRIPT ARCHITECT (conceito + hooks + roteiro).

Funde Content Strategist, Hook Engineer e Script Writer. Escreve em ingles
para EUA/CA/UK/AU.
"""

from __future__ import annotations

import re

from .base import EVIDENCE_LEVEL, Agent, obj, score_0_10

HOOK_TYPES = ["Curiosity", "Contrarian", "Problem", "Data", "Unexpected", "Question"]

SCHEMA = obj(
    {
        "concept": obj(
            {
                "hook": {"type": "string", "description": "Reason to keep watching, seconds 0-2."},
                "promise": {"type": "string", "description": "What the viewer walks away with."},
                "curiosity_gap": {"type": "string"},
                "body": {"type": "string", "description": "How value builds, in one paragraph."},
                "payoff": {"type": "string", "description": "How the promise is kept."},
                "cta": {"type": "string", "description": "Empty string when a CTA would be filler."},
            }
        ),
        "hooks": {
            "type": "array",
            "minItems": 4,
            "description": "At least 4 distinct hook variations, ranked.",
            "items": obj(
                {
                    "text": {"type": "string"},
                    "hook_type": {"type": "string", "enum": HOOK_TYPES},
                    "retention_potential": score_0_10("Predicted holding power."),
                    "rationale": {"type": "string"},
                }
            ),
        },
        "selected_hook": {"type": "string", "description": "Must equal one of hooks[].text."},
        "sections": {
            "type": "array",
            "minItems": 4,
            "items": obj(
                {
                    "label": {
                        "type": "string",
                        "enum": ["HOOK", "CONTEXTO", "DESENVOLVIMENTO", "FECHO"],
                    },
                    "start_s": {"type": "number", "minimum": 0},
                    "end_s": {"type": "number", "minimum": 0},
                    "text": {"type": "string", "description": "Narration, verbatim."},
                    "on_screen": {"type": "string", "description": "Text overlay for this beat."},
                }
            ),
        },
        "sources": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string"},
            "description": "Citable source for every number used. No number without a source.",
        },
        "tone": {"type": "string", "description": "Voice direction for narration."},
        "duration_s": {"type": "integer", "minimum": 60, "maximum": 180},
        "structure_signature": {
            "type": "string",
            "description": "Short label of the narrative skeleton, so consecutive videos can differ.",
        },
        "evidence_level": EVIDENCE_LEVEL,
    }
)

# Lista negra da Camada 1 (regras anti-generico obrigatorias).
BANNED_OPENERS = (
    "did you know",
    "here are 5",
    "here's 5",
    "here are five",
    "in this video",
    "let me tell you",
)
BANNED_CLICHES = (
    "money doesn't grow on trees",
    "money does not grow on trees",
    "the sky is the limit",
    "game changer",
    "at the end of the day",
)
NUMBER_RE = re.compile(r"\d")


def _validate(result: dict) -> list[str]:
    problems: list[str] = []

    hooks = result.get("hooks", [])
    texts = {h.get("text", "") for h in hooks}
    if result.get("selected_hook") not in texts:
        problems.append("selected_hook nao esta entre as variacoes geradas")
    if len({h.get("hook_type") for h in hooks}) < 2:
        problems.append("todas as variacoes de hook sao do mesmo tipo")

    hook_text = (result.get("selected_hook") or "").lower().lstrip()
    if any(hook_text.startswith(b) for b in BANNED_OPENERS):
        problems.append(f"hook usa abertura proibida: {hook_text[:40]!r}")

    narration = " ".join(s.get("text", "") for s in result.get("sections", [])).lower()
    for cliche in BANNED_CLICHES:
        if cliche in narration:
            problems.append(f"clichê do nicho na narracao: {cliche!r}")
    if not NUMBER_RE.search(narration):
        problems.append("roteiro sem nenhum dado numerico concreto")
    if not result.get("sources"):
        problems.append("roteiro sem fonte citavel")

    labels = [s.get("label") for s in result.get("sections", [])]
    for required in ("HOOK", "CONTEXTO", "DESENVOLVIMENTO", "FECHO"):
        if required not in labels:
            problems.append(f"secao obrigatoria ausente: {required}")

    sections = result.get("sections", [])
    if sections:
        first = sections[0]
        if first.get("label") == "HOOK" and float(first.get("end_s", 99)) > 2.5:
            problems.append("hook passa de 2s")

    return problems


SCRIPT_ARCHITECT = Agent(
    name="script_architect",
    number=4,
    prompt_file="04_script_architect.md",
    schema=SCHEMA,
    validate=_validate,
)
