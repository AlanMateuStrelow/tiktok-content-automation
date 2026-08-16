"""Infraestrutura comum dos 8 agentes.

Cada agente = prompt (arquivo .md) + schema JSON de saida + validacao. O prompt
descreve o julgamento; o schema garante que a saida seja consumivel por codigo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from ..llm import LLM, LLMError

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# Preambulo da Camada 0 injetado em todo agente. Escrito em ingles porque os
# agentes produzem conteudo para o mercado EUA/CA/UK/AU.
LAYER_ZERO = """\
# OPERATING PRINCIPLES (apply to every response)

Decision hierarchy:
- With enough data: DATA > OPINION
- Without data: HYPOTHESIS > GUESSWORK
- With a hypothesis: TEST > DEBATE
- When a test fails: LEARNING > FRUSTRATION
- When a format works: SCALE WITH VARIATIONS, never blind-copy

Epistemic labelling is mandatory. Every claim you make is one of:
FATO (verifiable now), HIPOTESE (untested), CORRELACAO (co-occurrence, no
proven cause), CAUSALIDADE_NAO_COMPROVADA (causal story without proof),
DADOS_INSUFICIENTES (not enough evidence to judge). Never present a hypothesis
as a fact. If you do not know, say DADOS_INSUFICIENTES.

Anti-generic rule. Recommendations like "make quality content", "know your
audience", or "use good hooks" are rejected outright. Every recommendation
answers: WHAT? WHY? HOW? WHEN? WHICH METRIC? WHICH HYPOTHESIS? WHAT COST?
WHAT EXPECTED RESULT?

Compliance is non-negotiable. Respect platform policy, copyright, and music or
image licensing. Never buy views or followers, fake engagement, or evade
moderation. The edge comes from intelligence, speed, testing, quality, and data.

Optimize for REVENUE/HOUR, REVENUE/COST, REVENUE/VIDEO and ROI -- not views.

Output contract: reply with JSON matching the provided schema. No prose outside
the JSON.
"""


class AgentError(RuntimeError):
    """Saida do agente violou o contrato esperado."""


@lru_cache(maxsize=None)
def load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise AgentError(f"prompt nao encontrado: {path}")
    return path.read_text(encoding="utf-8")


def obj(
    properties: dict[str, Any], required: list[str] | None = None
) -> dict[str, Any]:
    """Objeto de schema com as restricoes que structured outputs exige."""
    return {
        "type": "object",
        "properties": properties,
        "required": required if required is not None else list(properties),
        "additionalProperties": False,
    }


def score_0_10(description: str) -> dict[str, Any]:
    return {"type": "number", "minimum": 0, "maximum": 10, "description": description}


def score_0_100(description: str) -> dict[str, Any]:
    return {"type": "integer", "minimum": 0, "maximum": 100, "description": description}


EVIDENCE_LEVEL = {
    "type": "string",
    "enum": [
        "FATO",
        "HIPOTESE",
        "CORRELACAO",
        "CAUSALIDADE_NAO_COMPROVADA",
        "DADOS_INSUFICIENTES",
    ],
    "description": "Epistemic status of this output.",
}


@dataclass
class Agent:
    """Um agente especializado: prompt + schema + validacao opcional."""

    name: str
    number: int
    prompt_file: str
    schema: dict[str, Any]
    validate: Callable[[dict[str, Any]], list[str]] | None = field(default=None)

    def system_prompt(self) -> str:
        return f"{LAYER_ZERO}\n---\n\n{load_prompt(self.prompt_file)}"

    def run(self, llm: LLM, context: dict[str, Any]) -> dict[str, Any]:
        user = render_context(context)
        result = llm.json(self.system_prompt(), user, self.schema, label=self.name)
        problems = self.validate(result) if self.validate else []
        if problems:
            raise AgentError(f"[{self.name}] saida invalida: {'; '.join(problems)}")
        return result


def render_context(context: dict[str, Any]) -> str:
    """Serializa o contexto de entrada de forma estavel (bom para cache)."""
    parts: list[str] = []
    for key in sorted(context):
        value = context[key]
        if isinstance(value, str):
            parts.append(f"## {key}\n{value}")
        else:
            parts.append(
                f"## {key}\n```json\n{json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)}\n```"
            )
    return "\n\n".join(parts) if parts else "(sem contexto adicional)"


__all__ = [
    "Agent",
    "AgentError",
    "EVIDENCE_LEVEL",
    "LAYER_ZERO",
    "LLMError",
    "load_prompt",
    "obj",
    "render_context",
    "score_0_10",
    "score_0_100",
]
