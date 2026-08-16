"""CONTENT KNOWLEDGE BASE (Agente 8, Parte C).

SQLite: um arquivo, sem servidor, versionavel em backup. Guarda nichos,
oportunidades, roteiros, videos, metricas, experimentos, aprendizados e
decisoes de morte -- e responde as perguntas que o pipeline faz antes de
produzir (buffer, baseline, ultimos hooks usados).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .models import (
    Experiment,
    KillDecision,
    Learning,
    Metrics,
    Niche,
    Opportunity,
    Script,
    ShotList,
    Video,
    utcnow,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS niches (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    channel TEXT NOT NULL,
    score REAL NOT NULL,
    evidence_level TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(name, channel)
);

CREATE TABLE IF NOT EXISTS opportunities (
    id TEXT PRIMARY KEY,
    channel TEXT NOT NULL,
    title TEXT NOT NULL,
    niche_name TEXT NOT NULL,
    trend_stage TEXT NOT NULL,
    content_score REAL NOT NULL,
    decision TEXT NOT NULL,
    bucket TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scripts (
    id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shot_lists (
    id TEXT PRIMARY KEY,
    script_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS videos (
    id TEXT PRIMARY KEY,
    channel TEXT NOT NULL,
    script_id TEXT NOT NULL,
    opportunity_id TEXT NOT NULL,
    title TEXT NOT NULL,
    hook_type TEXT NOT NULL,
    format TEXT NOT NULL,
    bucket TEXT NOT NULL,
    status TEXT NOT NULL,
    scheduled_for TEXT,
    published_at TEXT,
    experiment_id TEXT,
    variant TEXT,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL,
    window TEXT NOT NULL,
    payload TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    UNIQUE(video_id, window)
);

CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    channel TEXT NOT NULL,
    status TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS learnings (
    id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    evidence_level TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kill_log (
    id TEXT PRIMARY KEY,
    dimension TEXT NOT NULL,
    value TEXT NOT NULL,
    verdict TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id TEXT,
    outcome TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_videos_channel_status ON videos(channel, status);
CREATE INDEX IF NOT EXISTS idx_metrics_video ON metrics(video_id, window);
CREATE INDEX IF NOT EXISTS idx_opps_channel ON opportunities(channel, created_at);
"""


class KnowledgeBase:
    def __init__(self, path: str | Path = "data/knowledge_base.db") -> None:
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # -- ciclo de vida ------------------------------------------------------
    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "KnowledgeBase":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- escrita ------------------------------------------------------------
    def save_niche(self, niche: Niche) -> str:
        self.conn.execute(
            """INSERT INTO niches (id, name, channel, score, evidence_level, payload, created_at)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(name, channel) DO UPDATE SET
                 score=excluded.score,
                 evidence_level=excluded.evidence_level,
                 payload=excluded.payload""",
            (
                niche.id,
                niche.name,
                niche.channel,
                niche.score,
                niche.evidence_level,
                json.dumps(niche.to_dict(), ensure_ascii=False),
                niche.created_at,
            ),
        )
        self.conn.commit()
        return niche.id

    def save_opportunity(self, opp: Opportunity) -> str:
        self.conn.execute(
            """INSERT OR REPLACE INTO opportunities
               (id, channel, title, niche_name, trend_stage, content_score, decision,
                bucket, payload, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                opp.id,
                opp.channel,
                opp.title,
                opp.niche_name,
                opp.trend_stage,
                opp.content_score,
                opp.decision,
                opp.bucket,
                json.dumps(opp.to_dict(), ensure_ascii=False),
                opp.created_at,
            ),
        )
        self.conn.commit()
        return opp.id

    def save_script(self, script: Script) -> str:
        self.conn.execute(
            "INSERT OR REPLACE INTO scripts (id, opportunity_id, channel, payload, created_at) VALUES (?,?,?,?,?)",
            (
                script.id,
                script.opportunity_id,
                script.channel,
                json.dumps(script.to_dict(), ensure_ascii=False),
                script.created_at,
            ),
        )
        self.conn.commit()
        return script.id

    def save_shot_list(self, shots: ShotList) -> str:
        self.conn.execute(
            "INSERT OR REPLACE INTO shot_lists (id, script_id, payload, created_at) VALUES (?,?,?,?)",
            (
                shots.id,
                shots.script_id,
                json.dumps(shots.to_dict(), ensure_ascii=False),
                shots.created_at,
            ),
        )
        self.conn.commit()
        return shots.id

    def save_video(self, video: Video) -> str:
        self.conn.execute(
            """INSERT OR REPLACE INTO videos
               (id, channel, script_id, opportunity_id, title, hook_type, format, bucket,
                status, scheduled_for, published_at, experiment_id, variant, payload, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                video.id,
                video.channel,
                video.script_id,
                video.opportunity_id,
                video.title,
                video.hook_type,
                video.format,
                video.bucket,
                video.status,
                video.scheduled_for,
                video.published_at,
                video.experiment_id,
                video.variant,
                json.dumps(video.to_dict(), ensure_ascii=False),
                video.created_at,
            ),
        )
        self.conn.commit()
        return video.id

    def save_metrics(self, metrics: Metrics) -> None:
        self.conn.execute(
            """INSERT INTO metrics (video_id, window, payload, collected_at)
               VALUES (?,?,?,?)
               ON CONFLICT(video_id, window) DO UPDATE SET
                 payload=excluded.payload, collected_at=excluded.collected_at""",
            (
                metrics.video_id,
                metrics.window,
                json.dumps(metrics.to_dict(), ensure_ascii=False),
                metrics.collected_at,
            ),
        )
        self.conn.commit()

    def save_experiment(self, exp: Experiment) -> str:
        self.conn.execute(
            "INSERT OR REPLACE INTO experiments (id, channel, status, payload, created_at) VALUES (?,?,?,?,?)",
            (
                exp.id,
                exp.channel,
                exp.status,
                json.dumps(exp.to_dict(), ensure_ascii=False),
                exp.created_at,
            ),
        )
        self.conn.commit()
        return exp.id

    def save_learning(self, learning: Learning) -> str:
        self.conn.execute(
            "INSERT OR REPLACE INTO learnings (id, topic, evidence_level, payload, created_at) VALUES (?,?,?,?,?)",
            (
                learning.id,
                learning.topic,
                learning.evidence_level,
                json.dumps(learning.to_dict(), ensure_ascii=False),
                learning.created_at,
            ),
        )
        self.conn.commit()
        return learning.id

    def save_kill(self, kill: KillDecision) -> str:
        self.conn.execute(
            "INSERT OR REPLACE INTO kill_log (id, dimension, value, verdict, payload, created_at) VALUES (?,?,?,?,?,?)",
            (
                kill.id,
                kill.dimension,
                kill.value,
                kill.verdict,
                json.dumps(kill.to_dict(), ensure_ascii=False),
                kill.created_at,
            ),
        )
        self.conn.commit()
        return kill.id

    def log_run(self, opportunity_id: str | None, outcome: str, payload: dict) -> None:
        self.conn.execute(
            "INSERT INTO pipeline_runs (opportunity_id, outcome, payload, created_at) VALUES (?,?,?,?)",
            (opportunity_id, outcome, json.dumps(payload, ensure_ascii=False), utcnow()),
        )
        self.conn.commit()

    def update_video_status(
        self, video_id: str, status: str, **fields: Any
    ) -> None:
        row = self.conn.execute(
            "SELECT payload FROM videos WHERE id = ?", (video_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"video desconhecido: {video_id}")
        payload = json.loads(row["payload"])
        payload["status"] = status
        payload.update(fields)
        self.conn.execute(
            """UPDATE videos SET status=?, scheduled_for=?, published_at=?, payload=?
               WHERE id=?""",
            (
                status,
                payload.get("scheduled_for"),
                payload.get("published_at"),
                json.dumps(payload, ensure_ascii=False),
                video_id,
            ),
        )
        self.conn.commit()

    # -- leitura ------------------------------------------------------------
    def top_niches(self, limit: int = 5, channel: str | None = None) -> list[dict]:
        sql = "SELECT payload FROM niches"
        params: list[Any] = []
        if channel:
            sql += " WHERE channel = ?"
            params.append(channel)
        sql += " ORDER BY score DESC LIMIT ?"
        params.append(limit)
        return [json.loads(r["payload"]) for r in self.conn.execute(sql, params)]

    def opportunities(
        self, channel: str | None = None, min_score: float = 0.0, limit: int = 50
    ) -> list[dict]:
        sql = "SELECT payload FROM opportunities WHERE content_score >= ?"
        params: list[Any] = [min_score]
        if channel:
            sql += " AND channel = ?"
            params.append(channel)
        sql += " ORDER BY content_score DESC LIMIT ?"
        params.append(limit)
        return [json.loads(r["payload"]) for r in self.conn.execute(sql, params)]

    def buffer_count(self, channel: str) -> int:
        """Videos prontos mas ainda nao publicados (Agente 7)."""
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM videos WHERE channel=? AND status IN ('APROVADO','AGENDADO')",
            (channel,),
        ).fetchone()
        return int(row["n"])

    def bucket_counts(self, channel: str) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT bucket, COUNT(*) AS n FROM videos WHERE channel=? AND status != 'REJEITADO' GROUP BY bucket",
            (channel,),
        )
        return {r["bucket"]: int(r["n"]) for r in rows}

    def recent_videos(self, channel: str, limit: int = 3) -> list[dict]:
        rows = self.conn.execute(
            "SELECT payload FROM videos WHERE channel=? ORDER BY created_at DESC LIMIT ?",
            (channel, limit),
        )
        return [json.loads(r["payload"]) for r in rows]

    def recent_hooks(self, channel: str, limit: int = 10) -> list[str]:
        rows = self.conn.execute(
            """SELECT s.payload AS p FROM scripts s
               JOIN videos v ON v.script_id = s.id
               WHERE v.channel = ? ORDER BY s.created_at DESC LIMIT ?""",
            (channel, limit),
        )
        return [json.loads(r["p"]).get("selected_hook", "") for r in rows]

    def metrics_for(self, video_id: str) -> dict[str, dict]:
        rows = self.conn.execute(
            "SELECT window, payload FROM metrics WHERE video_id=?", (video_id,)
        )
        return {r["window"]: json.loads(r["payload"]) for r in rows}

    def metric_samples(
        self,
        metric: str,
        window: str = "72h",
        channel: str | None = None,
        where: dict[str, str] | None = None,
    ) -> list[float]:
        """Amostras de uma metrica, opcionalmente filtradas por campo do video.

        `where` aceita colunas da tabela videos (hook_type, format, bucket,
        variant, experiment_id, ...). Usado pelo sistema de morte e pelos A/B.
        """
        sql = """SELECT m.payload AS p FROM metrics m
                 JOIN videos v ON v.id = m.video_id
                 WHERE m.window = ?"""
        params: list[Any] = [window]
        if channel:
            sql += " AND v.channel = ?"
            params.append(channel)
        allowed = {
            "hook_type",
            "format",
            "bucket",
            "variant",
            "experiment_id",
            "status",
            "title",
        }
        for key, value in (where or {}).items():
            if key not in allowed:
                raise ValueError(f"filtro nao suportado: {key}")
            sql += f" AND v.{key} = ?"
            params.append(value)

        out: list[float] = []
        for row in self.conn.execute(sql, params):
            payload = json.loads(row["p"])
            if metric in payload and payload[metric] is not None:
                out.append(float(payload[metric]))
        return out

    def performers(
        self, metric: str = "avg_retention_pct", window: str = "72h", limit: int = 5
    ) -> dict[str, list[dict]]:
        rows = self.conn.execute(
            """SELECT v.payload AS v, m.payload AS m FROM metrics m
               JOIN videos v ON v.id = m.video_id WHERE m.window = ?""",
            (window,),
        )
        items = []
        for row in rows:
            video = json.loads(row["v"])
            metrics = json.loads(row["m"])
            if metrics.get(metric) is None:
                continue
            items.append({"video": video, "metrics": metrics, "value": float(metrics[metric])})
        items.sort(key=lambda i: i["value"], reverse=True)
        return {"best": items[:limit], "worst": list(reversed(items[-limit:]))}

    def open_experiments(self, channel: str | None = None) -> list[dict]:
        sql = "SELECT payload FROM experiments WHERE status IN ('ABERTO','RODANDO')"
        params: list[Any] = []
        if channel:
            sql += " AND channel = ?"
            params.append(channel)
        return [json.loads(r["payload"]) for r in self.conn.execute(sql, params)]

    def recent_learnings(self, limit: int = 10) -> list[dict]:
        rows = self.conn.execute(
            "SELECT payload FROM learnings ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [json.loads(r["payload"]) for r in rows]

    def recent_kills(self, limit: int = 10) -> list[dict]:
        rows = self.conn.execute(
            "SELECT payload FROM kill_log ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [json.loads(r["payload"]) for r in rows]

    def scheduled(self, channel: str | None = None) -> list[dict]:
        sql = "SELECT payload FROM videos WHERE status='AGENDADO'"
        params: list[Any] = []
        if channel:
            sql += " AND channel = ?"
            params.append(channel)
        sql += " ORDER BY scheduled_for ASC"
        return [json.loads(r["payload"]) for r in self.conn.execute(sql, params)]


def bulk_save_metrics(kb: KnowledgeBase, items: Iterable[Metrics]) -> int:
    count = 0
    for item in items:
        kb.save_metrics(item)
        count += 1
    return count
