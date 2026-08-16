# Content Intelligence & Automated Media System

Pipeline de aquisição de audiência para dois canais de TikTok — **Finanças
Pessoais** e **Tech/IA** — voltados ao mercado de língua inglesa (EUA, Canadá,
Reino Unido, Austrália).

O objetivo não é produzir vídeos. É construir uma máquina que aprende com
dados e aumenta eficiência ao longo do tempo. Por isso o sistema **para
sozinho** em cada gate: se a oportunidade não pontua, se o roteiro é genérico,
se o QC reprova — a produção não avança, e o motivo fica registrado.

## Como isso funciona

Duas camadas. A **estratégica** decide O QUÊ e POR QUÊ (agentes 1, 2, 8); a
**tática** decide COMO (agentes 3, 4, 5, 6, 7). O orquestrador encadeia as
duas e aplica os gates.

```
trends ──► CONTENT SCORE ≥ 70 ──► roteiro (4) ──► detector (3) ──┐
                                       ▲                          │ reprovou?
                                       └──────── feedback ────────┘ reescreve
                                              │ passou
                            auditoria de algoritmo (2) ──► edição (5)
                                              │
                                     caption (7) ──► QC final (6)
                                              │ aprovado
                                     agendamento (7) ──► publica
                                              │
                            métricas ──► sistema de morte + aprendizado (8)
                                              │
                                    retroalimenta 1, 2 e 4
```

O que é **código determinístico** (mesma entrada, mesma decisão): pontuação,
faixas de decisão, portfólio 60/25/15, sistema de morte, janelas de
publicação, buffer, detecção de similaridade. O que é **julgamento do
modelo**: as notas por dimensão, o roteiro, os hooks, a spec de edição, a
leitura dos resultados.

## Instalação

```bash
pip install -e ".[dev]"
cp .env.example .env      # e preencha ANTHROPIC_API_KEY
```

Requer Python 3.11+. Sem chave da API, tudo roda em `--dry-run`.

## Primeiros comandos

```bash
# 1. Ver o encanamento funcionando, sem gastar crédito e sem chamar a API
ci-system --dry-run mission

# 2. PRIMEIRA MISSÃO de verdade (Fase 1): nichos, top 5, hipóteses, calendário
ci-system mission --out out/fase1.md

# --- depois de validar o documento acima ---

ci-system trends --channel finance          # angulos do dia + CONTENT SCORE
ci-system cycle  --channel finance          # produz até encher o buffer
ci-system health                            # buffer, portfólio, próximo slot
ci-system schedule                          # calendário agendado

# --- depois de publicar e coletar métricas ---

ci-system ingest --file data/metrics.json   # ver data/metrics.example.json
ci-system learn  --channel finance          # sistema de morte + aprendizado
ci-system report daily --out out/daily.md
ci-system report weekly --out out/weekly.md
```

Flags globais: `--dry-run`, `--json`, `--out ARQUIVO`, `--db CAMINHO`,
`--model`, `--effort {low,medium,high,xhigh,max}`, `--config settings.json`.

## Os gates (onde o sistema para)

| Gate | Agente | Regra padrão | Configurável em |
|---|---|---|---|
| CONTENT SCORE | orquestrador | `< 70` não produz | `DECISION_BANDS` |
| Qualidade pré-produção | 3 | `quality < 70`, risco de retenção `> 60`, ou qualquer issue bloqueante | `Gates.min_quality_score` |
| Reescrita | 4 ↔ 3 | até 2 tentativas com o apontamento exato do erro | `Gates.max_rewrite_attempts` |
| Auditoria de algoritmo | 2 | risco de shadowban `> médio`, potencial `< 5`, ou mudança obrigatória pendente | `Gates.max_shadowban_risk` |
| QC final | 6 | rejeita por padrão; qualquer check reprovado volta | `Gates.min_originality` |
| Buffer | 7 | abaixo de 3 vídeos = prioridade máxima | `PublishingRules` |

Todos vivem em `src/content_intelligence/config.py`. Mudou um limiar por causa
de dado real? O commit registra o porquê.

## Separação epistêmica

Toda saída carrega um rótulo: `FATO`, `HIPOTESE`, `CORRELACAO`,
`CAUSALIDADE_NAO_COMPROVADA` ou `DADOS_INSUFICIENTES`. Isso não é decorativo:

- O sistema de morte devolve `DADOS_INSUFICIENTES` — não um palpite — quando a
  amostra é menor que 5 vídeos, e usa **mediana** para que um único viral não
  salve um formato que falha sempre.
- Diferença de performance entre grupos é sempre `CORRELACAO`. Só vira
  causalidade com experimento controlado de uma variável (Agente 2).
- Relatório sem dado mostra `DADOS_INSUFICIENTES`, nunca um número inventado.

## Estrutura

```
src/content_intelligence/
├── config.py          pesos, limiares, gates, regras — tudo em um lugar
├── models.py          estruturas que atravessam o pipeline
├── scoring.py         NICHE SCORE, CONTENT SCORE, portfólio, sistema de morte
├── knowledge_base.py  CONTENT KNOWLEDGE BASE (SQLite)
├── llm.py             Messages API + structured outputs; DryRunLLM offline
├── scheduler.py       janelas, buffer, similaridade (sem LLM)
├── orchestrator.py    Agente 0: encadeia tudo e aplica os gates
├── reports.py         DAILY e WEEKLY (Camada 3)
├── cli.py             interface de linha de comando
├── demo_data.py       saídas válidas usadas pelo --dry-run
├── agents/            os 8 agentes: prompt + schema + validação
└── prompts/           prompts de sistema (em inglês — o conteúdo é para EUA/UK)
```

## Testes

```bash
pytest
```

100 testes cobrindo pontuação, sistema de morte, knowledge base, agendamento,
validadores de agente, pipeline completo com gates e relatórios. Nenhum chama
a API.

## Custos e modelo

Padrão: `claude-opus-5` com esforço `high` e adaptive thinking. O prompt de
sistema de cada agente é cacheado, então rodadas seguidas do mesmo agente leem
o cache em vez de reprocessar. Para reduzir custo, comece baixando o esforço
(`--effort medium`) antes de trocar de modelo.

## O que ainda depende de você

Por decisão de projeto (Camada 4 do master prompt), continuam sob supervisão
humana: a aprovação final de publicação, o corte de orçamento ou ferramenta, e
qualquer mudança de estratégia entre nichos. A integração com a API de
publicação do TikTok e a renderização em FFmpeg **não** estão implementadas —
o sistema entrega a shot list e o agendamento; a execução do render e do post
é o próximo passo. Ver `docs/ROADMAP.md`.
