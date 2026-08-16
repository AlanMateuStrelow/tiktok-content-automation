"""Reexporta os stubs de demonstracao do pacote.

Ficam em `content_intelligence.demo_data` porque o `--dry-run` da CLI usa os
mesmos dados -- um lugar so para manter saidas de agente validas.
"""

from content_intelligence.demo_data import (  # noqa: F401
    algorithm_audit,
    analytics_learning,
    demo_overrides,
    happy_path,
    hypotheses,
    low_quality_detector,
    market_intelligence,
    publishing,
    quality_control,
    script_architect,
    trend_hunter,
    video_editor,
)
