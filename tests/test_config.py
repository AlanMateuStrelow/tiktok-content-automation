"""Carregamento de configuracao.

O foco e o `.env`: o `.env.example` promete que a chave da API vai ser lida
dali, e por um tempo nada leu. Um teste que so checasse "o parser funciona"
nao teria pego isso -- o que importa e que `Settings.load()` carregue o
arquivo sozinho, porque e o que a CLI chama.
"""

from __future__ import annotations

import os

import pytest

from content_intelligence.config import Settings, load_env_file


@pytest.fixture()
def cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture(autouse=True)
def ambiente_limpo(monkeypatch):
    for key in ("ANTHROPIC_API_KEY", "CI_MODEL", "CI_EFFORT", "CI_DB_PATH"):
        monkeypatch.delenv(key, raising=False)


class TestEnvFile:
    def test_sem_arquivo_nao_faz_nada(self, cwd):
        assert load_env_file() == []

    def test_le_chave_valor(self, cwd):
        (cwd / ".env").write_text("ANTHROPIC_API_KEY=sk-ant-teste\n")
        assert load_env_file() == ["ANTHROPIC_API_KEY"]
        assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-teste"

    def test_ignora_comentario_linha_vazia_e_lixo(self, cwd):
        (cwd / ".env").write_text("# comentario\n\nsem_igual\nCI_EFFORT=low\n")
        assert load_env_file() == ["CI_EFFORT"]

    def test_aceita_export_e_aspas(self, cwd):
        (cwd / ".env").write_text('export CI_MODEL="claude-opus-5"\n')
        load_env_file()
        assert os.environ["CI_MODEL"] == "claude-opus-5"

    def test_valor_vazio_nao_sobrescreve(self, cwd):
        # `.env.example` vem com ANTHROPIC_API_KEY= vazio: copiar sem preencher
        # nao pode plantar uma chave em branco no ambiente.
        (cwd / ".env").write_text("ANTHROPIC_API_KEY=\n")
        assert load_env_file() == []
        assert "ANTHROPIC_API_KEY" not in os.environ

    def test_ambiente_vence_o_arquivo(self, cwd, monkeypatch):
        monkeypatch.setenv("CI_EFFORT", "max")
        (cwd / ".env").write_text("CI_EFFORT=low\n")
        assert load_env_file() == []
        assert os.environ["CI_EFFORT"] == "max"


class TestSettingsLoad:
    def test_load_le_o_env_sozinho(self, cwd):
        # A CLI chama Settings.load() e nada mais -- se o .env nao for lido
        # aqui, a chave preenchida pelo usuario nunca chega ao SDK.
        (cwd / ".env").write_text("ANTHROPIC_API_KEY=sk-ant-teste\nCI_EFFORT=medium\n")
        settings = Settings.load()
        assert settings.effort == "medium"
        assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-teste"

    def test_json_e_env_convivem_com_env_ganhando(self, cwd):
        (cwd / "s.json").write_text('{"model": "do-json", "output_dir": "saida"}')
        (cwd / ".env").write_text("CI_MODEL=do-env\n")
        settings = Settings.load(cwd / "s.json")
        assert settings.model == "do-env"
        assert settings.output_dir == "saida"

    def test_gates_do_json_chegam_inteiros(self, cwd):
        (cwd / "s.json").write_text('{"gates": {"min_quality_score": 85}}')
        assert Settings.load(cwd / "s.json").gates.min_quality_score == 85
