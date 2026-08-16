"""Painel web de gestao a vista.

Serve um quadro local (localhost) com o estado real do pipeline: buffer por
canal, portfolio, fila de producao, roteiro e shot list de cada video, caption
pronta para colar, e o log de decisoes do orquestrador.

Duas escolhas deliberadas:

- **Sem dependencia nova.** Usa `http.server` da stdlib e HTML/JS sem build.
  O projeto continua instalavel com `pip install -e .` e nada mais.
- **Uma conexao por requisicao.** O painel le o mesmo SQLite que a CLI
  escreve; abrir o banco a cada request evita afinidade de thread e garante
  que o que a CLI acabou de gravar aparece no proximo refresh.

O painel **nao renderiza video e nao posta no TikTok** -- isso nao existe no
sistema (ver docs/ROADMAP.md). Ele mostra o que produzir e registra o que voce
ja publicou a mao.
"""

from __future__ import annotations

import errno
import json
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import scheduler
from .config import Settings
from .knowledge_base import KnowledgeBase
from .models import utcnow
from .orchestrator import operational_health

WEB_ROOT = Path(__file__).parent / "web"

# Colunas do quadro, na ordem em que o trabalho anda.
BOARD_COLUMNS: tuple[tuple[str, str], ...] = (
    ("APROVADO", "Aprovado — sem horario"),
    ("AGENDADO", "Agendado — falta produzir e postar"),
    ("PUBLICADO", "Publicado"),
    ("REJEITADO", "Rejeitado nos gates"),
)

ACTIONS: dict[str, str] = {
    "agendar": "APROVADO -> AGENDADO no proximo slot livre do canal",
    "publicar": "marca como PUBLICADO com a hora de agora",
    "rejeitar": "tira da fila",
    "reabrir": "volta para APROVADO e limpa horario/publicacao",
}


class DashboardError(RuntimeError):
    """Pedido invalido vindo do painel."""


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------
def _card(video: dict) -> dict[str, Any]:
    """Versao leve do video para o quadro -- sem roteiro nem shot list."""
    return {
        "id": video.get("id"),
        "title": video.get("title"),
        "channel": video.get("channel"),
        "status": video.get("status"),
        "bucket": video.get("bucket"),
        "format": video.get("format"),
        "hook_type": video.get("hook_type"),
        "duration_s": video.get("duration_s"),
        "scheduled_for": video.get("scheduled_for"),
        "published_at": video.get("published_at"),
        "created_at": video.get("created_at"),
        "script_id": video.get("script_id"),
        "opportunity_id": video.get("opportunity_id"),
    }


def build_state(kb: KnowledgeBase, settings: Settings) -> dict[str, Any]:
    """Tudo que o quadro precisa em uma leitura so."""
    health = operational_health(kb, settings)
    videos = kb.videos(limit=300)

    channels = []
    for name, data in health["channels"].items():
        entry = dict(data)
        entry["channel"] = name
        entry["windows"] = settings.publishing.windows.get(name, [])
        channels.append(entry)

    counts: dict[str, int] = {status: 0 for status, _ in BOARD_COLUMNS}
    for video in videos:
        status = video.get("status", "APROVADO")
        counts[status] = counts.get(status, 0) + 1

    return {
        "generated_at": utcnow(),
        "db_path": str(kb.path),
        "timezone": settings.publishing.audience_timezone,
        "priority": health["priority"],
        "channels": channels,
        "columns": [{"status": s, "label": l} for s, l in BOARD_COLUMNS],
        "counts": counts,
        "videos": [_card(v) for v in videos],
        "opportunities": kb.opportunities(limit=40),
        "learnings": kb.recent_learnings(limit=15),
        "kills": kb.recent_kills(limit=15),
        "experiments": kb.open_experiments(),
        "runs": kb.recent_runs(limit=15),
        # O painel avisa o usuario do que o sistema ainda nao faz sozinho.
        "not_automated": {
            "render": "o video nao e renderizado: a shot list e a planta, o corte e manual",
            "publish": "nao ha integracao com a API do TikTok: o post e manual",
            "metrics": "as metricas entram por 'ci-system ingest --file ...'",
        },
    }


def video_detail(kb: KnowledgeBase, video_id: str) -> dict[str, Any]:
    """Roteiro, shot list, caption e metricas de um video."""
    match = [v for v in kb.videos(limit=1000) if v.get("id") == video_id]
    if not match:
        raise DashboardError(f"video desconhecido: {video_id}")
    video = match[0]

    script = kb.script(video["script_id"]) if video.get("script_id") else None
    shots = kb.shot_list_for(video["script_id"]) if video.get("script_id") else None
    opportunity = (
        kb.opportunity(video["opportunity_id"]) if video.get("opportunity_id") else None
    )
    return {
        "video": video,
        "script": script,
        "shot_list": shots,
        "opportunity": opportunity,
        "publishing": video.get("publishing") or {},
        "metrics": kb.metrics_for(video_id),
    }


# ---------------------------------------------------------------------------
# Escrita
# ---------------------------------------------------------------------------
def apply_action(
    kb: KnowledgeBase, settings: Settings, video_id: str, action: str
) -> dict[str, Any]:
    """Move um video de estado. Toda transicao passa por aqui."""
    if action not in ACTIONS:
        raise DashboardError(f"acao desconhecida: {action}")

    match = [v for v in kb.videos(limit=1000) if v.get("id") == video_id]
    if not match:
        raise DashboardError(f"video desconhecido: {video_id}")
    video = match[0]

    if action == "agendar":
        taken = [
            v["scheduled_for"]
            for v in kb.scheduled(video["channel"])
            if v.get("scheduled_for") and v.get("id") != video_id
        ]
        slot = scheduler.next_slot(video["channel"], taken, settings.publishing)
        kb.update_video_status(video_id, "AGENDADO", scheduled_for=slot)
    elif action == "publicar":
        kb.update_video_status(video_id, "PUBLICADO", published_at=utcnow())
    elif action == "rejeitar":
        kb.update_video_status(video_id, "REJEITADO")
    else:  # reabrir
        kb.update_video_status(
            video_id, "APROVADO", scheduled_for=None, published_at=None
        )

    return video_detail(kb, video_id)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def make_handler(settings: Settings) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "ci-system-dashboard"

        # -- utilidades ---------------------------------------------------
        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, payload: Any, code: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send(code, body, "application/json; charset=utf-8")

        def _error(self, code: int, message: str) -> None:
            self._json({"error": message}, code)

        def log_message(self, *args: Any) -> None:  # silencia o log por request
            pass

        # -- rotas ---------------------------------------------------------
        def do_GET(self) -> None:  # noqa: N802 - assinatura da stdlib
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                page = WEB_ROOT / "index.html"
                if not page.exists():  # pragma: no cover - instalacao quebrada
                    self._error(500, f"UI nao encontrada em {page}")
                    return
                self._send(200, page.read_bytes(), "text/html; charset=utf-8")
                return

            if path == "/api/state":
                with KnowledgeBase(settings.db_path) as kb:
                    self._json(build_state(kb, settings))
                return

            if path.startswith("/api/video/"):
                video_id = path.rsplit("/", 1)[-1]
                try:
                    with KnowledgeBase(settings.db_path) as kb:
                        self._json(video_detail(kb, video_id))
                except DashboardError as exc:
                    self._error(404, str(exc))
                return

            self._error(404, "rota desconhecida")

        def do_POST(self) -> None:  # noqa: N802 - assinatura da stdlib
            path = urlparse(self.path).path
            if not path.startswith("/api/video/"):
                self._error(404, "rota desconhecida")
                return

            video_id = path.rsplit("/", 1)[-1]
            length = int(self.headers.get("Content-Length") or 0)
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._error(400, "corpo nao e JSON")
                return

            try:
                with KnowledgeBase(settings.db_path) as kb:
                    self._json(
                        apply_action(kb, settings, video_id, payload.get("action", ""))
                    )
            except DashboardError as exc:
                self._error(400, str(exc))
            except (ValueError, RuntimeError) as exc:
                # next_slot estoura quando nao ha horario livre no horizonte.
                self._error(409, str(exc))

    return Handler


def make_server(settings: Settings, host: str, port: int) -> HTTPServer:
    return HTTPServer((host, port), make_handler(settings))


def serve(
    settings: Settings,
    host: str = "127.0.0.1",
    port: int = 8787,
    open_browser: bool = True,
) -> int:
    try:
        httpd = make_server(settings, host, port)
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            print(
                f"erro: a porta {port} ja esta em uso -- provavelmente o painel "
                f"ja esta aberto em http://{host}:{port}.\n"
                f"       para subir um segundo: ci-system dashboard --port {port + 1}",
                file=sys.stderr,
            )
            return 1
        raise
    url = f"http://{host}:{httpd.server_port}"
    print(f"painel em {url}  (banco: {settings.db_path})")
    print("ctrl+c para parar")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:  # pragma: no cover - ambiente sem navegador
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\npainel encerrado")
    finally:
        httpd.server_close()
    return 0
