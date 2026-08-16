"""Estruturas de dados que atravessam o pipeline.

Cada objeto carrega, alem do conteudo, o rastro epistemico exigido pela
Camada 0: FATO / HIPOTESE / CORRELACAO / CAUSALIDADE_NAO_COMPROVADA.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Literal

EvidenceLevel = Literal[
    "FATO", "HIPOTESE", "CORRELACAO", "CAUSALIDADE_NAO_COMPROVADA", "DADOS_INSUFICIENTES"
]
TrendStage = Literal["EMERGENTE", "EM_ACELERACAO", "SATURADA", "EM_DECLINIO", "EVERGREEN"]
PortfolioBucket = Literal["CORE", "EXPERIMENTAL", "OPPORTUNITY"]


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Niche:
    name: str
    channel: str
    dimensions: dict[str, float]
    score: float = 0.0
    evidence_level: EvidenceLevel = "HIPOTESE"
    rationale: str = ""
    monetization_notes: str = ""
    id: str = field(default_factory=lambda: new_id("niche"))
    created_at: str = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Opportunity:
    """Angulo de conteudo aprovado pelo Market & Trend Agent."""

    channel: str
    title: str
    angle: str
    evidence: str
    trend_stage: TrendStage
    saturation: float  # 0-10, 10 = totalmente saturado
    suggested_format: str
    audience: str
    niche_name: str
    components: dict[str, float] = field(default_factory=dict)
    content_score: float = 0.0
    decision: str = "DESCARTAR"
    bucket: PortfolioBucket = "EXPERIMENTAL"
    evidence_level: EvidenceLevel = "HIPOTESE"
    id: str = field(default_factory=lambda: new_id("opp"))
    created_at: str = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Hook:
    text: str
    hook_type: str  # Curiosity | Contrarian | Problem | Data | Unexpected | Question
    retention_potential: float  # 0-10
    rationale: str = ""


@dataclass
class Script:
    opportunity_id: str
    channel: str
    concept: dict[str, str]  # hook/promise/curiosity_gap/body/payoff/cta
    hooks: list[Hook]
    selected_hook: str
    sections: list[dict[str, Any]]  # [{label, start_s, end_s, text, on_screen}]
    sources: list[str]
    tone: str
    duration_s: int
    id: str = field(default_factory=lambda: new_id("script"))
    created_at: str = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["hooks"] = [asdict(h) if not isinstance(h, dict) else h for h in self.hooks]
        return d


@dataclass
class ShotList:
    script_id: str
    shots: list[dict[str, Any]]  # [{t_start, t_end, visual_type, on_screen, transition}]
    broll_queries: list[str]
    music: dict[str, Any]
    export: dict[str, Any]
    brand: dict[str, Any]
    id: str = field(default_factory=lambda: new_id("shots"))
    created_at: str = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GateResult:
    agent: str
    passed: bool
    scores: dict[str, float]
    blocking_issues: list[str]
    optional_notes: list[str]
    evidence_level: EvidenceLevel = "HIPOTESE"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Video:
    """Um video aprovado, agendado ou publicado."""

    channel: str
    script_id: str
    opportunity_id: str
    title: str
    hook_type: str
    format: str
    bucket: PortfolioBucket
    duration_s: int
    status: str = "APROVADO"  # APROVADO | AGENDADO | PUBLICADO | REJEITADO
    scheduled_for: str | None = None
    published_at: str | None = None
    production_cost_usd: float = 0.0
    experiment_id: str | None = None
    variant: str | None = None  # control | test
    id: str = field(default_factory=lambda: new_id("vid"))
    created_at: str = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Metrics:
    """Snapshot de performance em uma janela (24h / 72h / 7d / 30d)."""

    video_id: str
    window: str
    views: int = 0
    watch_time_s: float = 0.0
    avg_retention_pct: float = 0.0
    completion_pct: float = 0.0
    shares: int = 0
    comments: int = 0
    saves: int = 0
    followers_gained: int = 0
    revenue_usd: float = 0.0
    cost_usd: float = 0.0
    collected_at: str = field(default_factory=utcnow)

    @property
    def roi(self) -> float | None:
        if self.cost_usd <= 0:
            return None
        return (self.revenue_usd - self.cost_usd) / self.cost_usd

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["roi"] = self.roi
        return d


@dataclass
class Experiment:
    """Hipotese testavel no formato do Agente 2."""

    hypothesis: str
    test: str
    variable: str
    metric: str
    channel: str
    min_samples_per_group: int = 5
    status: str = "ABERTO"  # ABERTO | RODANDO | CONCLUIDO | ABORTADO
    result: str = ""
    evidence_level: EvidenceLevel = "HIPOTESE"
    id: str = field(default_factory=lambda: new_id("exp"))
    created_at: str = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Learning:
    topic: str
    statement: str
    evidence_level: EvidenceLevel
    supporting_video_ids: list[str] = field(default_factory=list)
    experiment_id: str | None = None
    id: str = field(default_factory=lambda: new_id("learn"))
    created_at: str = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class KillDecision:
    """Saida do SISTEMA DE MORTE."""

    dimension: str  # niche | format | hook | slot | style
    value: str
    verdict: str  # MATAR | MANTER | ESCALAR | DADOS_INSUFICIENTES
    samples: int
    observed: float
    baseline: float
    rationale: str
    evidence_level: EvidenceLevel
    id: str = field(default_factory=lambda: new_id("kill"))
    created_at: str = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
