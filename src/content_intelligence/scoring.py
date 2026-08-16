"""Motor de pontuacao: NICHE SCORE, CONTENT SCORE, portfolio e sistema de morte.

Tudo aqui e deterministico e testavel. O LLM produz as notas por dimensao;
a aritmetica, as faixas de decisao e os vereditos de morte sao codigo -- assim
duas rodadas com as mesmas notas sempre dao a mesma decisao.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from .config import (
    CONTENT_NEGATIVE_COMPONENTS,
    CONTENT_POSITIVE_COMPONENTS,
    DECISION_BANDS,
    DEFAULT_CONTENT_WEIGHTS,
    DEFAULT_NICHE_WEIGHTS,
    NICHE_DIMENSIONS,
    PORTFOLIO_TARGET,
    DeathSystem,
)

SCALE_MAX = 10.0


class ScoringError(ValueError):
    """Entrada invalida para o motor de pontuacao."""


def _validate(values: dict[str, float], expected: tuple[str, ...], label: str) -> None:
    missing = [k for k in expected if k not in values]
    if missing:
        raise ScoringError(f"{label}: dimensoes ausentes: {', '.join(sorted(missing))}")
    for key in expected:
        v = values[key]
        if not isinstance(v, (int, float)) or not 0 <= v <= SCALE_MAX:
            raise ScoringError(f"{label}: '{key}'={v!r} fora da escala 0-{SCALE_MAX:.0f}")


def niche_score(
    dimensions: dict[str, float], weights: dict[str, float] | None = None
) -> float:
    """NICHE SCORE 0-100 a partir das 8 dimensoes do Agente 1.

    'competition' entra ja invertida (10 = pouca concorrencia), o que mantem a
    soma monotonica: mais alto e sempre melhor.
    """
    weights = weights or DEFAULT_NICHE_WEIGHTS
    _validate(dimensions, NICHE_DIMENSIONS, "NICHE SCORE")
    total_weight = sum(weights[d] for d in NICHE_DIMENSIONS)
    raw = sum(dimensions[d] * weights[d] for d in NICHE_DIMENSIONS)
    return round(raw / (total_weight * SCALE_MAX) * 100, 2)


@dataclass
class ContentScore:
    value: float
    decision: str
    components: dict[str, float]
    penalties: dict[str, float]

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "decision": self.decision,
            "components": self.components,
            "penalties": self.penalties,
        }


def content_score(
    components: dict[str, float], weights: dict[str, float] | None = None
) -> ContentScore:
    """CONTENT SCORE 0-100.

    Formula da Camada 2: positivos somam, competition e risk subtraem. O
    resultado bruto e normalizado pelo intervalo teorico [min, max] para que a
    escala 0-100 signifique sempre a mesma coisa.
    """
    weights = weights or DEFAULT_CONTENT_WEIGHTS
    expected = CONTENT_POSITIVE_COMPONENTS + CONTENT_NEGATIVE_COMPONENTS
    _validate(components, expected, "CONTENT SCORE")

    positive = sum(components[c] * weights[c] for c in CONTENT_POSITIVE_COMPONENTS)
    negative = sum(components[c] * weights[c] for c in CONTENT_NEGATIVE_COMPONENTS)
    raw = positive - negative

    max_raw = sum(weights[c] for c in CONTENT_POSITIVE_COMPONENTS) * SCALE_MAX
    min_raw = -sum(weights[c] for c in CONTENT_NEGATIVE_COMPONENTS) * SCALE_MAX
    value = round((raw - min_raw) / (max_raw - min_raw) * 100, 2)

    return ContentScore(
        value=value,
        decision=decide(value),
        components={c: components[c] for c in CONTENT_POSITIVE_COMPONENTS},
        penalties={c: components[c] for c in CONTENT_NEGATIVE_COMPONENTS},
    )


def decide(score: float) -> str:
    """Traduz o CONTENT SCORE na acao correspondente (Camada 2)."""
    for threshold, label in DECISION_BANDS:
        if score >= threshold:
            return label
    return "DESCARTAR"


def should_produce(score: float) -> bool:
    """Vale gastar producao? Somente TESTAR (>=70) para cima."""
    return decide(score) in {"PRIORIDADE_MAXIMA", "PRODUZIR", "TESTAR"}


def assign_bucket(trend_stage: str, decision: str) -> str:
    """Classifica a oportunidade no portfolio 60/25/15."""
    if trend_stage in {"EMERGENTE", "EM_ACELERACAO"}:
        return "OPPORTUNITY"
    if decision in {"PRIORIDADE_MAXIMA", "PRODUZIR"} and trend_stage == "EVERGREEN":
        return "CORE"
    return "EXPERIMENTAL"


def portfolio_drift(counts: dict[str, int]) -> dict[str, dict[str, float]]:
    """Compara a distribuicao real do buffer com o alvo 60/25/15."""
    total = sum(counts.get(b, 0) for b in PORTFOLIO_TARGET) or 0
    out: dict[str, dict[str, float]] = {}
    for bucket, target in PORTFOLIO_TARGET.items():
        actual = (counts.get(bucket, 0) / total) if total else 0.0
        out[bucket] = {
            "target": target,
            "actual": round(actual, 3),
            "drift": round(actual - target, 3),
            "count": counts.get(bucket, 0),
        }
    return out


def next_bucket(counts: dict[str, int]) -> str:
    """Qual bucket esta mais defasado -- o proximo video deveria vir dele."""
    drift = portfolio_drift(counts)
    return min(drift, key=lambda b: drift[b]["drift"])


# ---------------------------------------------------------------------------
# SISTEMA DE MORTE
# ---------------------------------------------------------------------------


@dataclass
class KillVerdict:
    verdict: str  # MATAR | MANTER | ESCALAR | DADOS_INSUFICIENTES
    samples: int
    observed: float
    baseline: float
    ratio: float | None
    rationale: str
    evidence_level: str

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "samples": self.samples,
            "observed": self.observed,
            "baseline": self.baseline,
            "ratio": self.ratio,
            "rationale": self.rationale,
            "evidence_level": self.evidence_level,
        }


def evaluate_kill(
    samples: list[float],
    baseline_samples: list[float],
    rules: DeathSystem | None = None,
) -> KillVerdict:
    """Decide matar, manter ou escalar um nicho/formato/hook/horario.

    Usa mediana (nao media): um unico video viral nao deve salvar um formato
    que falha de forma consistente, nem um zero deve condenar um que funciona.
    Sem amostra minima o veredito e DADOS_INSUFICIENTES -- explicitamente nao
    uma decisao, para nao transformar ruido em estrategia.
    """
    rules = rules or DeathSystem()
    n = len(samples)
    observed = round(median(samples), 4) if samples else 0.0
    baseline = round(median(baseline_samples), 4) if baseline_samples else 0.0

    if n < rules.min_samples or not baseline_samples:
        return KillVerdict(
            verdict="DADOS_INSUFICIENTES",
            samples=n,
            observed=observed,
            baseline=baseline,
            ratio=None,
            rationale=(
                f"{n} amostras contra minimo de {rules.min_samples}"
                if n < rules.min_samples
                else "sem baseline comparavel"
            ),
            evidence_level="DADOS_INSUFICIENTES",
        )

    if baseline == 0:
        return KillVerdict(
            verdict="DADOS_INSUFICIENTES",
            samples=n,
            observed=observed,
            baseline=baseline,
            ratio=None,
            rationale="baseline zerada; comparacao nao e interpretavel",
            evidence_level="DADOS_INSUFICIENTES",
        )

    ratio = round(observed / baseline, 4)
    if ratio <= rules.kill_ratio:
        verdict, why = (
            "MATAR",
            f"mediana {ratio:.0%} da baseline em {n} amostras; abaixo do corte "
            f"de {rules.kill_ratio:.0%}",
        )
    elif ratio >= rules.scale_ratio:
        verdict, why = (
            "ESCALAR",
            f"mediana {ratio:.0%} da baseline em {n} amostras; acima do corte "
            f"de {rules.scale_ratio:.0%}",
        )
    else:
        verdict, why = (
            "MANTER",
            f"mediana {ratio:.0%} da baseline; dentro da faixa neutra",
        )

    return KillVerdict(
        verdict=verdict,
        samples=n,
        observed=observed,
        baseline=baseline,
        ratio=ratio,
        rationale=why,
        # Diferenca de performance e CORRELACAO: nao prova que a dimensao
        # avaliada causou o resultado.
        evidence_level="CORRELACAO",
    )
