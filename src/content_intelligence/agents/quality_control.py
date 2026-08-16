"""AGENTE 6 - QUALITY CONTROL AGENT (gate final).

Rejeita por padrao. Qualquer item falho no checklist volta para revisao, com o
ponto exato da falha -- nunca "reescreva tudo".
"""

from __future__ import annotations

from .base import EVIDENCE_LEVEL, Agent, obj, score_0_10

_CHECK = obj(
    {
        "passed": {"type": "boolean"},
        "detail": {"type": "string", "description": "Exact failure point when passed=false."},
    }
)

SCHEMA = obj(
    {
        "content": obj(
            {
                "hook_is_specific": _CHECK,
                "has_concrete_data": _CHECK,
                "no_niche_cliches": _CHECK,
                "payoff_matches_promise": _CHECK,
                "no_invented_facts": _CHECK,
            }
        ),
        "video": obj(
            {
                "audio_clean": _CHECK,
                "captions_synced": _CHECK,
                "structure_differs_from_last_3": _CHECK,
                "voice_has_rhythm_variation": _CHECK,
                "cut_pace_2_to_4s": _CHECK,
            }
        ),
        "platform": obj(
            {
                "format_and_duration_ok": _CHECK,
                "caption_and_hashtags_specific": _CHECK,
                "policy_compliant": _CHECK,
            }
        ),
        "business": obj(
            {
                "no_unqualified_advice": _CHECK,
                "cost_justified": _CHECK,
            }
        ),
        "originality_score": score_0_10("Perceived originality, 1-10."),
        "verdict": {"type": "string", "enum": ["APROVADO", "REJEITADO"]},
        "blocking_failures": {
            "type": "array",
            "items": {"type": "string"},
            "description": "One line per failed check, naming the exact fix needed.",
        },
        "evidence_level": EVIDENCE_LEVEL,
    }
)

_GROUPS = ("content", "video", "platform", "business")


def failed_checks(result: dict) -> list[str]:
    """Lista `grupo.check` de tudo que reprovou."""
    out: list[str] = []
    for group in _GROUPS:
        for name, check in (result.get(group) or {}).items():
            if isinstance(check, dict) and not check.get("passed", False):
                detail = check.get("detail") or "sem detalhe"
                out.append(f"{group}.{name}: {detail}")
    return out


def _validate(result: dict) -> list[str]:
    problems: list[str] = []
    failures = failed_checks(result)
    # O checklist e de rejeicao automatica: qualquer falha = REJEITADO.
    if result.get("verdict") == "APROVADO" and failures:
        problems.append(f"APROVADO com {len(failures)} check(s) reprovados")
    if result.get("verdict") == "REJEITADO" and not (
        failures or result.get("blocking_failures")
    ):
        problems.append("REJEITADO sem apontar o ponto exato de falha")
    return problems


QUALITY_CONTROL = Agent(
    name="quality_control",
    number=6,
    prompt_file="06_quality_control.md",
    schema=SCHEMA,
    validate=_validate,
)
