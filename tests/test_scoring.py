import pytest

from content_intelligence.config import DeathSystem
from content_intelligence.scoring import (
    ScoringError,
    assign_bucket,
    content_score,
    decide,
    evaluate_kill,
    next_bucket,
    niche_score,
    portfolio_drift,
    should_produce,
)


def dims(value: float = 5.0, **over) -> dict:
    base = {
        "demand": value,
        "growth": value,
        "monetization": value,
        "competition": value,
        "production_ease": value,
        "viral_potential": value,
        "long_term_potential": value,
        "expansion_potential": value,
    }
    base.update(over)
    return base


def components(value: float = 5.0, **over) -> dict:
    base = {
        "demand": value,
        "trend": value,
        "hook": value,
        "retention": value,
        "production": value,
        "monetization": value,
        "quality": value,
        "competition": value,
        "risk": value,
    }
    base.update(over)
    return base


class TestNicheScore:
    def test_extremes_map_to_0_and_100(self):
        assert niche_score(dims(0)) == 0.0
        assert niche_score(dims(10)) == 100.0

    def test_monetization_outweighs_virality(self):
        # Regra critica: viralidade != rentabilidade.
        viral = niche_score(dims(5, viral_potential=10, monetization=0))
        profitable = niche_score(dims(5, viral_potential=0, monetization=10))
        assert profitable > viral

    def test_missing_dimension_is_rejected(self):
        broken = dims()
        del broken["growth"]
        with pytest.raises(ScoringError, match="growth"):
            niche_score(broken)

    def test_out_of_range_is_rejected(self):
        with pytest.raises(ScoringError, match="demand"):
            niche_score(dims(demand=11))


class TestContentScore:
    def test_penalties_lower_the_score(self):
        clean = content_score(components(8, competition=0, risk=0))
        risky = content_score(components(8, competition=10, risk=10))
        assert clean.value > risky.value

    def test_score_stays_inside_0_100(self):
        assert content_score(components(10, competition=0, risk=0)).value == 100.0
        assert content_score(components(0, competition=10, risk=10)).value == 0.0

    def test_decision_bands(self):
        assert decide(95) == "PRIORIDADE_MAXIMA"
        assert decide(85) == "PRODUZIR"
        assert decide(70) == "TESTAR"
        assert decide(69.9) == "BANCO_DE_IDEIAS"
        assert decide(12) == "DESCARTAR"

    def test_production_gate_starts_at_70(self):
        assert should_produce(70) is True
        assert should_produce(69.99) is False

    def test_components_and_penalties_are_reported_separately(self):
        result = content_score(components(6, competition=9, risk=1))
        assert set(result.penalties) == {"competition", "risk"}
        assert "hook" in result.components


class TestPortfolio:
    def test_bucket_assignment(self):
        assert assign_bucket("EMERGENTE", "TESTAR") == "OPPORTUNITY"
        assert assign_bucket("EVERGREEN", "PRODUZIR") == "CORE"
        assert assign_bucket("SATURADA", "TESTAR") == "EXPERIMENTAL"

    def test_drift_against_60_25_15(self):
        drift = portfolio_drift({"CORE": 6, "EXPERIMENTAL": 3, "OPPORTUNITY": 1})
        assert drift["CORE"]["actual"] == 0.6
        assert drift["CORE"]["drift"] == 0.0
        assert drift["EXPERIMENTAL"]["drift"] > 0

    def test_empty_portfolio_does_not_divide_by_zero(self):
        drift = portfolio_drift({})
        assert all(d["actual"] == 0.0 for d in drift.values())

    def test_next_bucket_is_the_most_underweighted(self):
        assert next_bucket({"CORE": 0, "EXPERIMENTAL": 5, "OPPORTUNITY": 5}) == "CORE"


class TestDeathSystem:
    rules = DeathSystem(min_samples=5, kill_ratio=0.7, scale_ratio=1.3)

    def test_below_min_samples_is_never_a_decision(self):
        verdict = evaluate_kill([1, 1, 1], [10] * 10, self.rules)
        assert verdict.verdict == "DADOS_INSUFICIENTES"
        assert verdict.evidence_level == "DADOS_INSUFICIENTES"

    def test_no_baseline_is_insufficient_data(self):
        verdict = evaluate_kill([5] * 10, [], self.rules)
        assert verdict.verdict == "DADOS_INSUFICIENTES"

    def test_zero_baseline_is_not_interpretable(self):
        verdict = evaluate_kill([5] * 10, [0, 0, 0], self.rules)
        assert verdict.verdict == "DADOS_INSUFICIENTES"

    def test_consistent_underperformance_is_killed(self):
        verdict = evaluate_kill([3, 3, 4, 3, 3], [10] * 20, self.rules)
        assert verdict.verdict == "MATAR"
        assert verdict.evidence_level == "CORRELACAO"

    def test_consistent_overperformance_scales(self):
        verdict = evaluate_kill([15, 14, 16, 15, 15], [10] * 20, self.rules)
        assert verdict.verdict == "ESCALAR"

    def test_neutral_band_is_kept(self):
        verdict = evaluate_kill([10, 9, 11, 10, 10], [10] * 20, self.rules)
        assert verdict.verdict == "MANTER"

    def test_median_resists_a_single_viral_outlier(self):
        # Um unico video viral nao pode salvar um formato que falha sempre.
        verdict = evaluate_kill([3, 3, 3, 3, 900], [10] * 20, self.rules)
        assert verdict.verdict == "MATAR"

    def test_verdict_carries_its_evidence(self):
        verdict = evaluate_kill([3] * 6, [10] * 20, self.rules)
        assert verdict.samples == 6
        assert "baseline" in verdict.rationale or "%" in verdict.rationale
