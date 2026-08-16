"""CAMADA 3 - Relatorios.

DAILY INTELLIGENCE REPORT e WEEKLY CONTENT INTELLIGENCE, em Markdown PT-BR,
montados a partir do que esta na knowledge base. Nada e inventado aqui: campo
sem dado aparece como DADOS_INSUFICIENTES.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .knowledge_base import KnowledgeBase
from .scoring import portfolio_drift

EMPTY = "_DADOS_INSUFICIENTES_"


def _fmt_date(value: str | None = None) -> str:
    dt = datetime.fromisoformat(value) if value else datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items) if items else f"- {EMPTY}"


def _mode(values: list[str]) -> str:
    values = [v for v in values if v]
    if not values:
        return EMPTY
    return max(set(values), key=values.count)


def daily_report(
    kb: KnowledgeBase,
    channels: tuple[str, ...],
    health: dict[str, Any],
    window: str = "72h",
) -> str:
    """Top 5 trends | Top 5 oportunidades | best/worst | aprendizados | acoes."""
    lines: list[str] = [
        "# DAILY INTELLIGENCE REPORT",
        f"_{_fmt_date()}_",
        "",
        f"**Prioridade agora:** {health.get('priority', EMPTY)}",
        "",
    ]

    lines += ["## 1. Top 5 tendencias", ""]
    trends: list[str] = []
    for channel in channels:
        for opp in kb.opportunities(channel=channel, limit=5)[:5]:
            trends.append(
                f"[{opp['channel']}] {opp['title']} — {opp['trend_stage']}, "
                f"saturacao {opp['saturation']}, score {opp['content_score']} "
                f"({opp['evidence_level']})"
            )
    lines += [_bullets(trends[:5]), ""]

    lines += ["## 2. Top 5 oportunidades de conteudo", ""]
    opportunities = []
    for channel in channels:
        opportunities += kb.opportunities(channel=channel, min_score=70, limit=5)
    opportunities.sort(key=lambda o: o["content_score"], reverse=True)
    lines += [
        _bullets(
            [
                f"**{o['content_score']}** ({o['decision']}/{o['bucket']}) "
                f"[{o['channel']}] {o['title']} — {o['angle']}"
                for o in opportunities[:5]
            ]
        ),
        "",
    ]

    lines += [f"## 3. Melhores e piores performers ({window})", ""]
    performers = kb.performers(window=window)
    lines += ["### Melhores", ""]
    lines += [
        _bullets(
            [
                f"{p['video']['title']} — retencao {p['value']:.1f}% "
                f"| ROI {_roi(p['metrics'])} → **acao:** gerar 5 variacoes (Agente 8)"
                for p in performers["best"]
            ]
        ),
        "",
        "### Piores",
        "",
    ]
    lines += [
        _bullets(
            [
                f"{p['video']['title']} — retencao {p['value']:.1f}% "
                f"→ **acao:** candidato ao sistema de morte"
                for p in performers["worst"]
            ]
        ),
        "",
    ]

    lines += ["## 4. Novos aprendizados", ""]
    lines += [
        _bullets(
            [
                f"[{l['evidence_level']}] {l['topic']}: {l['statement']}"
                for l in kb.recent_learnings(limit=5)
            ]
        ),
        "",
    ]

    lines += ["## 5. Experimentos", ""]
    experiments = []
    for exp in kb.open_experiments():
        experiments.append(
            f"**{exp['status']}** — HIPOTESE: {exp['hypothesis']} | "
            f"TESTE: {exp['test']} | VARIAVEL: {exp['variable']} | "
            f"METRICA: {exp['metric']} | RESULTADO: {exp.get('result') or 'pendente'}"
        )
    lines += [_bullets(experiments), ""]

    lines += ["## 6. Proximas acoes", ""]
    actions: list[str] = []
    for channel, data in health.get("channels", {}).items():
        if data.get("critical"):
            actions.append(
                f"PRIORIDADE MAXIMA: produzir {data['deficit']} video(s) para '{channel}' "
                f"(buffer {data['count']}/{data['minimum']})"
            )
        else:
            actions.append(
                f"'{channel}': buffer ok ({data['count']}), proximo slot {data.get('next_slot') or EMPTY}"
            )
    for kill in kb.recent_kills(limit=5):
        if kill["verdict"] in {"MATAR", "ESCALAR"}:
            actions.append(
                f"{kill['verdict']} {kill['dimension']}='{kill['value']}' — {kill['rationale']}"
            )
    lines += [_bullets(actions), ""]

    return "\n".join(lines)


def weekly_report(
    kb: KnowledgeBase, channels: tuple[str, ...], window: str = "7d"
) -> str:
    """WEEKLY CONTENT INTELLIGENCE: o que venceu, o que morreu, o que vem."""
    performers = kb.performers(window=window, limit=10)
    best = performers["best"]
    worst = performers["worst"]

    lines: list[str] = [
        "# WEEKLY CONTENT INTELLIGENCE",
        f"_{_fmt_date()} — janela {window}_",
        "",
        "> Performance comparada e **CORRELACAO**. Atribuicao de causa so com",
        "> experimento controlado (Agente 2).",
        "",
        "## Quadro da semana",
        "",
        "| Campo | Valor |",
        "|---|---|",
        f"| Top niche | {_top_niche(kb)} |",
        f"| Top format | {_mode([p['video'].get('format', '') for p in best])} |",
        f"| Top hook | {_mode([p['video'].get('hook_type', '') for p in best])} |",
        f"| Top topic | {best[0]['video']['title'] if best else EMPTY} |",
        f"| Top editing style | {_mode([p['video'].get('format', '') for p in best])} |",
        f"| Best posting window | {_best_window(best)} |",
        f"| Best monetization opportunity | {_best_monetization(kb, channels)} |",
        f"| Worst strategy | {worst[0]['video']['title'] if worst else EMPTY} |",
        f"| Biggest learning | {_biggest_learning(kb)} |",
        "",
    ]

    lines += ["## Portfolio por canal (alvo 60/25/15)", ""]
    for channel in channels:
        drift = portfolio_drift(kb.bucket_counts(channel))
        lines.append(f"**{channel}**")
        lines.append("")
        lines.append("| Bucket | Alvo | Real | Desvio | Videos |")
        lines.append("|---|---|---|---|---|")
        for bucket, data in drift.items():
            lines.append(
                f"| {bucket} | {data['target']:.0%} | {data['actual']:.0%} | "
                f"{data['drift']:+.0%} | {data['count']} |"
            )
        lines.append("")

    lines += ["## Sistema de morte", ""]
    lines += [
        _bullets(
            [
                f"**{k['verdict']}** {k['dimension']}='{k['value']}' "
                f"({k['samples']} amostras) — {k['rationale']}"
                for k in kb.recent_kills(limit=10)
            ]
        ),
        "",
    ]

    lines += ["## Estrategia da proxima semana", ""]
    lines += [
        _bullets(
            [
                f"[{l['evidence_level']}] {l['statement']}"
                for l in kb.recent_learnings(limit=5)
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def _roi(metrics: dict) -> str:
    roi = metrics.get("roi")
    return f"{roi:.2f}" if isinstance(roi, (int, float)) else EMPTY


def _top_niche(kb: KnowledgeBase) -> str:
    niches = kb.top_niches(limit=1)
    if not niches:
        return EMPTY
    n = niches[0]
    return f"{n['name']} (NICHE SCORE {n['score']}, {n['evidence_level']})"


def _best_window(best: list[dict]) -> str:
    slots = [
        (p["video"].get("scheduled_for") or "")[11:16] for p in best if p["video"].get("scheduled_for")
    ]
    return _mode(slots)


def _best_monetization(kb: KnowledgeBase, channels: tuple[str, ...]) -> str:
    best_niche, best_score = None, -1.0
    for channel in channels:
        for niche in kb.top_niches(limit=10, channel=channel):
            score = float(niche["dimensions"].get("monetization", 0))
            if score > best_score:
                best_niche, best_score = niche, score
    if not best_niche:
        return EMPTY
    notes = best_niche.get("monetization_notes") or ""
    return f"{best_niche['name']} (monetizacao {best_score}/10) {notes}".strip()


def _biggest_learning(kb: KnowledgeBase) -> str:
    learnings = kb.recent_learnings(limit=20)
    if not learnings:
        return EMPTY
    order = {"FATO": 0, "CORRELACAO": 1, "HIPOTESE": 2, "CAUSALIDADE_NAO_COMPROVADA": 3}
    learnings.sort(key=lambda l: order.get(l["evidence_level"], 9))
    top = learnings[0]
    return f"[{top['evidence_level']}] {top['statement']}"
