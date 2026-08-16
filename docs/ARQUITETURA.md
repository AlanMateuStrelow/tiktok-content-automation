# Arquitetura

## Princípio de divisão: julgamento vs aritmética

A regra que organiza todo o código:

> Se duas execuções com a mesma entrada precisam dar a mesma resposta, é
> código. Se precisa de julgamento sobre linguagem, mercado ou narrativa, é
> prompt.

Por isso o LLM **nunca** calcula um score. Ele atribui notas por dimensão
(0–10) com justificativa; `scoring.py` faz a aritmética, a normalização e a
faixa de decisão. Consequência prática: dá para replicar qualquer decisão do
sistema sem chamar a API, e uma mudança de limiar aparece como diff no git em
vez de sumir dentro de um prompt.

## Os 8 agentes

| # | Agente | Papel | Onde |
|---|---|---|---|
| 0 | CEO / Orchestrator | encadeia, aplica gates, controla custo | `orchestrator.py` (código) |
| 1 | Market & Trend | NICHE SCORE (semanal) + angulos (diário) | `agents/market_trend.py` |
| 2 | Algorithm Research | auditoria pré-produção + hipóteses testáveis | `agents/algorithm_research.py` |
| 3 | Low-Quality Detector | gate de conceito, antes de produzir | `agents/low_quality_detector.py` |
| 4 | Script Architect | conceito + 4 hooks + roteiro final | `agents/script_architect.py` |
| 5 | Video Editor | shot list, B-roll, música, export | `agents/video_editor.py` |
| 6 | Quality Control | gate final, rejeita por padrão | `agents/quality_control.py` |
| 7 | Publishing & Scheduling | caption/hashtags (LLM) + janela/buffer (código) | `agents/publishing.py` + `scheduler.py` |
| 8 | Analytics & Learning | mede, roda A/B, vira conhecimento | `agents/analytics_learning.py` |

Cada agente é `Agent(name, prompt_file, schema, validate)`:

- **prompt** — o julgamento, em `prompts/*.md`, escrito em inglês porque o
  conteúdo é para EUA/CA/UK/AU.
- **schema** — JSON Schema com `additionalProperties: false` e `required` em
  todo objeto, exigência do structured outputs. A saída chega já parseada.
- **validate** — regras da Camada 1 que schema nenhum expressa: hook começando
  com "did you know", roteiro sem número, B-roll genérico, QC aprovando com
  check reprovado. Uma violação levanta `AgentError` e o pipeline registra.

O preâmbulo da Camada 0 (hierarquia de decisão, rótulos epistêmicos,
anti-genericidade, compliance) é injetado em todo prompt de sistema por
`agents/base.py`.

## Fluxo de produção

`orchestrator.produce()` roda a esteira e devolve um `PipelineResult` com o log
por estágio. Ordem e critério de parada:

1. **CONTENT SCORE < 70** → rejeita antes de qualquer chamada de produção.
2. **Agente 4 → Agente 3**, em loop. Reprovou? O feedback devolvido ao Agente 4
   é o apontamento exato (categoria, detalhe, segundo previsto de abandono),
   não "reescreva". Até `max_rewrite_attempts` tentativas.
3. **Agente 2** audita. Risco de shadowban acima de médio, potencial abaixo de
   5, ou mudança obrigatória pendente → rejeita antes de gastar edição.
4. **Agente 5** gera a shot list.
5. **Agente 7** escreve caption e hashtags — antes do QC, para que o Agente 6
   possa checá-las.
6. **Agente 6** decide. Qualquer check reprovado, ou originalidade abaixo do
   mínimo → volta.
7. **Agendamento**: próximo slot livre na janela do canal, no fuso do público.
   Se o vídeo é parecido demais com os últimos, ele é empurrado um slot — não
   rejeitado.

Cada etapa vira um `Stage(agent, status, detail)`. Se um vídeo morreu, dá para
apontar em qual gate e por quê.

## Persistência

SQLite (`knowledge_base.py`): um arquivo, sem servidor, fácil de versionar em
backup. Tabelas: `niches`, `opportunities`, `scripts`, `shot_lists`, `videos`,
`metrics`, `experiments`, `learnings`, `kill_log`, `pipeline_runs`.

Cada linha guarda as colunas usadas em filtro **e** o payload JSON completo —
assim consultas são rápidas sem perder nada do que o agente devolveu.

`metric_samples()` aceita filtro por campo do vídeo (`hook_type`, `format`,
`bucket`, `variant`, `experiment_id`) contra uma allowlist explícita. É o que
alimenta o sistema de morte e as comparações A/B.

## Camada de modelo

`llm.py` expõe um protocolo `LLM` com um método: `json(system, user, schema)`.

- `AnthropicLLM` — Messages API com `output_config.format` (structured
  outputs), adaptive thinking, esforço configurável, e `cache_control` no
  prompt de sistema. Acima de 16k tokens de saída usa streaming. Trata
  `stop_reason == "refusal"` como erro explícito, nunca como resposta vazia.
- `DryRunLLM` — devolve um objeto mínimo válido contra o schema, ou um override
  de `demo_data.py`. Todo o encanamento roda sem rede.

Os testes usam `DryRunLLM` com overrides. Nenhum teste chama a API.

## O que ainda não existe

Renderização (FFmpeg), publicação via API do TikTok, e coleta automática de
métricas. Hoje a fronteira é: o sistema entrega shot list + caption +
agendamento, e recebe métricas por `ci-system ingest`. Ver `ROADMAP.md`.
