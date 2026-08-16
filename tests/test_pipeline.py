"""O pipeline inteiro, com o LLM substituido por saidas fixas.

O ponto destes testes: cada gate precisa de fato parar a producao, e o motivo
da parada precisa aparecer no log -- um sistema que rejeita em silencio nao
ensina nada.
"""

from __future__ import annotations

import fixtures
import pytest

from content_intelligence.config import Settings
from content_intelligence.knowledge_base import KnowledgeBase
from content_intelligence.llm import DryRunLLM
from content_intelligence.models import Metrics, Video
from content_intelligence.orchestrator import Orchestrator


@pytest.fixture()
def kb(tmp_path):
    with KnowledgeBase(tmp_path / "kb.db") as db:
        yield db


def orchestrator(kb, overrides=None, settings=None):
    llm = DryRunLLM(overrides=overrides or fixtures.happy_path())
    return Orchestrator(llm, kb, settings or Settings())


def one_opportunity(orch, channel="finance"):
    return orch.hunt_trends(channel)[0]


class TestDiscovery:
    def test_niches_are_scored_ranked_and_persisted(self, kb):
        orch = orchestrator(kb)
        niches = orch.discover_niches("finance")
        assert len(niches) == 2
        assert niches[0].score >= niches[1].score
        assert kb.top_niches(limit=5)[0]["name"] == niches[0].name

    def test_opportunities_get_a_content_score_and_a_bucket(self, kb):
        orch = orchestrator(kb)
        opp = one_opportunity(orch)
        assert 0 <= opp.content_score <= 100
        assert opp.bucket in {"CORE", "EXPERIMENTAL", "OPPORTUNITY"}
        assert opp.decision in {
            "PRIORIDADE_MAXIMA",
            "PRODUZIR",
            "TESTAR",
            "BANCO_DE_IDEIAS",
            "DESCARTAR",
        }


class TestHappyPath:
    def test_opportunity_reaches_the_calendar(self, kb):
        orch = orchestrator(kb)
        result = orch.produce(one_opportunity(orch))

        assert result.succeeded, result.rejection_reason
        assert result.scheduled_for and result.video_id
        assert kb.buffer_count("finance") == 1

    def test_every_agent_in_the_chain_is_logged(self, kb):
        orch = orchestrator(kb)
        result = orch.produce(one_opportunity(orch))
        agents = [s.agent for s in result.stages]
        for expected in (
            "script_architect",
            "low_quality_detector",
            "algorithm_audit",
            "video_editor",
            "quality_control",
            "publishing_schedule",
        ):
            assert expected in agents

    def test_script_and_shot_list_are_persisted(self, kb):
        orch = orchestrator(kb)
        result = orch.produce(one_opportunity(orch))
        assert kb.recent_hooks("finance")[0].startswith("Your old employer")
        assert result.script_id


class TestGates:
    def test_low_content_score_never_reaches_production(self, kb):
        overrides = fixtures.happy_path()
        overrides["trend_hunter"]["opportunities"][0]["components"] = {
            "demand": 1.0,
            "trend": 1.0,
            "monetization": 1.0,
            "competition": 10.0,
            "risk": 10.0,
        }
        overrides["trend_hunter"]["opportunities"][0]["saturation"] = 8.0
        orch = orchestrator(kb, overrides)
        result = orch.produce(one_opportunity(orch))

        assert result.outcome == "REJEITADO"
        assert "CONTENT SCORE" in result.rejection_reason
        # Nao gastou nenhuma chamada de producao.
        assert [s.agent for s in result.stages] == ["orchestrator"]

    def test_low_quality_detector_stops_after_the_rewrite_budget(self, kb):
        overrides = fixtures.happy_path()
        overrides["low_quality_detector"] = fixtures.low_quality_detector(False)
        settings = Settings()
        settings.gates.max_rewrite_attempts = 1
        orch = orchestrator(kb, overrides, settings)
        result = orch.produce(one_opportunity(orch))

        assert result.outcome == "REJEITADO"
        assert "Low-Quality Detector" in result.rejection_reason
        # 1 tentativa original + 1 reescrita = 2 rodadas de roteiro.
        assert sum(s.agent == "script_architect" for s in result.stages) == 2
        assert kb.buffer_count("finance") == 0

    def test_rewrite_receives_the_exact_failure_as_feedback(self, kb):
        overrides = fixtures.happy_path()
        overrides["low_quality_detector"] = fixtures.low_quality_detector(False)
        llm = DryRunLLM(overrides=overrides)
        settings = Settings()
        settings.gates.max_rewrite_attempts = 1
        orch = Orchestrator(llm, kb, settings)
        orch.produce(one_opportunity(orch))

        rewrite_calls = [c for c in llm.calls if c["label"] == "script_architect"]
        assert "rejection_feedback" in rewrite_calls[-1]["user"]
        assert "long_intro" in rewrite_calls[-1]["user"]

    def test_algorithm_audit_blocks_high_shadowban_risk(self, kb):
        overrides = fixtures.happy_path()
        overrides["algorithm_audit"] = fixtures.algorithm_audit(False)
        orch = orchestrator(kb, overrides)
        result = orch.produce(one_opportunity(orch))

        assert result.outcome == "REJEITADO"
        assert "risco=alto" in result.rejection_reason
        assert not any(s.agent == "video_editor" for s in result.stages)

    def test_quality_control_rejects_by_default(self, kb):
        overrides = fixtures.happy_path()
        overrides["quality_control"] = fixtures.quality_control(False)
        orch = orchestrator(kb, overrides)
        result = orch.produce(one_opportunity(orch))

        assert result.outcome == "REJEITADO"
        assert "has_concrete_data" in result.rejection_reason
        assert kb.buffer_count("finance") == 0


class TestScheduling:
    def test_consecutive_videos_do_not_share_a_slot(self, kb):
        orch = orchestrator(kb)
        first = orch.produce(one_opportunity(orch))
        second = orch.produce(one_opportunity(orch))
        assert first.scheduled_for != second.scheduled_for

    def test_cycle_respects_the_video_cap(self, kb):
        orch = orchestrator(kb)
        results = orch.run_cycle("finance", max_videos=1)
        assert len(results) == 1


class TestHealth:
    def test_critical_buffer_is_surfaced_as_priority(self, kb):
        orch = orchestrator(kb)
        health = orch.health()
        assert "BUFFER CRITICO" in health["priority"]
        assert health["channels"]["finance"]["critical"] is True

    def test_health_reports_next_slot_per_channel(self, kb):
        orch = orchestrator(kb)
        health = orch.health()
        assert health["channels"]["tech_ai"]["next_slot"]


class TestLearning:
    def _publish_with_metrics(self, kb, hook_type, retentions):
        for i, retention in enumerate(retentions):
            video = Video(
                channel="finance",
                script_id=f"s{i}",
                opportunity_id=f"o{i}",
                title=f"{hook_type} video {i}",
                hook_type=hook_type,
                format="talking-head",
                bucket="CORE",
                duration_s=90,
                status="PUBLICADO",
            )
            kb.save_video(video)
            kb.save_metrics(
                Metrics(video_id=video.id, window="72h", avg_retention_pct=retention)
            )

    def test_death_system_kills_a_consistently_weak_hook(self, kb):
        self._publish_with_metrics(kb, "Data", [60.0] * 12)
        self._publish_with_metrics(kb, "Question", [20.0] * 6)
        orch = orchestrator(kb)
        decisions = {(d.dimension, d.value): d for d in orch.run_death_system("finance")}

        assert decisions[("hook", "Question")].verdict == "MATAR"
        assert decisions[("hook", "Question")].evidence_level == "CORRELACAO"

    def test_small_sample_is_never_killed(self, kb):
        self._publish_with_metrics(kb, "Data", [60.0] * 12)
        self._publish_with_metrics(kb, "Question", [20.0] * 2)
        orch = orchestrator(kb)
        decisions = {(d.dimension, d.value): d for d in orch.run_death_system("finance")}
        assert decisions[("hook", "Question")].verdict == "DADOS_INSUFICIENTES"

    def test_learn_persists_learnings_and_next_experiments(self, kb):
        self._publish_with_metrics(kb, "Data", [60.0] * 6)
        orch = orchestrator(kb)
        result = orch.learn("finance")

        assert result["what_won"]["dimension"] == "hook"
        assert kb.recent_learnings()[0]["evidence_level"] == "CORRELACAO"
        assert len(kb.open_experiments("finance")) == 1

    def test_hypotheses_are_stored_as_open_experiments(self, kb):
        orch = orchestrator(kb)
        exps = orch.generate_hypotheses("finance", count=3)
        assert exps[0].variable
        assert kb.open_experiments("finance")[0]["status"] == "ABERTO"
