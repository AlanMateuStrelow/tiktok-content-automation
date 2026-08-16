"""Content Intelligence & Automated Media System.

Camada estrategica (o que produzir e por que) + camada tatica (como produzir),
com gates que impedem o sistema de produzir sem medir resultado.
"""

from .config import Settings
from .knowledge_base import KnowledgeBase
from .llm import AnthropicLLM, DryRunLLM, LLMConfig, LLMError, build_llm
from .orchestrator import Orchestrator, PipelineResult
from .scoring import content_score, evaluate_kill, niche_score

__version__ = "0.1.0"

__all__ = [
    "AnthropicLLM",
    "DryRunLLM",
    "KnowledgeBase",
    "LLMConfig",
    "LLMError",
    "Orchestrator",
    "PipelineResult",
    "Settings",
    "build_llm",
    "content_score",
    "evaluate_kill",
    "niche_score",
]
