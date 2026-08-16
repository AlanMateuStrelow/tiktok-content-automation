import fixtures
import pytest

from content_intelligence import reports
from content_intelligence.config import Settings
from content_intelligence.knowledge_base import KnowledgeBase
from content_intelligence.llm import DryRunLLM
from content_intelligence.orchestrator import Orchestrator

CHANNELS = ("finance", "tech_ai")


@pytest.fixture()
def kb(tmp_path):
    with KnowledgeBase(tmp_path / "kb.db") as db:
        yield db


def test_empty_state_reports_insufficient_data_instead_of_inventing(kb):
    orch = Orchestrator(DryRunLLM(), kb, Settings())
    daily = reports.daily_report(kb, CHANNELS, orch.health())
    weekly = reports.weekly_report(kb, CHANNELS)

    assert reports.EMPTY in daily
    assert reports.EMPTY in weekly
    assert "BUFFER CRITICO" in daily


def test_daily_report_has_every_required_section(kb):
    orch = Orchestrator(DryRunLLM(overrides=fixtures.happy_path()), kb, Settings())
    orch.produce(orch.hunt_trends("finance")[0])

    report = reports.daily_report(kb, CHANNELS, orch.health())
    for section in (
        "Top 5 tendencias",
        "Top 5 oportunidades",
        "performers",
        "Novos aprendizados",
        "Experimentos",
        "Proximas acoes",
    ):
        assert section in report


def test_weekly_report_flags_correlation_not_causation(kb):
    report = reports.weekly_report(kb, CHANNELS)
    assert "CORRELACAO" in report
    assert "Portfolio por canal" in report
    for field in ("Top niche", "Top format", "Top hook", "Worst strategy"):
        assert field in report
