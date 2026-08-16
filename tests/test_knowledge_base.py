import pytest

from content_intelligence.knowledge_base import KnowledgeBase
from content_intelligence.models import (
    Experiment,
    KillDecision,
    Learning,
    Metrics,
    Niche,
    Opportunity,
    Video,
)


@pytest.fixture()
def kb(tmp_path):
    with KnowledgeBase(tmp_path / "kb.db") as db:
        yield db


def make_video(kb, **over):
    video = Video(
        channel=over.pop("channel", "finance"),
        script_id="script_x",
        opportunity_id="opp_x",
        title=over.pop("title", "A title"),
        hook_type=over.pop("hook_type", "Data"),
        format=over.pop("format", "talking-head"),
        bucket=over.pop("bucket", "CORE"),
        duration_s=90,
        **over,
    )
    kb.save_video(video)
    return video


def test_niche_upsert_keeps_one_row_per_name_and_channel(kb):
    first = Niche(name="HSA", channel="finance", dimensions={}, score=50.0)
    kb.save_niche(first)
    kb.save_niche(Niche(name="HSA", channel="finance", dimensions={}, score=88.0))
    top = kb.top_niches()
    assert len(top) == 1
    assert top[0]["score"] == 88.0


def test_buffer_counts_only_unpublished(kb):
    make_video(kb, status="APROVADO")
    make_video(kb, status="AGENDADO")
    make_video(kb, status="PUBLICADO")
    assert kb.buffer_count("finance") == 2
    assert kb.buffer_count("tech_ai") == 0


def test_opportunities_filter_by_score(kb):
    for score in (95.0, 72.0, 40.0):
        kb.save_opportunity(
            Opportunity(
                channel="finance",
                title=f"t{score}",
                angle="a",
                evidence="e",
                trend_stage="EVERGREEN",
                saturation=3,
                suggested_format="f",
                audience="x",
                niche_name="n",
                content_score=score,
            )
        )
    assert len(kb.opportunities(channel="finance", min_score=70)) == 2
    assert kb.opportunities(channel="finance")[0]["content_score"] == 95.0


def test_metric_samples_can_be_filtered_by_video_field(kb):
    data_video = make_video(kb, hook_type="Data")
    question_video = make_video(kb, hook_type="Question")
    kb.save_metrics(Metrics(video_id=data_video.id, window="72h", avg_retention_pct=61.0))
    kb.save_metrics(Metrics(video_id=question_video.id, window="72h", avg_retention_pct=22.0))

    assert kb.metric_samples("avg_retention_pct", channel="finance") == pytest.approx([61.0, 22.0])
    assert kb.metric_samples(
        "avg_retention_pct", channel="finance", where={"hook_type": "Data"}
    ) == pytest.approx([61.0])


def test_metric_samples_rejects_unknown_filter(kb):
    with pytest.raises(ValueError, match="filtro nao suportado"):
        kb.metric_samples("views", where={"drop table": "x"})


def test_metrics_upsert_by_window(kb):
    video = make_video(kb)
    kb.save_metrics(Metrics(video_id=video.id, window="24h", views=10))
    kb.save_metrics(Metrics(video_id=video.id, window="24h", views=99))
    assert kb.metrics_for(video.id)["24h"]["views"] == 99


def test_roi_is_computed_and_stored(kb):
    video = make_video(kb)
    kb.save_metrics(
        Metrics(video_id=video.id, window="7d", revenue_usd=12.0, cost_usd=4.0)
    )
    assert kb.metrics_for(video.id)["7d"]["roi"] == pytest.approx(2.0)


def test_roi_is_none_without_cost(kb):
    video = make_video(kb)
    kb.save_metrics(Metrics(video_id=video.id, window="7d", revenue_usd=12.0))
    assert kb.metrics_for(video.id)["7d"]["roi"] is None


def test_performers_ranks_best_and_worst(kb):
    for retention in (10.0, 55.0, 80.0):
        video = make_video(kb, title=f"v{retention}")
        kb.save_metrics(
            Metrics(video_id=video.id, window="72h", avg_retention_pct=retention)
        )
    performers = kb.performers(window="72h", limit=1)
    assert performers["best"][0]["value"] == 80.0
    assert performers["worst"][0]["value"] == 10.0


def test_update_video_status_rejects_unknown_id(kb):
    with pytest.raises(KeyError):
        kb.update_video_status("vid_nope", "PUBLICADO")


def test_update_video_status_persists_fields(kb):
    video = make_video(kb)
    kb.update_video_status(video.id, "PUBLICADO", published_at="2026-01-01T12:00:00+00:00")
    row = kb.recent_videos("finance")[0]
    assert row["status"] == "PUBLICADO"
    assert row["published_at"].startswith("2026-01-01")


def test_open_experiments_and_learnings(kb):
    kb.save_experiment(
        Experiment(hypothesis="h", test="t", variable="v", metric="m", channel="finance")
    )
    kb.save_experiment(
        Experiment(
            hypothesis="done", test="t", variable="v", metric="m", channel="finance",
            status="CONCLUIDO",
        )
    )
    kb.save_learning(Learning(topic="hooks", statement="s", evidence_level="CORRELACAO"))
    kb.save_kill(
        KillDecision(
            dimension="format",
            value="listicle",
            verdict="MATAR",
            samples=6,
            observed=3.0,
            baseline=10.0,
            rationale="30% da baseline",
            evidence_level="CORRELACAO",
        )
    )
    assert len(kb.open_experiments("finance")) == 1
    assert kb.recent_learnings()[0]["topic"] == "hooks"
    assert kb.recent_kills()[0]["verdict"] == "MATAR"
