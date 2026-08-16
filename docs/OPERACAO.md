# Operação

## Rotina diária

```bash
ci-system health                      # 1. o buffer está crítico?
ci-system cycle --channel finance     # 2. produz o que falta
ci-system cycle --channel tech_ai
ci-system report daily --out out/daily-$(date +%F).md
```

**Regra que vem antes de qualquer outra:** buffer abaixo de 3 vídeos em um
canal é prioridade máxima. `health` mostra isso na primeira linha.

## Rotina semanal

```bash
ci-system discover --channel finance      # reavalia NICHE SCORE
ci-system discover --channel tech_ai
ci-system ingest --file data/metrics.json
ci-system learn --channel finance         # sistema de morte + aprendizado
ci-system learn --channel tech_ai
ci-system report weekly --out out/weekly-$(date +%F).md
```

## Coleta de métricas

O sistema não coleta métricas sozinho (ainda). Exporte do TikTok Analytics e
formate como `data/metrics.example.json`:

```json
[{ "video_id": "vid_...", "window": "72h", "views": 48200,
   "avg_retention_pct": 58.4, "revenue_usd": 21.4, "cost_usd": 3.0 }]
```

Janelas usadas pelos relatórios: `24h`, `72h`, `7d`, `30d`. Uma linha por
vídeo por janela; reimportar a mesma combinação sobrescreve.

`video_id` é o id gerado no agendamento — `ci-system schedule --json` lista.

## Lendo o sistema de morte

`ci-system learn` devolve vereditos por dimensão:

| Veredito | Significa | Faça |
|---|---|---|
| `DADOS_INSUFICIENTES` | menos de 5 amostras, ou sem baseline | continue medindo; **não decida** |
| `MATAR` | mediana ≤ 70% da baseline | pare de produzir nessa dimensão |
| `MANTER` | dentro da faixa neutra | siga, sem escalar |
| `ESCALAR` | mediana ≥ 130% da baseline | gere 5 variações (não copie o vencedor) |

Os cortes são configuráveis em `DeathSystem` (`config.py`). Baixe
`min_samples` só se aceitar decidir com mais ruído — a razão do padrão ser 5 é
que abaixo disso um único outlier decide sozinho.

## Rodando um experimento controlado

```bash
ci-system hypotheses --channel finance --count 3
```

Cada hipótese sai no formato do Agente 2: HIPÓTESE → TESTE → VARIÁVEL →
MÉTRICA. Para rodar:

1. Produza os vídeos dos dois grupos variando **só** a variável declarada.
2. Marque cada vídeo com `experiment_id` e `variant` (`control` / `test`) —
   hoje isso é feito direto no banco; o suporte na CLI está no roadmap.
3. Colete métricas nas duas janelas e compare com `kb.metric_samples(...,
   where={"variant": "test"})`.

Duas variáveis mudando ao mesmo tempo = experimento inútil para causalidade.
O resultado continua sendo `CORRELACAO`.

## Ajustando o comportamento

Tudo em `src/content_intelligence/config.py`:

- **Gates muito rígidos?** (produção rejeitando demais) — `Gates.min_quality_score`,
  `Gates.min_distribution_potential`, `Gates.min_originality`.
- **Custo alto?** — `--effort medium` antes de trocar de modelo. Depois,
  `Settings.max_tokens`.
- **Horários errados?** — `PublishingRules.windows` e `audience_timezone`.
- **Portfólio desbalanceado?** — `PORTFOLIO_TARGET`; `health` mostra o desvio.

Registre no commit **por que** mudou. Um limiar sem histórico vira superstição
em três meses.

## Quando algo quebra

| Sintoma | Causa provável |
|---|---|
| `erro: pacote 'anthropic' nao instalado` | `pip install -e .` ou use `--dry-run` |
| `requisicao recusada (categoria=...)` | classificador de segurança barrou o prompt; revise o tema |
| `[agente] saida invalida: ...` | o modelo violou uma regra da Camada 1 — a mensagem diz qual |
| `nenhum slot livre em 14 dias` | fila maior que a janela; amplie `windows` |
| Pipeline sempre `REJEITADO` no QC | veja `rejection_reason`: ele nomeia o check exato |

Todo pipeline fica em `pipeline_runs`, com o log por estágio. Nada é rejeitado
em silêncio.
