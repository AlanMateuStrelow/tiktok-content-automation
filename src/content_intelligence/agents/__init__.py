"""Os 8 agentes operacionais (Camada 1)."""

from .algorithm_research import ALGORITHM_AUDIT, HYPOTHESIS_GENERATOR
from .analytics_learning import ANALYTICS_LEARNING
from .base import Agent, AgentError, load_prompt
from .low_quality_detector import LOW_QUALITY_DETECTOR
from .market_trend import MARKET_INTELLIGENCE, TREND_HUNTER
from .publishing import PUBLISHING
from .quality_control import QUALITY_CONTROL, failed_checks
from .script_architect import SCRIPT_ARCHITECT
from .video_editor import VIDEO_EDITOR

ALL_AGENTS: tuple[Agent, ...] = (
    MARKET_INTELLIGENCE,
    TREND_HUNTER,
    ALGORITHM_AUDIT,
    HYPOTHESIS_GENERATOR,
    LOW_QUALITY_DETECTOR,
    SCRIPT_ARCHITECT,
    VIDEO_EDITOR,
    QUALITY_CONTROL,
    PUBLISHING,
    ANALYTICS_LEARNING,
)

__all__ = [
    "ALGORITHM_AUDIT",
    "ALL_AGENTS",
    "ANALYTICS_LEARNING",
    "Agent",
    "AgentError",
    "HYPOTHESIS_GENERATOR",
    "LOW_QUALITY_DETECTOR",
    "MARKET_INTELLIGENCE",
    "PUBLISHING",
    "QUALITY_CONTROL",
    "SCRIPT_ARCHITECT",
    "TREND_HUNTER",
    "VIDEO_EDITOR",
    "failed_checks",
    "load_prompt",
]
