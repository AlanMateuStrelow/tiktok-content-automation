"""Os agentes so sao uteis se o contrato de saida for confiavel.

Estes testes cobrem duas coisas: (1) os schemas atendem as restricoes que
structured outputs exige, e (2) os validadores realmente barram as saidas
proibidas pela Camada 1 -- hook generico, roteiro sem numero, QC aprovando com
check reprovado.
"""

from __future__ import annotations

import fixtures
import pytest

from content_intelligence.agents import ALL_AGENTS, failed_checks
from content_intelligence.agents.base import AgentError, load_prompt
from content_intelligence.agents.market_trend import TREND_HUNTER
from content_intelligence.agents.quality_control import QUALITY_CONTROL
from content_intelligence.agents.script_architect import SCRIPT_ARCHITECT
from content_intelligence.agents.video_editor import VIDEO_EDITOR
from content_intelligence.llm import DryRunLLM


def walk_objects(schema: dict):
    if schema.get("type") == "object":
        yield schema
        for prop in schema.get("properties", {}).values():
            yield from walk_objects(prop)
    elif schema.get("type") == "array":
        yield from walk_objects(schema.get("items", {}))


@pytest.mark.parametrize("agent", ALL_AGENTS, ids=lambda a: a.name)
def test_schema_meets_structured_output_constraints(agent):
    for node in walk_objects(agent.schema):
        assert node.get("additionalProperties") is False, agent.name
        assert "required" in node, agent.name
        assert set(node["required"]) <= set(node.get("properties", {})), agent.name


@pytest.mark.parametrize("agent", ALL_AGENTS, ids=lambda a: a.name)
def test_prompt_file_exists_and_carries_layer_zero(agent):
    assert load_prompt(agent.prompt_file).strip()
    system = agent.system_prompt()
    assert "FATO" in system and "HIPOTESE" in system
    assert "Compliance is non-negotiable" in system


def run(agent, payload):
    return agent.run(DryRunLLM(overrides={agent.name: payload}), {"ctx": "x"})


class TestScriptArchitectValidation:
    def test_valid_script_passes(self):
        assert run(SCRIPT_ARCHITECT, fixtures.script_architect())["duration_s"] == 90

    def test_banned_opener_is_rejected(self):
        data = fixtures.script_architect()
        data["hooks"][0]["text"] = "Did you know your 401k has a deadline?"
        data["selected_hook"] = data["hooks"][0]["text"]
        with pytest.raises(AgentError, match="abertura proibida"):
            run(SCRIPT_ARCHITECT, data)

    def test_script_without_a_number_is_rejected(self):
        data = fixtures.script_architect()
        for section in data["sections"]:
            section["text"] = "generic advice with no figures at all"
        with pytest.raises(AgentError, match="dado numerico"):
            run(SCRIPT_ARCHITECT, data)

    def test_niche_cliche_is_rejected(self):
        data = fixtures.script_architect()
        data["sections"][2]["text"] += " Remember, money doesn't grow on trees."
        with pytest.raises(AgentError, match="clich"):
            run(SCRIPT_ARCHITECT, data)

    def test_selected_hook_must_come_from_the_variations(self):
        data = fixtures.script_architect()
        data["selected_hook"] = "Something never generated"
        with pytest.raises(AgentError, match="selected_hook"):
            run(SCRIPT_ARCHITECT, data)

    def test_hook_longer_than_2s_is_rejected(self):
        data = fixtures.script_architect()
        data["sections"][0]["end_s"] = 6
        with pytest.raises(AgentError, match="hook passa de 2s"):
            run(SCRIPT_ARCHITECT, data)


class TestTrendHunterValidation:
    def test_generic_listicle_title_is_rejected(self):
        data = fixtures.trend_hunter()
        data["opportunities"][0]["title"] = "5 tips to save money faster"
        with pytest.raises(AgentError, match="generico"):
            run(TREND_HUNTER, data)

    def test_saturated_non_evergreen_angle_is_rejected(self):
        data = fixtures.trend_hunter()
        data["opportunities"][0]["saturation"] = 10
        with pytest.raises(AgentError, match="satura"):
            run(TREND_HUNTER, data)


class TestVideoEditorValidation:
    def test_generic_broll_is_rejected(self):
        data = fixtures.video_editor()
        data["shots"][1]["broll_query"] = "person typing on laptop"
        with pytest.raises(AgentError, match="b-roll generico"):
            run(VIDEO_EDITOR, data)

    def test_static_stretch_is_rejected(self):
        data = fixtures.video_editor()
        data["shots"][0]["t_end"] = 12
        with pytest.raises(AgentError, match="sem mudanca visual"):
            run(VIDEO_EDITOR, data)

    def test_music_louder_than_the_narration_budget_is_rejected(self):
        data = fixtures.video_editor()
        data["music"]["duck_db"] = -7
        with pytest.raises(AgentError, match="fora da faixa"):
            run(VIDEO_EDITOR, data)


class TestQualityControlValidation:
    def test_approval_with_a_failed_check_is_rejected(self):
        data = fixtures.quality_control(approve=True)
        data["content"]["no_invented_facts"] = {"passed": False, "detail": "unsourced claim"}
        with pytest.raises(AgentError, match="APROVADO com"):
            run(QUALITY_CONTROL, data)

    def test_rejection_must_name_the_failure(self):
        data = fixtures.quality_control(approve=True)
        data["verdict"] = "REJEITADO"
        with pytest.raises(AgentError, match="ponto exato"):
            run(QUALITY_CONTROL, data)

    def test_failed_checks_lists_group_and_name(self):
        failures = failed_checks(fixtures.quality_control(approve=False))
        assert failures == ["content.has_concrete_data: no verifiable number in the DESENVOLVIMENTO section"]


def test_dry_run_stub_satisfies_required_fields():
    """O stub generico e proposital: valido contra o schema, burro no conteudo."""
    stub = DryRunLLM().json("sys", "user", SCRIPT_ARCHITECT.schema, label="x")
    assert set(SCRIPT_ARCHITECT.schema["required"]) <= set(stub)
    assert len(stub["hooks"]) >= 4
