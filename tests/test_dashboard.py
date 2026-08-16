"""O painel de gestao a vista.

Duas coisas importam aqui: o estado que o quadro le tem que refletir o banco
sem inventar nada, e as acoes tem que mover o video de estado de verdade --
inclusive gravando a hora da publicacao manual, que e a unica prova de que o
video saiu.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import fixtures
import pytest

from content_intelligence import dashboard
from content_intelligence.config import Settings
from content_intelligence.knowledge_base import KnowledgeBase
from content_intelligence.llm import DryRunLLM
from content_intelligence.orchestrator import Orchestrator


@pytest.fixture()
def settings(tmp_path):
    s = Settings()
    s.db_path = str(tmp_path / "kb.db")
    return s


@pytest.fixture()
def kb(settings):
    with KnowledgeBase(settings.db_path) as db:
        yield db


@pytest.fixture()
def produced(kb, settings):
    """Um video agendado de ponta a ponta, como o `cycle` deixaria."""
    orch = Orchestrator(DryRunLLM(overrides=fixtures.happy_path()), kb, settings)
    opp = orch.hunt_trends("finance")[0]
    result = orch.produce(opp)
    assert result.succeeded
    return result


class TestEstado:
    def test_banco_vazio_nao_inventa_dado(self, kb, settings):
        state = dashboard.build_state(kb, settings)
        assert state["videos"] == []
        assert state["opportunities"] == []
        assert state["counts"] == {"APROVADO": 0, "AGENDADO": 0, "PUBLICADO": 0, "REJEITADO": 0}
        assert "BUFFER CRITICO" in state["priority"]

    def test_quadro_agrupa_por_status(self, kb, settings, produced):
        state = dashboard.build_state(kb, settings)
        assert state["counts"]["AGENDADO"] == 1
        card = state["videos"][0]
        assert card["id"] == produced.video_id
        assert card["scheduled_for"] == produced.scheduled_for
        # O card e leve de proposito: roteiro e shot list so no detalhe.
        assert "script" not in card

    def test_canais_trazem_buffer_portfolio_e_janela(self, kb, settings, produced):
        state = dashboard.build_state(kb, settings)
        finance = next(c for c in state["channels"] if c["channel"] == "finance")
        assert finance["count"] == 1
        assert finance["windows"] == ["07:30", "12:15"]
        assert set(finance["portfolio"]) == {"CORE", "EXPERIMENTAL", "OPPORTUNITY"}

    def test_estado_avisa_o_que_nao_e_automatico(self, kb, settings):
        # O painel nao pode sugerir que posta sozinho -- ver docs/ROADMAP.md.
        avisos = dashboard.build_state(kb, settings)["not_automated"]
        assert "manual" in avisos["render"]
        assert "manual" in avisos["publish"]


class TestDetalhe:
    def test_detalhe_junta_roteiro_shotlist_e_caption(self, kb, produced):
        detail = dashboard.video_detail(kb, produced.video_id)
        assert detail["script"]["id"] == produced.script_id
        assert detail["shot_list"]["shots"]
        assert detail["publishing"]["caption"]
        assert detail["publishing"]["hashtags"]
        assert detail["metrics"] == {}

    def test_video_desconhecido_estoura(self, kb):
        with pytest.raises(dashboard.DashboardError):
            dashboard.video_detail(kb, "vid_naoexiste")


class TestAcoes:
    def test_publicar_grava_a_hora(self, kb, settings, produced):
        out = dashboard.apply_action(kb, settings, produced.video_id, "publicar")
        assert out["video"]["status"] == "PUBLICADO"
        assert out["video"]["published_at"]
        # Sai do buffer: publicado nao conta como pronto para publicar.
        assert kb.buffer_count("finance") == 0

    def test_reabrir_limpa_horario_e_publicacao(self, kb, settings, produced):
        dashboard.apply_action(kb, settings, produced.video_id, "publicar")
        out = dashboard.apply_action(kb, settings, produced.video_id, "reabrir")
        assert out["video"]["status"] == "APROVADO"
        assert out["video"]["published_at"] is None
        assert out["video"]["scheduled_for"] is None

    def test_agendar_pega_slot_livre_da_janela(self, kb, settings, produced):
        dashboard.apply_action(kb, settings, produced.video_id, "reabrir")
        out = dashboard.apply_action(kb, settings, produced.video_id, "agendar")
        assert out["video"]["status"] == "AGENDADO"
        hora = out["video"]["scheduled_for"][11:16]
        assert hora in settings.publishing.windows["finance"]

    def test_rejeitar_tira_da_fila(self, kb, settings, produced):
        dashboard.apply_action(kb, settings, produced.video_id, "rejeitar")
        assert kb.buffer_count("finance") == 0

    def test_acao_invalida_e_recusada(self, kb, settings, produced):
        with pytest.raises(dashboard.DashboardError):
            dashboard.apply_action(kb, settings, produced.video_id, "postar_no_tiktok")


class TestHTTP:
    @pytest.fixture()
    def server(self, settings, produced):
        httpd = dashboard.make_server(settings, "127.0.0.1", 0)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        yield f"http://127.0.0.1:{httpd.server_port}"
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)

    # O painel e local: um proxy herdado do ambiente quebraria a chamada.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _get(self, url):
        with self.opener.open(url, timeout=10) as r:
            return json.loads(r.read())

    def test_serve_a_pagina(self, server):
        with self.opener.open(server + "/", timeout=10) as r:
            body = r.read().decode("utf-8")
        assert r.status == 200
        assert "Gestão à vista" in body

    def test_api_de_estado(self, server):
        assert self._get(server + "/api/state")["counts"]["AGENDADO"] == 1

    def test_acao_por_post(self, server, produced):
        req = urllib.request.Request(
            f"{server}/api/video/{produced.video_id}",
            data=json.dumps({"action": "publicar"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.opener.open(req, timeout=10) as r:
            body = json.loads(r.read())
        assert body["video"]["status"] == "PUBLICADO"
        assert self._get(server + "/api/state")["counts"]["PUBLICADO"] == 1

    def test_rota_desconhecida_responde_404(self, server):
        with pytest.raises(urllib.error.HTTPError) as exc:
            self._get(server + "/api/nada")
        assert exc.value.code == 404

    def test_acao_invalida_responde_400(self, server, produced):
        req = urllib.request.Request(
            f"{server}/api/video/{produced.video_id}",
            data=json.dumps({"action": "explodir"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc:
            self.opener.open(req, timeout=10)
        assert exc.value.code == 400
