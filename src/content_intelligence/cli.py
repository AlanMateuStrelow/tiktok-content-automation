"""CLI do sistema.

    ci-system health
    ci-system mission --dry-run
    ci-system cycle --channel finance
    ci-system report daily
    ci-system dashboard

Sem ANTHROPIC_API_KEY, use --dry-run: o encanamento inteiro roda com stubs.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from . import dashboard, reports
from .config import Settings
from .knowledge_base import KnowledgeBase
from .llm import LLMError, build_llm
from .models import Metrics
from .orchestrator import Orchestrator
from .scheduler import next_slot


def _add_global_flags(parser: argparse.ArgumentParser, *, suppress: bool) -> None:
    """Flags globais, aceitas antes E depois do subcomando.

    argparse so reconhece opcao do parser principal antes do subcomando, entao
    `report daily --out x.md` -- a forma que a documentacao sempre mostrou --
    morria com "unrecognized arguments". Repetir as flags em cada subparser
    resolve; `SUPPRESS` impede que a copia do subcomando sobrescreva com o
    default um valor que veio antes.
    """
    extra: dict[str, Any] = {"default": argparse.SUPPRESS} if suppress else {}
    parser.add_argument("--config", help="JSON de settings (opcional)", **extra)
    parser.add_argument("--db", help="Caminho do banco de conhecimento", **extra)
    parser.add_argument("--model", help="Sobrescreve o modelo", **extra)
    parser.add_argument(
        "--effort", choices=["low", "medium", "high", "xhigh", "max"], **extra
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nao chama a API: gera stubs validos contra o schema de cada agente",
        **extra,
    )
    parser.add_argument("--out", help="Grava a saida em arquivo alem do stdout", **extra)
    parser.add_argument("--json", action="store_true", help="Saida crua em JSON", **extra)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ci-system",
        description="Content Intelligence & Automated Media System",
    )
    _add_global_flags(p, suppress=False)

    herda_globais = argparse.ArgumentParser(add_help=False)
    _add_global_flags(herda_globais, suppress=True)

    _sub = p.add_subparsers(dest="command", required=True)

    class sub:  # noqa: N801 - so para injetar o parent em todo add_parser
        @staticmethod
        def add_parser(name: str, **kwargs: Any) -> argparse.ArgumentParser:
            return _sub.add_parser(name, parents=[herda_globais], **kwargs)

    sub.add_parser("init", help="Cria o banco de conhecimento vazio")
    sub.add_parser("health", help="Buffer, portfolio e proximo slot por canal")

    d = sub.add_parser("discover", help="FASE 1: avalia sub-nichos (NICHE SCORE)")
    d.add_argument("--channel", required=True)
    d.add_argument("--brief", help="Contexto extra em texto livre")

    t = sub.add_parser("trends", help="Caca angulos do dia e pontua (CONTENT SCORE)")
    t.add_argument("--channel", required=True)

    pr = sub.add_parser("produce", help="Roda a esteira de uma oportunidade")
    pr.add_argument("--opportunity-id", help="Id especifico; padrao = melhor score")
    pr.add_argument("--channel", required=True)

    c = sub.add_parser("cycle", help="Caca tendencias e produz ate encher o buffer")
    c.add_argument("--channel", required=True)
    c.add_argument("--max-videos", type=int, default=1)

    h = sub.add_parser("hypotheses", help="Gera hipoteses testaveis (Agente 2)")
    h.add_argument("--channel", required=True)
    h.add_argument("--count", type=int, default=3)

    i = sub.add_parser("ingest", help="Importa metricas (JSON) para a knowledge base")
    i.add_argument("--file", required=True)

    l = sub.add_parser("learn", help="Sistema de morte + aprendizado (Agente 8)")
    l.add_argument("--channel", required=True)
    l.add_argument("--window", default="72h")

    r = sub.add_parser("report", help="Gera relatorio")
    r.add_argument("kind", choices=["daily", "weekly"])
    r.add_argument(
        "--window",
        help="Janela de metricas (padrao: 72h no diario, 7d no semanal)",
    )

    sub.add_parser("schedule", help="Lista o calendario agendado")

    w = sub.add_parser(
        "dashboard", help="Painel web de gestao a vista (roda local, sem rede)"
    )
    w.add_argument("--host", default="127.0.0.1")
    w.add_argument("--port", type=int, default=8787)
    w.add_argument(
        "--no-browser", action="store_true", help="Nao abre o navegador sozinho"
    )

    m = sub.add_parser(
        "mission", help="PRIMEIRA MISSAO (Fase 1): nichos, top 5, hipoteses, calendario"
    )
    m.add_argument("--niches-per-channel", type=int, default=10)

    return p


def _emit(args: argparse.Namespace, text: str, payload: Any = None) -> None:
    output = json.dumps(payload, ensure_ascii=False, indent=2) if args.json and payload is not None else text
    print(output)
    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding="utf-8")
        print(f"\n[gravado em {path}]", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    settings = Settings.load(args.config)
    if args.db:
        settings.db_path = args.db
    if args.model:
        settings.model = args.model
    if args.effort:
        settings.effort = args.effort

    kb = KnowledgeBase(settings.db_path)
    try:
        llm = build_llm(
            dry_run=args.dry_run,
            model=settings.model,
            effort=settings.effort,
            max_tokens=settings.max_tokens,
        )
    except LLMError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        kb.close()
        return 2

    orch = Orchestrator(llm, kb, settings)
    try:
        return _dispatch(args, orch, kb, settings)
    except LLMError as exc:
        print(f"erro de LLM: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - a CLI reporta, nao explode
        print(f"erro: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        kb.close()


def _dispatch(
    args: argparse.Namespace, orch: Orchestrator, kb: KnowledgeBase, settings: Settings
) -> int:
    cmd = args.command

    if cmd == "init":
        _emit(args, f"knowledge base pronta em {settings.db_path}")
        return 0

    if cmd == "dashboard":
        # O painel abre a propria conexao a cada requisicao: le sempre o estado
        # atual do banco, mesmo com a CLI escrevendo em outro terminal.
        return dashboard.serve(settings, args.host, args.port, not args.no_browser)

    if cmd == "health":
        health = orch.health()
        _emit(args, _render_health(health), health)
        return 0

    if cmd == "discover":
        extra = {"brief": args.brief} if args.brief else None
        niches = orch.discover_niches(args.channel, extra)
        payload = [n.to_dict() for n in niches]
        lines = [f"# NICHE SCORE — {args.channel}", ""]
        lines += [
            f"{i + 1}. **{n.score}** {n.name} ({n.evidence_level}) — {n.rationale}"
            for i, n in enumerate(niches)
        ]
        _emit(args, "\n".join(lines), payload)
        return 0

    if cmd == "trends":
        opps = orch.hunt_trends(args.channel)
        payload = [o.to_dict() for o in opps]
        lines = [f"# CONTENT SCORE — {args.channel}", ""]
        lines += [
            f"- **{o.content_score}** [{o.decision}/{o.bucket}] {o.title}\n"
            f"  angulo: {o.angle}\n  evidencia: {o.evidence} ({o.evidence_level})"
            for o in opps
        ]
        _emit(args, "\n".join(lines), payload)
        return 0

    if cmd == "produce":
        opp = _pick_opportunity(kb, args.channel, args.opportunity_id)
        if opp is None:
            print("nenhuma oportunidade elegivel; rode 'trends' primeiro", file=sys.stderr)
            return 1
        result = orch.produce(opp)
        _emit(args, _render_pipeline(result), result.to_dict())
        return 0 if result.succeeded else 1

    if cmd == "cycle":
        results = orch.run_cycle(args.channel, args.max_videos)
        payload = [r.to_dict() for r in results]
        text = "\n\n".join(_render_pipeline(r) for r in results) or "nada a produzir"
        _emit(args, text, payload)
        return 0 if all(r.succeeded for r in results) else 1

    if cmd == "hypotheses":
        exps = orch.generate_hypotheses(args.channel, args.count)
        payload = [e.to_dict() for e in exps]
        lines = [f"# HIPOTESES TESTAVEIS — {args.channel}", ""]
        for i, e in enumerate(exps, 1):
            lines += [
                f"## {i}. {e.hypothesis}",
                f"- **TESTE:** {e.test}",
                f"- **VARIAVEL:** {e.variable}",
                f"- **METRICA:** {e.metric}",
                f"- **AMOSTRA MINIMA/GRUPO:** {e.min_samples_per_group}",
                "",
            ]
        _emit(args, "\n".join(lines), payload)
        return 0

    if cmd == "ingest":
        count = _ingest_metrics(kb, Path(args.file))
        _emit(args, f"{count} snapshot(s) de metrica importado(s)")
        return 0

    if cmd == "learn":
        result = orch.learn(args.channel, args.window)
        _emit(args, _render_learning(result), result)
        return 0

    if cmd == "report":
        if args.kind == "daily":
            text = reports.daily_report(
                kb, settings.channels, orch.health(), window=args.window or "72h"
            )
        else:
            text = reports.weekly_report(kb, settings.channels, window=args.window or "7d")
        _emit(args, text, {"markdown": text})
        return 0

    if cmd == "schedule":
        rows = kb.scheduled()
        lines = ["# CALENDARIO AGENDADO", ""]
        lines += [
            f"- {v['scheduled_for']} [{v['channel']}] {v['title']} ({v['bucket']})"
            for v in rows
        ] or ["- _nada agendado_"]
        _emit(args, "\n".join(lines), rows)
        return 0

    if cmd == "mission":
        text, payload = _first_mission(orch, kb, settings, args.niches_per_channel)
        _emit(args, text, payload)
        return 0

    print(f"comando desconhecido: {cmd}", file=sys.stderr)
    return 1


def _pick_opportunity(kb: KnowledgeBase, channel: str, opp_id: str | None):
    from .models import Opportunity

    candidates = kb.opportunities(channel=channel, min_score=70, limit=50)
    if opp_id:
        candidates = [o for o in candidates if o["id"] == opp_id] or [
            o for o in kb.opportunities(channel=channel, limit=200) if o["id"] == opp_id
        ]
    if not candidates:
        return None
    data = candidates[0]
    known = {f for f in Opportunity.__dataclass_fields__}
    return Opportunity(**{k: v for k, v in data.items() if k in known})


def _ingest_metrics(kb: KnowledgeBase, path: Path) -> int:
    """Importa uma lista JSON de snapshots {video_id, window, ...}."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = [data]
    known = {f for f in Metrics.__dataclass_fields__}
    count = 0
    for row in data:
        kb.save_metrics(Metrics(**{k: v for k, v in row.items() if k in known}))
        count += 1
    return count


def _first_mission(
    orch: Orchestrator, kb: KnowledgeBase, settings: Settings, per_channel: int
) -> tuple[str, dict]:
    """PRIMEIRA MISSAO: nao produz video nenhum. Entrega a Fase 1 para validacao."""
    payload: dict[str, Any] = {"niches": {}, "hypotheses": {}, "calendar": {}}
    lines = [
        "# PRIMEIRA MISSAO — FASE 1 (Market Discovery)",
        "",
        "> Nenhum video foi produzido. Valide este documento antes de liberar producao em lote.",
        "",
    ]

    all_niches = []
    for channel in settings.channels:
        niches = orch.discover_niches(
            channel,
            {"target_count": per_channel, "task": f"Evaluate {per_channel} candidate sub-niches."},
        )
        payload["niches"][channel] = [n.to_dict() for n in niches]
        all_niches += niches
        lines += [f"## Nichos avaliados — {channel}", ""]
        lines += ["| # | Sub-nicho | NICHE SCORE | Evidencia | Monetizacao |", "|---|---|---|---|---|"]
        lines += [
            f"| {i} | {n.name} | {n.score} | {n.evidence_level} | {n.monetization_notes[:70]} |"
            for i, n in enumerate(niches, 1)
        ]
        lines.append("")

    top5 = sorted(all_niches, key=lambda n: n.score, reverse=True)[:5]
    lines += ["## Os 5 melhores, com justificativa", ""]
    lines += [
        f"{i}. **{n.name}** ({n.channel}) — NICHE SCORE {n.score}. {n.rationale}"
        for i, n in enumerate(top5, 1)
    ]
    lines.append("")
    payload["top5"] = [n.to_dict() for n in top5]

    lines += ["## Primeiras hipoteses testaveis", ""]
    for channel in settings.channels:
        exps = orch.generate_hypotheses(channel, count=3)
        payload["hypotheses"][channel] = [e.to_dict() for e in exps]
        lines.append(f"### {channel}")
        lines.append("")
        for i, e in enumerate(exps, 1):
            lines += [
                f"{i}. **HIPOTESE:** {e.hypothesis}",
                f"   - TESTE: {e.test}",
                f"   - VARIAVEL: {e.variable}",
                f"   - METRICA: {e.metric}",
                f"   - AMOSTRA MINIMA POR GRUPO: {e.min_samples_per_group}",
            ]
        lines.append("")

    lines += ["## Calendario proposto (fuso do publico-alvo)", ""]
    tz = ZoneInfo(settings.publishing.audience_timezone)
    lines += [f"Fuso: **{settings.publishing.audience_timezone}**", ""]
    lines += ["| Canal | Janelas | Proximos 3 slots |", "|---|---|---|"]
    for channel in settings.channels:
        windows = settings.publishing.windows.get(channel, [])
        slots: list[str] = []
        taken: list[str] = []
        now = datetime.now(tz)
        for _ in range(3):
            slot = next_slot(channel, taken, settings.publishing, now=now)
            slots.append(slot[:16].replace("T", " "))
            taken.append(slot)
        payload["calendar"][channel] = {"windows": windows, "next_slots": slots}
        lines.append(f"| {channel} | {', '.join(windows)} | {' / '.join(slots)} |")
    lines.append("")

    lines += [
        "## Proximo passo",
        "",
        "Aguardando validacao humana. Depois de aprovado:",
        "",
        "1. `ci-system trends --channel <canal>` — mapear angulos",
        "2. `ci-system cycle --channel <canal>` — piloto controlado",
        "3. `ci-system ingest --file metrics.json` + `ci-system learn --channel <canal>`",
        "",
    ]
    return "\n".join(lines), payload


def _render_health(health: dict) -> str:
    lines = ["# SAUDE OPERACIONAL", "", f"**{health['priority']}**", ""]
    for channel, data in health["channels"].items():
        flag = "CRITICO" if data["critical"] else "ok"
        lines += [
            f"## {channel} — buffer {data['count']}/{data['minimum']} ({flag})",
            f"- proximo slot: {data.get('next_slot') or data.get('slot_error', '-')}",
            "- portfolio: "
            + ", ".join(
                f"{b} {d['actual']:.0%} (alvo {d['target']:.0%})"
                for b, d in data["portfolio"].items()
            ),
            "",
        ]
    return "\n".join(lines)


def _render_pipeline(result) -> str:
    icon = {"OK": "[ok]", "GATE_FALHOU": "[gate]", "ERRO": "[erro]", "PULADO": "[skip]"}
    lines = [
        f"# PIPELINE {result.outcome} — {result.opportunity_id}",
        "",
    ]
    for stage in result.stages:
        lines.append(f"{icon.get(stage.status, '[?]')} {stage.agent}: {stage.detail}")
    if result.scheduled_for:
        lines += ["", f"Agendado para **{result.scheduled_for}** (video {result.video_id})"]
    if result.rejection_reason:
        lines += ["", f"Motivo: {result.rejection_reason}"]
    return "\n".join(lines)


def _render_learning(result: dict) -> str:
    lines = ["# APRENDIZADO", ""]
    won = result.get("what_won", {})
    lines += [
        f"**O que venceu:** {won.get('dimension', '-')} ({won.get('evidence_level', '-')})",
        f"{won.get('reasoning', '')}",
        "",
        "## Variacoes a testar",
        "",
    ]
    lines += [
        f"- {v.get('description')} (varia: {v.get('what_changes')})"
        for v in result.get("variations", [])
    ] or ["- _nenhuma_"]
    lines += ["", "## Sistema de morte", ""]
    lines += [
        f"- **{k['verdict']}** {k['dimension']}='{k['value']}' — {k['rationale']}"
        for k in result.get("kill_verdicts", [])
    ] or ["- _sem vereditos: dados insuficientes_"]
    lines += ["", "## Aprendizados", ""]
    lines += [
        f"- [{l.get('evidence_level')}] {l.get('topic')}: {l.get('statement')}"
        for l in result.get("learnings", [])
    ] or ["- _nenhum_"]
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
