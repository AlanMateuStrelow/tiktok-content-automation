"""Configuracao central do sistema.

Todos os pesos, limiares e regras operacionais vivem aqui. Nada de numero
magico espalhado pelo codigo -- se um limiar muda por causa de dado real,
muda em um lugar so e o historico de commits mostra por que.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

DEFAULT_MODEL = "claude-opus-5"
DEFAULT_EFFORT = "high"

# ---------------------------------------------------------------------------
# NICHE SCORE (Camada 1, Agente 1) - 8 dimensoes, 0-10 cada.
# ---------------------------------------------------------------------------
NICHE_DIMENSIONS: tuple[str, ...] = (
    "demand",
    "growth",
    "monetization",
    "competition",  # invertida: 10 = pouca concorrencia
    "production_ease",
    "viral_potential",
    "long_term_potential",
    "expansion_potential",
)

DEFAULT_NICHE_WEIGHTS: dict[str, float] = {
    "demand": 1.5,
    "growth": 1.25,
    "monetization": 1.75,  # viralidade != rentabilidade: monetizacao pesa mais
    "competition": 1.0,
    "production_ease": 0.75,
    "viral_potential": 1.0,
    "long_term_potential": 1.25,
    "expansion_potential": 0.5,
}

# ---------------------------------------------------------------------------
# CONTENT SCORE (Camada 2)
# ---------------------------------------------------------------------------
CONTENT_POSITIVE_COMPONENTS: tuple[str, ...] = (
    "demand",
    "trend",
    "hook",
    "retention",
    "production",
    "monetization",
    "quality",
)
CONTENT_NEGATIVE_COMPONENTS: tuple[str, ...] = ("competition", "risk")

DEFAULT_CONTENT_WEIGHTS: dict[str, float] = {
    "demand": 1.0,
    "trend": 1.0,
    "hook": 1.5,
    "retention": 1.5,
    "production": 0.75,
    "monetization": 1.5,
    "quality": 1.25,
    "competition": 1.0,
    "risk": 1.25,
}

# Faixas de decisao do CONTENT SCORE (limite inferior inclusivo).
DECISION_BANDS: tuple[tuple[int, str], ...] = (
    (90, "PRIORIDADE_MAXIMA"),
    (80, "PRODUZIR"),
    (70, "TESTAR"),
    (60, "BANCO_DE_IDEIAS"),
    (0, "DESCARTAR"),
)

# Distribuicao alvo de portfolio (Camada 2).
PORTFOLIO_TARGET: dict[str, float] = {
    "CORE": 0.60,
    "EXPERIMENTAL": 0.25,
    "OPPORTUNITY": 0.15,
}


@dataclass
class Gates:
    """Limiares que interrompem a producao (Camada 1, Agentes 3, 2 e 6)."""

    # Agente 3 - Low-Quality Detector (pre-producao)
    min_quality_score: int = 70
    max_retention_risk: int = 60
    # Agente 2 - Algorithm Research (auditoria pre-producao)
    min_distribution_potential: int = 5  # escala 1-10
    max_shadowban_risk: str = "medio"  # baixo | medio | alto
    # Agente 6 - Quality Control (gate final)
    min_originality: int = 6  # escala 1-10
    # Numero de vezes que um roteiro reprovado volta ao Script Architect
    max_rewrite_attempts: int = 2


@dataclass
class PublishingRules:
    """Regras operacionais do Agente 7."""

    min_buffer_per_channel: int = 3
    target_buffer_per_channel: int = 5
    # Janelas por nicho, no fuso do publico-alvo (America/New_York).
    windows: dict[str, list[str]] = field(
        default_factory=lambda: {
            "finance": ["07:30", "12:15"],
            "tech_ai": ["18:45", "21:30"],
        }
    )
    audience_timezone: str = "America/New_York"
    # Nao publicar dois videos do mesmo tema/formato em sequencia.
    similarity_lookback: int = 2


@dataclass
class DeathSystem:
    """Regras do SISTEMA DE MORTE (Agentes 0 e 8).

    Nunca matar nada sem amostra minima -- sem dado suficiente o veredito e
    DADOS_INSUFICIENTES, nao um palpite disfarcado de decisao.
    """

    min_samples: int = 5
    # Fracao da baseline abaixo da qual o item e candidato a morte.
    kill_ratio: float = 0.7
    # Fracao da baseline acima da qual o item e candidato a escala.
    scale_ratio: float = 1.3
    lookback_days: int = 30


def load_env_file(path: str | Path = ".env") -> list[str]:
    """Le um `.env` simples (CHAVE=valor) para o ambiente do processo.

    O `.env.example` promete isso e nada no codigo lia o arquivo: quem seguia
    o README preenchia a chave e continuava sem ela. Sem dependencia nova --
    o formato que o projeto usa cabe em um parser de dez linhas.

    Variavel ja definida no ambiente **vence** o arquivo: exportar a chave na
    sessao e a forma de sobrescrever o `.env` sem edita-lo.
    """
    p = Path(path)
    if not p.exists():
        return []

    carregadas: list[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.removeprefix("export ").partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        if not key or not value or key in os.environ:
            continue
        os.environ[key] = value
        carregadas.append(key)
    return carregadas


@dataclass
class Settings:
    model: str = DEFAULT_MODEL
    effort: str = DEFAULT_EFFORT
    max_tokens: int = 16000
    db_path: str = "data/knowledge_base.db"
    output_dir: str = "out"
    channels: tuple[str, ...] = ("finance", "tech_ai")
    markets: tuple[str, ...] = ("US", "CA", "UK", "AU")
    niche_weights: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_NICHE_WEIGHTS)
    )
    content_weights: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_CONTENT_WEIGHTS)
    )
    gates: Gates = field(default_factory=Gates)
    publishing: PublishingRules = field(default_factory=PublishingRules)
    death: DeathSystem = field(default_factory=DeathSystem)

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Settings":
        """Carrega settings de JSON + variaveis de ambiente (env tem prioridade).

        Le o `.env` da pasta atual antes de olhar o ambiente, para que a chave
        da API e os overrides funcionem como o README descreve.
        """
        load_env_file()
        data: dict = {}
        if path:
            p = Path(path)
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))

        nested = {
            "gates": Gates(**data.pop("gates", {})),
            "publishing": PublishingRules(**data.pop("publishing", {})),
            "death": DeathSystem(**data.pop("death", {})),
        }
        settings = cls(**{**data, **nested})

        if env_model := os.environ.get("CI_MODEL"):
            settings.model = env_model
        if env_effort := os.environ.get("CI_EFFORT"):
            settings.effort = env_effort
        if env_db := os.environ.get("CI_DB_PATH"):
            settings.db_path = env_db
        return settings

    def to_dict(self) -> dict:
        return asdict(self)
