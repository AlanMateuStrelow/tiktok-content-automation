# Roadmap

A Camada 4 do master prompt define quatro fases. O que está implementado é a
inteligência e o controle; o que falta é a execução física do vídeo.

## Fases

| Fase | O que é | Status |
|---|---|---|
| 1. Market Discovery | avaliar nichos, escolher os 5 melhores | `ci-system mission` |
| 2. Content Discovery | mapear formatos, hooks, temas por nicho | `ci-system trends` |
| 3. Piloto controlado | hipótese explícita, variações pequenas, medir | `ci-system hypotheses` + `cycle` |
| 4. Escala | só depois de evidência de formato, nicho, custo e monetização | bloqueado por dados |

**Não pule para a Fase 4.** Os critérios de escala são: formato vencedor,
nicho vencedor, audiência adequada, processo eficiente, custo aceitável,
monetização comprovada. Cada um deles é uma pergunta que o `learn` responde
com `DADOS_INSUFICIENTES` até haver amostra.

## Ordem de automação (a do master prompt, e onde estamos)

| # | Item | Estado |
|---|---|---|
| 1 | Script Architect + Video Editor | **pronto** (spec; falta render) |
| 2 | Publishing & Scheduling | **parcial** — agenda; falta postar |
| 3 | Low-Quality Detector + Quality Control | **pronto** |
| 4 | Algorithm Research | **pronto** — melhora com histórico |
| 5 | Analytics & Learning | **pronto** — depende de métricas reais |
| 6 | Market & Trend | **pronto** — mais valioso com canal performando |

## Próximos passos, em ordem de dependência

### 1. Render (FFmpeg) — desbloqueia tudo

A shot list já sai com timestamps, texto na tela, transições, queries de
B-roll e parâmetros de export. Falta o executor: baixar B-roll licenciado,
gerar narração (ElevenLabs ou equivalente), montar legendas sincronizadas,
compor e exportar 1080x1920.

Ponto de entrada: consumir `ShotList` da knowledge base.

### 2. Publicação via API

`Video.status` já tem `AGENDADO` → `PUBLICADO` e `scheduled_for`. Falta o
worker que posta na janela e grava `published_at`. Fila de retry e alerta por
falha de ferramenta são requisito do Agente 7.

### 3. Coleta automática de métricas

Substituir `ci-system ingest` manual por um coletor nas janelas 24h/72h/7d/30d.
O Agente 7 também pede monitoramento de sinal precoce nas primeiras 2h com
alerta se estiver anormalmente baixo.

### 4. Suporte a A/B na CLI

`Video` já tem `experiment_id` e `variant`, e `metric_samples` já filtra por
eles. Falta o comando que produz N vídeos marcados por grupo e compara.

### 5. Custo real por vídeo

`Metrics.cost_usd` hoje é preenchido à mão. Instrumentar o uso de tokens por
agente e somar com o custo de ferramentas fecha o cálculo de RECEITA/CUSTO que
o Agente 0 exige.

## O que permanece sob supervisão humana

Por decisão do master prompt, e até haver confiança medida:

- aprovação final de publicação (até o Agente 6 provar seu histórico);
- decisões de corte de orçamento ou de ferramenta;
- qualquer ajuste de estratégia entre nichos.
