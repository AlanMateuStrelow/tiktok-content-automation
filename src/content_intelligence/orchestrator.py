"""AGENTE 0 - CEO / ORCHESTRATOR.

Encadeia os 8 agentes, aplica os gates e nunca deixa o sistema produzir sem
medir. Toda decisao de parar/seguir e explicita e fica registrada em
`PipelineResult.stages` -- se um video morreu no meio do caminho, da para
apontar em qual gate e por que.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import scheduler
from .agents import (
    ALGORITHM_AUDIT,
    ANALYTICS_LEARNING,
    HYPOTHESIS_GENERATOR,
    LOW_QUALITY_DETECTOR,
    MARKET_INTELLIGENCE,
    PUBLISHING,
    QUALITY_CONTROL,
    SCRIPT_ARCHITECT,
    TREND_HUNTER,
    VIDEO_EDITOR,
    failed_checks,
)
from .agents.base import AgentError
from .config import Settings
from .knowledge_base import KnowledgeBase
from .llm import LLM, LLMError
from .models import (
    Experiment,
    Hook,
    KillDecision,
    Learning,
    Niche,
    Opportunity,
    Script,
    ShotList,
    Video,
    utcnow,
)
from .scoring import (
    ScoringError,
    assign_bucket,
    content_score,
    evaluate_kill,
    niche_score,
    portfolio_drift,
    should_produce,
)

RISK_ORDER = {"baixo": 0, "medio": 1, "alto": 2}


@dataclass
class Stage:
    agent: str
    status: str  # OK | GATE_FALHOU | ERRO | PULADO
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"agent": self.agent, "status": self.status, "detail": self.detail}


@dataclass
class PipelineResult:
    opportunity_id: str
    outcome: str  # AGENDADO | REJEITADO | ERRO
    stages: list[Stage] = field(default_factory=list)
    video_id: str | None = None
    script_id: str | None = None
    scheduled_for: str | None = None
    rejection_reason: str = ""

    @property
    def succeeded(self) -> bool:
        return self.outcome == "AGENDADO"

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "outcome": self.outcome,
            "video_id": self.video_id,
            "script_id": self.script_id,
            "scheduled_for": self.scheduled_for,
            "rejection_reason": self.rejection_reason,
            "stages": [s.to_dict() for s in self.stages],
        }


class Orchestrator:
    def __init__(self, llm: LLM, kb: KnowledgeBase, settings: Settings | None = None) -> None:
        self.llm = llm
        self.kb = kb
        self.settings = settings or Settings()

    # -- FASE 1: Market Discovery ------------------------------------------
    def discover_niches(self, channel: str, extra_context: dict | None = None) -> list[Niche]:
        """Agente 1 Parte A: avalia sub-nichos e grava o NICHE SCORE."""
        context = {
            "channel": channel,
            "markets": list(self.settings.markets),
            "task": (
                "Evaluate candidate sub-niches for this channel. Be specific: a "
                "sub-niche someone could build 50 videos around, not a category."
            ),
            **(extra_context or {}),
        }
        result = MARKET_INTELLIGENCE.run(self.llm, context)

        niches: list[Niche] = []
        for item in result.get("niches", []):
            try:
                score = niche_score(item["dimensions"], self.settings.niche_weights)
            except (ScoringError, KeyError) as exc:
                raise AgentError(f"[market_intelligence] {item.get('name')}: {exc}") from exc
            niche = Niche(
                name=item["name"],
                channel=item.get("channel", channel),
                dimensions=item["dimensions"],
                score=score,
                evidence_level=item.get("evidence_level", "HIPOTESE"),
                rationale=item.get("rationale", ""),
                monetization_notes=item.get("monetization_notes", ""),
            )
            self.kb.save_niche(niche)
            niches.append(niche)

        niches.sort(key=lambda n: n.score, reverse=True)
        return niches

    # -- FASE 2/3: Trend hunting + CONTENT SCORE ---------------------------
    def hunt_trends(self, channel: str, extra_context: dict | None = None) -> list[Opportunity]:
        """Agente 1 Parte B: angulos do dia, ja pontuados e priorizados."""
        context = {
            "channel": channel,
            "markets": list(self.settings.markets),
            "top_niches": [
                {"name": n["name"], "score": n["score"]}
                for n in self.kb.top_niches(limit=5, channel=channel)
            ],
            "recent_titles": [v["title"] for v in self.kb.recent_videos(channel, limit=5)],
            "task": "Find 3-5 angles worth producing this week. Avoid anything already covered above.",
            **(extra_context or {}),
        }
        result = TREND_HUNTER.run(self.llm, context)

        opportunities: list[Opportunity] = []
        for item in result.get("opportunities", []):
            components = self._content_components(item)
            score = content_score(components, self.settings.content_weights)
            opp = Opportunity(
                channel=item.get("channel", channel),
                title=item["title"],
                angle=item["angle"],
                evidence=item.get("evidence", ""),
                trend_stage=item["trend_stage"],
                saturation=item.get("saturation", 5),
                suggested_format=item.get("suggested_format", ""),
                audience=item.get("audience", ""),
                niche_name=item.get("niche_name", ""),
                components=components,
                content_score=score.value,
                decision=score.decision,
                bucket=assign_bucket(item["trend_stage"], score.decision),
                evidence_level=item.get("evidence_level", "HIPOTESE"),
            )
            self.kb.save_opportunity(opp)
            opportunities.append(opp)

        opportunities.sort(key=lambda o: o.content_score, reverse=True)
        return opportunities

    def _content_components(self, item: dict) -> dict[str, float]:
        """Junta as notas do Agente 1 com as estimativas derivadas do angulo.

        hook/retention/production/quality ainda nao existem nesta etapa -- sao
        estimados a partir de saturacao e formato e depois SUBSTITUIDOS pelas
        notas reais do Agente 3 antes da producao.
        """
        given = item.get("components", {})
        saturation = float(item.get("saturation", 5))
        estimate = round(max(0.0, 10.0 - saturation) * 0.6 + 4.0, 2)
        return {
            "demand": float(given.get("demand", 5)),
            "trend": float(given.get("trend", 5)),
            "monetization": float(given.get("monetization", 5)),
            "competition": float(given.get("competition", saturation)),
            "risk": float(given.get("risk", 3)),
            # Estimativas provisorias, marcadas como tal no log do pipeline.
            "hook": estimate,
            "retention": estimate,
            "production": 6.0,
            "quality": estimate,
        }

    # -- Producao ----------------------------------------------------------
    def produce(self, opportunity: Opportunity) -> PipelineResult:
        """Roda a esteira completa de uma oportunidade ate o agendamento."""
        result = PipelineResult(opportunity_id=opportunity.id, outcome="ERRO")

        if not should_produce(opportunity.content_score):
            result.outcome = "REJEITADO"
            result.rejection_reason = (
                f"CONTENT SCORE {opportunity.content_score} -> {opportunity.decision}"
            )
            result.stages.append(Stage("orchestrator", "GATE_FALHOU", result.rejection_reason))
            self.kb.log_run(opportunity.id, result.outcome, result.to_dict())
            return result

        try:
            return self._produce_inner(opportunity, result)
        except (AgentError, LLMError) as exc:
            result.outcome = "ERRO"
            result.rejection_reason = str(exc)
            result.stages.append(Stage("orchestrator", "ERRO", str(exc)))
            self.kb.log_run(opportunity.id, result.outcome, result.to_dict())
            return result

    def _produce_inner(
        self, opportunity: Opportunity, result: PipelineResult
    ) -> PipelineResult:
        gates = self.settings.gates
        channel = opportunity.channel

        # --- Agente 4 + Agente 3 em loop (escreve -> detecta -> reescreve)
        script_data: dict[str, Any] | None = None
        detector: dict[str, Any] = {}
        feedback: list[str] = []

        for attempt in range(gates.max_rewrite_attempts + 1):
            script_context = {
                "opportunity": opportunity.to_dict(),
                "recent_hooks": self.kb.recent_hooks(channel, limit=10),
                "recent_structures": [
                    v.get("format", "") for v in self.kb.recent_videos(channel, limit=3)
                ],
            }
            if feedback:
                script_context["rejection_feedback"] = feedback
                script_context["task"] = (
                    "A previous draft was rejected. Fix exactly the points listed in "
                    "rejection_feedback. Keep what already worked."
                )
            script_data = SCRIPT_ARCHITECT.run(self.llm, script_context)
            result.stages.append(
                Stage("script_architect", "OK", f"tentativa {attempt + 1}", script_data)
            )

            detector = LOW_QUALITY_DETECTOR.run(
                self.llm, {"script": script_data, "opportunity": opportunity.to_dict()}
            )
            quality = detector.get("quality_score", 0)
            retention_risk = detector.get("retention_risk", 100)
            blocking = [i for i in detector.get("issues", []) if i.get("blocking")]

            passed = (
                detector.get("verdict") == "AVANCAR"
                and quality >= gates.min_quality_score
                and retention_risk <= gates.max_retention_risk
                and not blocking
            )
            if passed:
                result.stages.append(
                    Stage(
                        "low_quality_detector",
                        "OK",
                        f"quality={quality} retention_risk={retention_risk}",
                        detector,
                    )
                )
                break

            feedback = [
                f"{i.get('category')}: {i.get('detail')}" for i in detector.get("issues", [])
            ] + [
                f"drop-off previsto em {d.get('at_second')}s: {d.get('reason')} -> {d.get('fix')}"
                for d in detector.get("drop_off_points", [])
            ]
            result.stages.append(
                Stage(
                    "low_quality_detector",
                    "GATE_FALHOU",
                    f"quality={quality} retention_risk={retention_risk}; tentativa {attempt + 1}",
                    detector,
                )
            )
        else:
            result.outcome = "REJEITADO"
            result.rejection_reason = (
                f"Low-Quality Detector reprovou apos {gates.max_rewrite_attempts + 1} tentativas"
            )
            self.kb.log_run(opportunity.id, result.outcome, result.to_dict())
            return result

        assert script_data is not None
        script = self._persist_script(opportunity, script_data)
        result.script_id = script.id

        # --- Agente 2: auditoria algoritmica antes de gastar producao
        audit = ALGORITHM_AUDIT.run(
            self.llm, {"script": script_data, "opportunity": opportunity.to_dict()}
        )
        risk = audit.get("shadowban_risk", "alto")
        potential = audit.get("distribution_potential", 0)
        required = audit.get("required_changes", [])
        if (
            RISK_ORDER.get(risk, 2) > RISK_ORDER[gates.max_shadowban_risk]
            or potential < gates.min_distribution_potential
            or required
        ):
            result.outcome = "REJEITADO"
            result.rejection_reason = (
                f"auditoria: risco={risk}, potencial={potential}, "
                f"mudancas obrigatorias={len(required)}"
            )
            result.stages.append(
                Stage("algorithm_audit", "GATE_FALHOU", result.rejection_reason, audit)
            )
            self.kb.log_run(opportunity.id, result.outcome, result.to_dict())
            return result
        result.stages.append(
            Stage("algorithm_audit", "OK", f"risco={risk} potencial={potential}", audit)
        )

        # --- Agente 5: especificacao de edicao
        shots_data = VIDEO_EDITOR.run(
            self.llm, {"script": script_data, "channel": channel}
        )
        shots = ShotList(
            script_id=script.id,
            shots=shots_data.get("shots", []),
            broll_queries=shots_data.get("broll_queries", []),
            music=shots_data.get("music", {}),
            export=shots_data.get("export", {}),
            brand=shots_data.get("brand", {}),
        )
        self.kb.save_shot_list(shots)
        result.stages.append(Stage("video_editor", "OK", f"{len(shots.shots)} planos", shots_data))

        # --- Agente 7 (copy) antes do gate final, para o QC checar caption
        copy = PUBLISHING.run(
            self.llm,
            {
                "script": script_data,
                "opportunity": opportunity.to_dict(),
                "channel": channel,
            },
        )
        result.stages.append(Stage("publishing_copy", "OK", copy.get("caption", "")[:60], copy))

        # --- Agente 6: gate final, rejeita por padrao
        qc = QUALITY_CONTROL.run(
            self.llm,
            {
                "script": script_data,
                "shot_list": shots.to_dict(),
                "publishing_copy": copy,
                "last_3_videos": self.kb.recent_videos(channel, limit=3),
                "opportunity": opportunity.to_dict(),
            },
        )
        failures = failed_checks(qc) + list(qc.get("blocking_failures", []))
        originality = qc.get("originality_score", 0)
        if qc.get("verdict") != "APROVADO" or failures or originality < gates.min_originality:
            result.outcome = "REJEITADO"
            result.rejection_reason = "; ".join(failures) or f"originalidade {originality}"
            result.stages.append(
                Stage("quality_control", "GATE_FALHOU", result.rejection_reason, qc)
            )
            self.kb.log_run(opportunity.id, result.outcome, result.to_dict())
            return result
        result.stages.append(
            Stage("quality_control", "OK", f"originalidade={originality}", qc)
        )

        # --- Agente 7 (mecanica): buffer, similaridade, slot
        video = Video(
            channel=channel,
            script_id=script.id,
            opportunity_id=opportunity.id,
            title=opportunity.title,
            hook_type=self._selected_hook_type(script_data),
            format=opportunity.suggested_format,
            bucket=opportunity.bucket,
            duration_s=int(script_data.get("duration_s", 90)),
        )

        similar, why = scheduler.too_similar(
            video.to_dict(),
            self.kb.recent_videos(channel, limit=5),
            self.settings.publishing.similarity_lookback,
        )
        taken = [v["scheduled_for"] for v in self.kb.scheduled(channel) if v.get("scheduled_for")]
        slot = scheduler.next_slot(channel, taken, self.settings.publishing)
        if similar:
            # Nao rejeita: apenas empurra para o slot seguinte, evitando dois
            # videos parecidos em sequencia.
            slot = scheduler.next_slot(channel, taken + [slot], self.settings.publishing)
            result.stages.append(Stage("scheduler", "OK", f"espacado: {why}"))

        video.status = "AGENDADO"
        video.scheduled_for = slot
        self.kb.save_video(video)

        result.video_id = video.id
        result.scheduled_for = slot
        result.outcome = "AGENDADO"
        result.stages.append(Stage("publishing_schedule", "OK", slot))
        self.kb.log_run(opportunity.id, result.outcome, result.to_dict())
        return result

    def _persist_script(self, opportunity: Opportunity, data: dict) -> Script:
        script = Script(
            opportunity_id=opportunity.id,
            channel=opportunity.channel,
            concept=data.get("concept", {}),
            hooks=[
                Hook(
                    text=h.get("text", ""),
                    hook_type=h.get("hook_type", ""),
                    retention_potential=h.get("retention_potential", 0),
                    rationale=h.get("rationale", ""),
                )
                for h in data.get("hooks", [])
            ],
            selected_hook=data.get("selected_hook", ""),
            sections=data.get("sections", []),
            sources=data.get("sources", []),
            tone=data.get("tone", ""),
            duration_s=int(data.get("duration_s", 90)),
        )
        self.kb.save_script(script)
        return script

    @staticmethod
    def _selected_hook_type(data: dict) -> str:
        selected = data.get("selected_hook")
        for hook in data.get("hooks", []):
            if hook.get("text") == selected:
                return hook.get("hook_type", "")
        return ""

    # -- Ciclo diario ------------------------------------------------------
    def run_cycle(self, channel: str, max_videos: int = 1) -> list[PipelineResult]:
        """Caca tendencias e produz ate encher o buffer ou esgotar oportunidades."""
        status = scheduler.buffer_status(
            channel, self.kb.buffer_count(channel), self.settings.publishing
        )
        needed = min(max_videos, max(status.deficit, 1 if status.critical else max_videos))

        opportunities = [
            o for o in self.hunt_trends(channel) if should_produce(o.content_score)
        ]
        results: list[PipelineResult] = []
        for opp in opportunities:
            if len(results) >= needed:
                break
            results.append(self.produce(opp))
        return results

    # -- Aprendizado -------------------------------------------------------
    def run_death_system(
        self, channel: str, metric: str = "avg_retention_pct", window: str = "72h"
    ) -> list[KillDecision]:
        """Avalia nicho/formato/hook contra a baseline do canal."""
        baseline = self.kb.metric_samples(metric, window=window, channel=channel)
        decisions: list[KillDecision] = []
        if not baseline:
            return decisions

        seen: set[tuple[str, str]] = set()
        for video in self.kb.recent_videos(channel, limit=200):
            for dimension, key in (("format", "format"), ("hook", "hook_type")):
                value = video.get(key)
                if not value or (dimension, value) in seen:
                    continue
                seen.add((dimension, value))
                samples = self.kb.metric_samples(
                    metric, window=window, channel=channel, where={key: value}
                )
                verdict = evaluate_kill(samples, baseline, self.settings.death)
                decision = KillDecision(
                    dimension=dimension,
                    value=value,
                    verdict=verdict.verdict,
                    samples=verdict.samples,
                    observed=verdict.observed,
                    baseline=verdict.baseline,
                    rationale=f"{metric}/{window}: {verdict.rationale}",
                    evidence_level=verdict.evidence_level,
                )
                self.kb.save_kill(decision)
                decisions.append(decision)
        return decisions

    def learn(self, channel: str, window: str = "72h") -> dict[str, Any]:
        """Agente 8: le metricas + vereditos de morte e devolve aprendizado."""
        kills = self.run_death_system(channel, window=window)
        performers = self.kb.performers(window=window)
        context = {
            "channel": channel,
            "window": window,
            "best_performers": performers["best"],
            "worst_performers": performers["worst"],
            "kill_verdicts": [k.to_dict() for k in kills],
            "portfolio": portfolio_drift(self.kb.bucket_counts(channel)),
            "open_experiments": self.kb.open_experiments(channel),
        }
        result = ANALYTICS_LEARNING.run(self.llm, context)

        for item in result.get("learnings", []):
            self.kb.save_learning(
                Learning(
                    topic=item.get("topic", ""),
                    statement=item.get("statement", ""),
                    evidence_level=item.get("evidence_level", "HIPOTESE"),
                    supporting_video_ids=item.get("supporting_video_ids", []),
                )
            )
        for item in result.get("next_experiments", []):
            self.kb.save_experiment(
                Experiment(
                    hypothesis=item.get("hypothesis", ""),
                    test=item.get("test", ""),
                    variable=item.get("variable", ""),
                    metric=item.get("metric", ""),
                    channel=item.get("channel", channel),
                )
            )
        result["kill_verdicts"] = [k.to_dict() for k in kills]
        return result

    def generate_hypotheses(self, channel: str, count: int = 3) -> list[Experiment]:
        """Agente 2: hipoteses testaveis para o piloto controlado (Fase 3)."""
        result = HYPOTHESIS_GENERATOR.run(
            self.llm,
            {
                "channel": channel,
                "count": count,
                "recent_learnings": self.kb.recent_learnings(limit=5),
                "open_experiments": self.kb.open_experiments(channel),
                "task": (
                    f"Propose {count} testable hypotheses for a controlled pilot. "
                    "One variable each."
                ),
            },
        )
        experiments: list[Experiment] = []
        for item in result.get("hypotheses", [])[:count]:
            exp = Experiment(
                hypothesis=item["hypothesis"],
                test=item["test"],
                variable=item["variable"],
                metric=item["metric"],
                channel=item.get("channel", channel),
                min_samples_per_group=item.get("min_samples_per_group", 5),
                evidence_level=item.get("evidence_level", "HIPOTESE"),
            )
            self.kb.save_experiment(exp)
            experiments.append(exp)
        return experiments

    # -- Saude operacional -------------------------------------------------
    def health(self) -> dict[str, Any]:
        """Estado do pipeline: buffer por canal, portfolio, proximo slot."""
        out: dict[str, Any] = {"checked_at": utcnow(), "channels": {}}
        for channel in self.settings.channels:
            status = scheduler.buffer_status(
                channel, self.kb.buffer_count(channel), self.settings.publishing
            )
            entry = status.to_dict()
            entry["portfolio"] = portfolio_drift(self.kb.bucket_counts(channel))
            try:
                taken = [
                    v["scheduled_for"]
                    for v in self.kb.scheduled(channel)
                    if v.get("scheduled_for")
                ]
                entry["next_slot"] = scheduler.next_slot(
                    channel, taken, self.settings.publishing
                )
            except (ValueError, RuntimeError) as exc:
                entry["next_slot"] = None
                entry["slot_error"] = str(exc)
            out["channels"][channel] = entry
        out["priority"] = next(
            (
                f"BUFFER CRITICO em '{c}': {d['count']} videos (minimo {d['minimum']})"
                for c, d in out["channels"].items()
                if d["critical"]
            ),
            "nenhuma prioridade critica",
        )
        return out
