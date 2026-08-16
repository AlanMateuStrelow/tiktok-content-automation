"""Mecanica de agendamento do Agente 7 (deterministica, sem LLM).

Horario no fuso do publico-alvo, janelas fixas por nicho, buffer minimo e
espacamento entre videos parecidos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .config import PublishingRules


@dataclass
class BufferStatus:
    channel: str
    count: int
    minimum: int
    target: int

    @property
    def critical(self) -> bool:
        """Buffer abaixo do minimo = prioridade maxima acima de qualquer tarefa."""
        return self.count < self.minimum

    @property
    def deficit(self) -> int:
        return max(0, self.target - self.count)

    def to_dict(self) -> dict:
        return {
            "channel": self.channel,
            "count": self.count,
            "minimum": self.minimum,
            "target": self.target,
            "critical": self.critical,
            "deficit": self.deficit,
        }


def buffer_status(channel: str, count: int, rules: PublishingRules) -> BufferStatus:
    return BufferStatus(
        channel=channel,
        count=count,
        minimum=rules.min_buffer_per_channel,
        target=rules.target_buffer_per_channel,
    )


def _slots_for_day(day: datetime, times: list[str], tz: ZoneInfo) -> list[datetime]:
    out = []
    for value in times:
        hour, minute = (int(p) for p in value.split(":"))
        out.append(day.replace(hour=hour, minute=minute, second=0, microsecond=0, tzinfo=tz))
    return sorted(out)


def next_slot(
    channel: str,
    taken: list[str],
    rules: PublishingRules,
    now: datetime | None = None,
    horizon_days: int = 14,
) -> str:
    """Proximo horario livre da janela do canal, no fuso do publico-alvo.

    `taken` sao horarios ja agendados (ISO). Um slot por horario por canal --
    o consistente vale mais que o denso.
    """
    tz = ZoneInfo(rules.audience_timezone)
    now = (now or datetime.now(tz)).astimezone(tz)
    times = rules.windows.get(channel)
    if not times:
        raise ValueError(f"canal sem janela configurada: {channel}")

    occupied = set()
    for value in taken:
        try:
            occupied.add(datetime.fromisoformat(value).astimezone(tz).isoformat())
        except ValueError:
            continue

    for offset in range(horizon_days):
        day = now + timedelta(days=offset)
        for slot in _slots_for_day(day, times, tz):
            if slot <= now:
                continue
            if slot.isoformat() in occupied:
                continue
            return slot.isoformat()

    raise RuntimeError(
        f"nenhum slot livre para '{channel}' em {horizon_days} dias -- "
        "amplie a janela ou reduza a fila"
    )


def too_similar(
    candidate: dict, recent: list[dict], lookback: int = 2
) -> tuple[bool, str]:
    """Impede dois videos de tema/formato muito parecido em sequencia."""
    for video in recent[:lookback]:
        if video.get("format") and video["format"] == candidate.get("format"):
            if video.get("hook_type") == candidate.get("hook_type"):
                return True, (
                    f"mesmo formato ({video['format']}) e mesmo tipo de hook "
                    f"({video.get('hook_type')}) do video {video.get('id')}"
                )
        cand_words = set((candidate.get("title") or "").lower().split())
        prev_words = set((video.get("title") or "").lower().split())
        if cand_words and prev_words:
            overlap = len(cand_words & prev_words) / len(cand_words | prev_words)
            if overlap >= 0.6:
                return True, (
                    f"titulo {overlap:.0%} sobreposto ao do video {video.get('id')}"
                )
    return False, ""
