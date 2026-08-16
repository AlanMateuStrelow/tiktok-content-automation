"""Saidas de agente realistas e validas, usadas para exercitar o pipeline.

Sao os stubs que o DryRunLLM devolve em `--dry-run` (e nos testes) quando
queremos que o pipeline chegue ate o fim. Sem elas, o stub generico derivado do
schema -- propositalmente burro -- e barrado pelos proprios validadores, que e
o comportamento correto.

CUIDADO: isto e conteudo de demonstracao, nao inteligencia de mercado. Os
numeros aqui sao ilustrativos. Rode sem --dry-run para obter analise real.
"""

from __future__ import annotations

from copy import deepcopy


def market_intelligence(channel: str = "finance") -> dict:
    def dims(**over):
        base = {
            "demand": 7.0,
            "growth": 7.5,
            "monetization": 8.0,
            "competition": 6.0,
            "production_ease": 7.0,
            "viral_potential": 6.0,
            "long_term_potential": 8.0,
            "expansion_potential": 6.5,
        }
        base.update(over)
        return base

    if channel == "tech_ai":
        entries = [
            {
                "name": "What actually breaks when a team ships an AI agent to production",
                "dimensions": dims(demand=7.5, competition=7.0),
                "rationale": "Post-hype phase: audience wants failure modes, not demos.",
                "monetization_notes": "Dev-tool and observability sponsors; high B2B CPM.",
            },
            {
                "name": "Local model running costs vs API pricing, with real numbers",
                "dimensions": dims(demand=6.5, monetization=7.0, competition=8.0),
                "rationale": "Every comparison video hand-waves the electricity and idle cost.",
                "monetization_notes": "Hardware affiliate links; GPU cloud sponsors.",
            },
        ]
    else:
        entries = [
            {
                "name": "401k rollover mistakes when changing jobs in your 30s",
                "dimensions": dims(),
                "rationale": "Recurring life event, high search intent, few specific videos.",
                "monetization_notes": "High-RPM finance inventory; brokerage affiliate programs.",
            },
            {
                "name": "HSA as a retirement account, not a medical account",
                "dimensions": dims(demand=6.0, monetization=7.0, competition=8.0),
                "rationale": "Widely misunderstood mechanic with a concrete tax number attached.",
                "monetization_notes": "Tax software and brokerage sponsors.",
            },
        ]
    return {
        "niches": [
            {**entry, "channel": channel, "evidence_level": "HIPOTESE"} for entry in entries
        ]
    }


def trend_hunter(channel: str = "finance") -> dict:
    if channel == "tech_ai":
        return {
            "opportunities": [
                {
                    "title": "The retry loop that quietly tripled one team's API bill",
                    "angle": "Cost post-mortem of a naive agent retry, with the actual invoice math.",
                    "evidence": "Agent frameworks shipped retries by default; nobody covers the bill.",
                    "trend_stage": "EM_ACELERACAO",
                    "saturation": 2.0,
                    "suggested_format": "screen recording + invoice breakdown",
                    "audience": "Engineers shipping their first LLM feature to production",
                    "niche_name": "What actually breaks when a team ships an AI agent to production",
                    "channel": channel,
                    "components": {
                        "demand": 7.5,
                        "trend": 8.0,
                        "monetization": 7.5,
                        "competition": 2.0,
                        "risk": 2.0,
                    },
                    "evidence_level": "HIPOTESE",
                }
            ]
        }
    return {
        "opportunities": [
            {
                "title": "The 60-day rollover clock nobody tells you about",
                "angle": "Frame it as a countdown with a tax penalty, not as generic 401k advice.",
                "evidence": "Rising job-change volume in Q1; existing videos cover only the basics.",
                "trend_stage": "EM_ACELERACAO",
                "saturation": 3.0,
                "suggested_format": "talking-head + on-screen countdown",
                "audience": "US workers aged 28-38 who just left a job with a 401k balance",
                "niche_name": "401k rollover mistakes when changing jobs in your 30s",
                "channel": channel,
                "components": {
                    "demand": 8.0,
                    "trend": 7.5,
                    "monetization": 8.0,
                    "competition": 3.0,
                    "risk": 2.0,
                },
                "evidence_level": "HIPOTESE",
            }
        ]
    }


def script_architect() -> dict:
    return {
        "concept": {
            "hook": "A 60-day clock most people never hear about",
            "promise": "You will know the exact deadline and how to avoid the 20% withholding",
            "curiosity_gap": "Why the check your old employer mails you is already short 20%",
            "body": "Explain indirect vs direct rollover with the real withholding number",
            "payoff": "The one phrase to use on the call that makes it a direct rollover",
            "cta": "",
        },
        "hooks": [
            {
                "text": "Your old employer just mailed you a check that is already 20% short.",
                "hook_type": "Unexpected",
                "retention_potential": 8.5,
                "rationale": "Concrete loss, stated as a fact about the viewer's situation.",
            },
            {
                "text": "There is a 60-day clock on your 401k and nobody started it for you.",
                "hook_type": "Curiosity",
                "retention_potential": 8.0,
                "rationale": "Time pressure with an unexplained mechanism.",
            },
            {
                "text": "Rolling over your 401k yourself is the expensive way to do it.",
                "hook_type": "Contrarian",
                "retention_potential": 7.5,
                "rationale": "Challenges the default assumption.",
            },
            {
                "text": "The IRS withholds 20% of an indirect rollover before you see a cent.",
                "hook_type": "Data",
                "retention_potential": 7.8,
                "rationale": "Specific number, verifiable.",
            },
        ],
        "selected_hook": "Your old employer just mailed you a check that is already 20% short.",
        "sections": [
            {
                "label": "HOOK",
                "start_s": 0,
                "end_s": 2,
                "text": "Your old employer just mailed you a check that is already 20% short.",
                "on_screen": "20% GONE",
            },
            {
                "label": "CONTEXTO",
                "start_s": 2,
                "end_s": 10,
                "text": "That is mandatory federal withholding on an indirect rollover, and the 60-day clock started the day they cut it.",
                "on_screen": "60-DAY CLOCK",
            },
            {
                "label": "DESENVOLVIMENTO",
                "start_s": 10,
                "end_s": 72,
                "text": "To keep the full balance you have to deposit 100% of it, including the withheld 20%, within 60 days. Ask for a direct trustee-to-trustee transfer instead and none of it is withheld.",
                "on_screen": "DIRECT TRANSFER",
            },
            {
                "label": "FECHO",
                "start_s": 72,
                "end_s": 90,
                "text": "Call your plan administrator and say the words: direct rollover, payable to the receiving custodian.",
                "on_screen": "SAY THIS",
            },
        ],
        "sources": ["IRS Publication 590-A, rollover withholding rules"],
        "tone": "Direct, first-person, no hedging",
        "duration_s": 90,
        "structure_signature": "loss-first -> mechanism -> exact script",
        "evidence_level": "FATO",
    }


def low_quality_detector(pass_gate: bool = True) -> dict:
    if pass_gate:
        return {
            "quality_score": 84,
            "retention_risk": 32,
            "viral_potential": 66,
            "drop_off_points": [],
            "issues": [],
            "verdict": "AVANCAR",
            "evidence_level": "HIPOTESE",
        }
    return {
        "quality_score": 41,
        "retention_risk": 78,
        "viral_potential": 22,
        "drop_off_points": [
            {"at_second": 6, "reason": "context runs long before any payoff", "fix": "cut to the number by second 4"}
        ],
        "issues": [
            {"category": "long_intro", "detail": "8s of setup before the first concrete number", "blocking": True}
        ],
        "verdict": "REESCREVER",
        "evidence_level": "HIPOTESE",
    }


def algorithm_audit(pass_gate: bool = True) -> dict:
    return {
        "shadowban_risk": "baixo" if pass_gate else "alto",
        "shadowban_reasons": [] if pass_gate else ["synthetic voice with no pace variation"],
        "distribution_potential": 8.0 if pass_gate else 3.0,
        "duration_assessment": {"recommended_seconds": 90, "reasoning": "One mechanic, one payoff."},
        "hook_assessment": {
            "specific_enough": True,
            "seconds_to_payoff_signal": 1.5,
            "notes": "Names a number the viewer can check against their own statement.",
        },
        "audio_assessment": {"risk": "baixo", "notes": "Platform-native licensed track."},
        "required_changes": [] if pass_gate else ["re-record narration with pace variation"],
        "optional_changes": ["consider a tighter FECHO"],
        "evidence_level": "HIPOTESE",
    }


def video_editor(duration: int = 90) -> dict:
    shots = []
    t = 0
    index = 0
    while t < duration:
        end = min(t + 4, duration)
        shots.append(
            {
                "t_start": t,
                "t_end": end,
                "function": "PATTERN_INTERRUPT" if index % 5 == 0 else "VISUAL_CHANGE",
                "visual_type": "talking head" if index % 2 else "screen recording",
                "on_screen": "20% WITHHELD" if index == 0 else f"beat {index}",
                "transition": "hard cut",
                "broll_query": "401k distribution check stub close up",
            }
        )
        t = end
        index += 1
    return {
        "shots": shots,
        "broll_queries": ["401k distribution check stub close up", "IRS form 1099-R detail"],
        "music": {"mood": "tense minimal", "source": "platform licensed library", "duck_db": -12},
        "brand": {"primary_color": "#0F172A", "font": "Inter Tight", "handle_position": "bottom-left"},
        "export": {
            "aspect_ratio": "9:16",
            "resolution": "1080x1920",
            "codec": "h264",
            "bitrate_kbps": 8000,
            "fps": 30,
        },
        "evidence_level": "FATO",
    }


def publishing() -> dict:
    return {
        "caption": "Indirect rollover = 20% withheld up front and a 60-day clock. Direct transfer = neither.",
        "hashtags": ["#401k", "#rollover", "#retirementplanning", "#taxes"],
        "pinned_comment": "Source: IRS Publication 590-A. Which part tripped you up?",
        "evidence_level": "FATO",
    }


def quality_control(approve: bool = True) -> dict:
    ok = {"passed": True, "detail": ""}
    result = {
        "content": {
            "hook_is_specific": deepcopy(ok),
            "has_concrete_data": deepcopy(ok),
            "no_niche_cliches": deepcopy(ok),
            "payoff_matches_promise": deepcopy(ok),
            "no_invented_facts": deepcopy(ok),
        },
        "video": {
            "audio_clean": deepcopy(ok),
            "captions_synced": deepcopy(ok),
            "structure_differs_from_last_3": deepcopy(ok),
            "voice_has_rhythm_variation": deepcopy(ok),
            "cut_pace_2_to_4s": deepcopy(ok),
        },
        "platform": {
            "format_and_duration_ok": deepcopy(ok),
            "caption_and_hashtags_specific": deepcopy(ok),
            "policy_compliant": deepcopy(ok),
        },
        "business": {
            "no_unqualified_advice": deepcopy(ok),
            "cost_justified": deepcopy(ok),
        },
        "originality_score": 8.0,
        "verdict": "APROVADO",
        "blocking_failures": [],
        "evidence_level": "HIPOTESE",
    }
    if not approve:
        result["content"]["has_concrete_data"] = {
            "passed": False,
            "detail": "no verifiable number in the DESENVOLVIMENTO section",
        }
        result["verdict"] = "REJEITADO"
        result["blocking_failures"] = ["add a citable number to DESENVOLVIMENTO"]
        result["originality_score"] = 4.0
    return result


def hypotheses(channel: str = "finance") -> dict:
    return {
        "hypotheses": [
            {
                "hypothesis": "Opening on a concrete dollar loss holds retention better than opening on a question",
                "test": "10 comparable videos, 5 per group, varying only the first 2 seconds",
                "variable": "hook type (Data/Unexpected vs Question)",
                "metric": "retention at 3s, measured at 72h",
                "min_samples_per_group": 5,
                "channel": channel,
                "evidence_level": "HIPOTESE",
            }
        ]
    }


def analytics_learning() -> dict:
    return {
        "what_won": {
            "dimension": "hook",
            "reasoning": "Loss-framed openings led the top 3 by retention, but topic also differed.",
            "evidence_level": "CORRELACAO",
        },
        "variations": [
            {"description": "Same loss framing, different tax mechanic", "what_changes": "topic only"}
        ],
        "learnings": [
            {
                "topic": "hooks",
                "statement": "Loss-framed openings correlate with higher 3s retention on the finance channel",
                "evidence_level": "CORRELACAO",
                "supporting_video_ids": [],
            }
        ],
        "next_experiments": [
            {
                "hypothesis": "Loss framing beats curiosity framing at 3s",
                "test": "10 videos, same topic, two hook types",
                "variable": "hook framing",
                "metric": "retention at 3s",
                "channel": "finance",
            }
        ],
        "strategy_updates": ["Agente 4: priorizar hooks tipo Data/Unexpected no canal finance"],
    }


def demo_overrides() -> dict[str, object]:
    """Overrides do `--dry-run`, sensiveis ao canal presente no contexto.

    Os valores sao callables: o DryRunLLM passa o texto do contexto, e cada um
    escolhe a variante do canal certo.
    """

    def channel_of(user: str) -> str:
        return "tech_ai" if "tech_ai" in user else "finance"

    return {
        **happy_path(),
        "market_intelligence": lambda user: market_intelligence(channel_of(user)),
        "trend_hunter": lambda user: trend_hunter(channel_of(user)),
        "hypothesis_generator": lambda user: hypotheses(channel_of(user)),
    }


def happy_path(channel: str = "finance") -> dict[str, dict]:
    """Overrides que levam uma oportunidade do inicio ao agendamento."""
    return {
        "market_intelligence": market_intelligence(channel),
        "trend_hunter": trend_hunter(channel),
        "script_architect": script_architect(),
        "low_quality_detector": low_quality_detector(True),
        "algorithm_audit": algorithm_audit(True),
        "video_editor": video_editor(),
        "publishing": publishing(),
        "quality_control": quality_control(True),
        "hypothesis_generator": hypotheses(channel),
        "analytics_learning": analytics_learning(),
    }
