"""AGENTE 5 - VIDEO EDITOR AGENT.

Produz a especificacao tecnica de edicao (shot list), executada depois via
FFmpeg/scripts. Cada elemento visual precisa declarar sua FUNCAO.
"""

from __future__ import annotations

from .base import EVIDENCE_LEVEL, Agent, obj

VISUAL_FUNCTIONS = [
    "VISUAL_CHANGE",
    "B_ROLL",
    "TEXT_OVERLAY",
    "ZOOM",
    "SOUND_EFFECT",
    "PATTERN_INTERRUPT",
]

SCHEMA = obj(
    {
        "shots": {
            "type": "array",
            "minItems": 4,
            "items": obj(
                {
                    "t_start": {"type": "number", "minimum": 0},
                    "t_end": {"type": "number", "minimum": 0},
                    "function": {
                        "type": "string",
                        "enum": VISUAL_FUNCTIONS,
                        "description": "Why this element exists. No decoration-only shots.",
                    },
                    "visual_type": {"type": "string", "description": "e.g. b-roll clip, chart, screen recording."},
                    "on_screen": {"type": "string", "description": "Karaoke-style overlay text."},
                    "transition": {"type": "string"},
                    "broll_query": {
                        "type": "string",
                        "description": "Specific search term. Never 'person typing on laptop'.",
                    },
                }
            ),
        },
        "broll_queries": {"type": "array", "minItems": 1, "items": {"type": "string"}},
        "music": obj(
            {
                "mood": {"type": "string"},
                "source": {
                    "type": "string",
                    "description": "Licensed library or platform-native audio. Name it.",
                },
                "duck_db": {
                    "type": "number",
                    "minimum": -20,
                    "maximum": -6,
                    "description": "Music level under narration, in dB (target -8 to -15).",
                },
            }
        ),
        "brand": obj(
            {
                "primary_color": {"type": "string"},
                "font": {"type": "string"},
                "handle_position": {"type": "string"},
            }
        ),
        "export": obj(
            {
                "aspect_ratio": {"type": "string", "enum": ["9:16"]},
                "resolution": {"type": "string", "enum": ["1080x1920"]},
                "codec": {"type": "string"},
                "bitrate_kbps": {"type": "integer", "minimum": 4000},
                "fps": {"type": "integer", "enum": [24, 30, 60]},
            }
        ),
        "evidence_level": EVIDENCE_LEVEL,
    }
)

GENERIC_BROLL = (
    "person typing on laptop",
    "business meeting",
    "city timelapse",
    "stock market chart",
    "man looking at phone",
)


def _validate(result: dict) -> list[str]:
    problems: list[str] = []
    shots = result.get("shots", [])

    for i, shot in enumerate(shots):
        span = float(shot.get("t_end", 0)) - float(shot.get("t_start", 0))
        if span <= 0:
            problems.append(f"shot[{i}]: intervalo invalido")
        # Mapa funcao -> elemento: troca de plano a cada 2-4s.
        elif span > 5:
            problems.append(f"shot[{i}]: {span:.1f}s sem mudanca visual (limite pratico 5s)")
        query = (shot.get("broll_query") or "").lower()
        if query and any(g in query for g in GENERIC_BROLL):
            problems.append(f"shot[{i}]: b-roll generico ({query!r})")

    # Pattern interrupt a cada 15-20s.
    if shots:
        duration = max(float(s.get("t_end", 0)) for s in shots)
        interrupts = [s for s in shots if s.get("function") == "PATTERN_INTERRUPT"]
        if duration > 20 and len(interrupts) < int(duration // 20):
            problems.append(
                f"pattern interrupts insuficientes: {len(interrupts)} para {duration:.0f}s"
            )

    music = result.get("music", {})
    duck = music.get("duck_db")
    if duck is not None and not -15 <= float(duck) <= -8:
        problems.append(f"musica em {duck}dB fora da faixa -8..-15 sob a narracao")

    return problems


VIDEO_EDITOR = Agent(
    name="video_editor",
    number=5,
    prompt_file="05_video_editor.md",
    schema=SCHEMA,
    validate=_validate,
)
