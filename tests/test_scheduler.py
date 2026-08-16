from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from content_intelligence.config import PublishingRules
from content_intelligence.scheduler import buffer_status, next_slot, too_similar

NY = ZoneInfo("America/New_York")
RULES = PublishingRules()


def test_slot_lands_in_the_channel_window_in_audience_time():
    now = datetime(2026, 3, 2, 5, 0, tzinfo=NY)
    slot = datetime.fromisoformat(next_slot("finance", [], RULES, now=now))
    assert slot.tzinfo is not None
    assert (slot.hour, slot.minute) == (7, 30)


def test_taken_slots_are_skipped():
    now = datetime(2026, 3, 2, 5, 0, tzinfo=NY)
    first = next_slot("finance", [], RULES, now=now)
    second = next_slot("finance", [first], RULES, now=now)
    assert second != first
    assert datetime.fromisoformat(second) > datetime.fromisoformat(first)


def test_slot_rolls_to_the_next_day_after_the_last_window():
    now = datetime(2026, 3, 2, 23, 0, tzinfo=NY)
    slot = datetime.fromisoformat(next_slot("tech_ai", [], RULES, now=now))
    assert slot.day == 3


def test_unknown_channel_is_an_error():
    with pytest.raises(ValueError, match="janela"):
        next_slot("unknown", [], RULES)


def test_horizon_exhaustion_is_explicit():
    now = datetime(2026, 3, 2, 5, 0, tzinfo=NY)
    taken = []
    for _ in range(4):  # 2 dias x 2 janelas
        taken.append(next_slot("finance", taken, RULES, now=now, horizon_days=2))
    with pytest.raises(RuntimeError, match="nenhum slot livre"):
        next_slot("finance", taken, RULES, now=now, horizon_days=2)


def test_buffer_below_minimum_is_critical():
    status = buffer_status("finance", 2, RULES)
    assert status.critical is True
    assert status.deficit == 3


def test_healthy_buffer_is_not_critical():
    assert buffer_status("finance", 5, RULES).critical is False


class TestSimilarity:
    candidate = {"format": "talking-head", "hook_type": "Data", "title": "The 60 day rollover clock"}

    def test_same_format_and_hook_in_sequence_is_flagged(self):
        recent = [{"id": "v1", "format": "talking-head", "hook_type": "Data", "title": "Other topic entirely"}]
        similar, why = too_similar(self.candidate, recent)
        assert similar and "mesmo formato" in why

    def test_overlapping_title_is_flagged(self):
        recent = [{"id": "v1", "format": "b-roll", "hook_type": "Question", "title": "The 60 day rollover clock"}]
        similar, why = too_similar(self.candidate, recent)
        assert similar and "sobreposto" in why

    def test_different_content_passes(self):
        recent = [{"id": "v1", "format": "b-roll", "hook_type": "Question", "title": "HSA triple tax advantage"}]
        assert too_similar(self.candidate, recent)[0] is False

    def test_lookback_limits_how_far_back_we_compare(self):
        recent = [
            {"id": "v1", "format": "b-roll", "hook_type": "Question", "title": "Unrelated"},
            {"id": "v2", "format": "b-roll", "hook_type": "Question", "title": "Unrelated too"},
            {"id": "v3", "format": "talking-head", "hook_type": "Data", "title": "Old"},
        ]
        assert too_similar(self.candidate, recent, lookback=2)[0] is False
        assert too_similar(self.candidate, recent, lookback=3)[0] is True
