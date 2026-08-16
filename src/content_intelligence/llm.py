"""Camada de acesso ao modelo (Anthropic Messages API).

Todos os agentes falam com o modelo por aqui. Duas implementacoes:

- `AnthropicLLM`: chamada real, com structured outputs (`output_config.format`)
  para que a saida ja venha como JSON valido contra o schema do agente.
- `DryRunLLM`: gera um objeto minimo que satisfaz o schema, sem rede. Serve
  para testes, CI e para rodar o pipeline inteiro sem gastar credito.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from .config import DEFAULT_EFFORT, DEFAULT_MODEL

# Acima disso o SDK exige streaming para nao estourar o timeout HTTP.
STREAMING_THRESHOLD = 16000


class LLMError(RuntimeError):
    """Falha ao obter uma resposta utilizavel do modelo."""


@dataclass
class LLMConfig:
    model: str = DEFAULT_MODEL
    effort: str = DEFAULT_EFFORT
    max_tokens: int = 16000
    # "summarized" mostra um resumo do raciocinio; "omitted" e o padrao da API.
    thinking_display: str = "omitted"


class LLM(Protocol):
    """Contrato que os agentes usam."""

    def json(
        self, system: str, user: str, schema: dict[str, Any], *, label: str = ""
    ) -> dict[str, Any]:
        ...


class AnthropicLLM:
    """Cliente real. Structured outputs garantem JSON valido contra o schema."""

    def __init__(self, config: LLMConfig | None = None, client: Any | None = None) -> None:
        self.config = config or LLMConfig()
        if client is not None:
            self.client = client
        else:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - depende do ambiente
                raise LLMError(
                    "pacote 'anthropic' nao instalado. Rode: pip install anthropic "
                    "(ou use --dry-run)"
                ) from exc
            # Sem argumentos: o SDK resolve ANTHROPIC_API_KEY ou o perfil ativo.
            self.client = anthropic.Anthropic()

    def json(
        self, system: str, user: str, schema: dict[str, Any], *, label: str = ""
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            # Adaptive: o modelo decide quanto pensar por requisicao.
            "thinking": {"type": "adaptive", "display": self.config.thinking_display},
            "output_config": {
                "effort": self.config.effort,
                "format": {"type": "json_schema", "schema": schema},
            },
            # O prompt de sistema e estavel entre chamadas do mesmo agente:
            # cacheado, cada rodada subsequente le em vez de reprocessar.
            "system": [
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ],
            "messages": [{"role": "user", "content": user}],
        }

        message = self._create(params)

        if getattr(message, "stop_reason", None) == "refusal":
            details = getattr(message, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise LLMError(f"[{label or 'llm'}] requisicao recusada (categoria={category})")

        text = self._first_text(message)
        if not text:
            raise LLMError(f"[{label or 'llm'}] resposta sem bloco de texto")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"[{label or 'llm'}] resposta nao e JSON valido: {exc}") from exc

    def _create(self, params: dict[str, Any]) -> Any:
        # Requisicoes longas precisam de streaming; o SDK ja faz retry de
        # 429/5xx/timeout sozinho (max_retries=2 por padrao).
        if params["max_tokens"] > STREAMING_THRESHOLD:
            with self.client.messages.stream(**params) as stream:
                return stream.get_final_message()
        return self.client.messages.create(**params)

    @staticmethod
    def _first_text(message: Any) -> str:
        for block in getattr(message, "content", []) or []:
            if getattr(block, "type", None) == "text":
                return getattr(block, "text", "")
        return ""


class DryRunLLM:
    """Gera um objeto minimo valido para o schema, sem chamar a API.

    Nao substitui o modelo: os valores sao placeholders explicitos. Serve para
    exercitar o encanamento (gates, scoring, persistencia, relatorios) sem rede.
    """

    def __init__(self, overrides: dict[str, Any] | None = None) -> None:
        # Um override pode ser um dict fixo ou um callable(user_context) -> dict,
        # para variar a resposta por canal.
        self.overrides = overrides or {}
        self.calls: list[dict[str, Any]] = []

    def json(
        self, system: str, user: str, schema: dict[str, Any], *, label: str = ""
    ) -> dict[str, Any]:
        self.calls.append({"label": label, "system": system, "user": user})
        if label in self.overrides:
            override = self.overrides[label]
            value = override(user) if callable(override) else override
            return json.loads(json.dumps(value))
        return _stub_from_schema(schema)


def _stub_from_schema(schema: dict[str, Any]) -> Any:
    """Constroi o menor valor que satisfaz um schema JSON."""
    if "enum" in schema:
        return schema["enum"][0]
    if "const" in schema:
        return schema["const"]

    kind = schema.get("type", "object")
    if kind == "object":
        props: dict[str, Any] = schema.get("properties", {})
        required = schema.get("required", list(props))
        return {name: _stub_from_schema(props[name]) for name in required if name in props}
    if kind == "array":
        item_schema = schema.get("items", {"type": "string"})
        count = max(int(schema.get("minItems", 1)), 1)
        return [_stub_from_schema(item_schema) for _ in range(count)]
    if kind == "integer":
        return int(schema.get("minimum", 5))
    if kind == "number":
        return float(schema.get("minimum", 5.0))
    if kind == "boolean":
        return True
    if kind == "null":
        return None
    return schema.get("description", "DRY_RUN")[:80] or "DRY_RUN"


def build_llm(
    *, dry_run: bool, model: str, effort: str, max_tokens: int, overrides: dict | None = None
) -> LLM:
    if dry_run:
        if overrides is None:
            from .demo_data import demo_overrides

            overrides = demo_overrides()
        return DryRunLLM(overrides=overrides)
    return AnthropicLLM(LLMConfig(model=model, effort=effort, max_tokens=max_tokens))
