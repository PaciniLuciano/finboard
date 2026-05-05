# Recomendações de Melhoria — Projeto Finboard (Fase 1)

Este documento resume as oportunidades de evolução técnica e funcional para o Finboard, com base na análise do código atual e do Briefing v1.0.

## 1. Performance e Concorrência (Gargalo de Latência)
*   **Problema:** Atualmente, a listagem de ativos e o cálculo de scores processam um item por vez. Chamadas sequenciais a APIs externas (Brapi, yfinance) tornam a interface lenta.
*   **Recomendação:**
    *   Implementar **async/await** (FastAPI) em todas as rotas de I/O.
    *   Utilizar `asyncio.gather` ou `ThreadPoolExecutor` no `scoring/engine.py` para calcular scores de múltiplos ativos em paralelo.
    *   No Radar, as chamadas devem ser em lote (batch) sempre que a API permitir (ex: Brapi suporta múltiplos tickers em uma URL).

## 2. Estratégia de Cache (Otimização de APIs)
*   **Problema:** O sistema consome APIs externas repetidamente para os mesmos dados.
*   **Recomendação:**
    *   Efetivar o uso da tabela `precos_cache`. O fluxo deve ser: `DB -> Cache (TTL de 15 min) -> API Externa`.
    *   Implementar cache para dados macro (Relatório Focus e Selic), que mudam com baixa frequência (semanal/diária).

## 3. Implementação do Scanner para o Radar
*   **Problema:** O briefing prevê o monitoramento de ~925 ativos, mas o código atual foca apenas na carteira do usuário.
*   **Recomendação:**
    *   Criar um **Worker/Scheduler** (usando `rocketry` ou `background tasks` do FastAPI) que rode o scanner nos ~925 ativos uma vez por dia (pós-fechamento).
    *   Salvar os resultados na tabela `scores` para que a tela Radar apenas consulte o banco de dados, garantindo carregamento instantâneo.

## 4. Refinamento do Motor de Scoring (V·M·Mac)
*   **Valuation (V):** Garantir que a lógica de "Margem de Segurança" (Preço Atual vs. Preço Justo) seja o coração do score V, conforme planejado.
*   **Momento (M):** No `momento.py`, integrar o cálculo de **Suporte e Resistência** e o **Volume Relativo** para dar mais peso à confirmação de tendência.
*   **Macro (Mac):** Automatizar a captura do viés (Hawkish/Dovish) através da análise da variação das projeções do Relatório Focus (se a Selic projetada subiu em relação à semana passada, o viés é negativo para ativos de risco).

## 5. Alinhamento com Objetivo de Rentabilidade
*   **Recomendação:** Criar um módulo de validação de "Prêmio de Risco". Para cada ativo de risco 4 (Ações), o sistema deve calcular se o Yield esperado supera o `CDI + 8,5%`. Se não superar, o Score Final deve ser penalizado ou um alerta de "Risco Desproporcional" deve ser gerado.

## 6. Arquitetura do Código
*   **API Routers:** Separar `main.py` em rotas menores (`/ativos`, `/scoring`, `/config`) usando `APIRouter`.
*   **Logs:** Substituir `print()` por `logging` para facilitar o monitoramento em ambiente de produção (Render/Cloud).
*   **Tratamento de Erros:** Em vez de retornar score 5.0 quando um dado falha, retornar um objeto de erro detalhado ou um "Confidence Score" baixo para o ativo.

## 7. Frontend e Visualização
*   **TradingView:** No backend, criar um endpoint `/history/{ticker}` que retorne os dados no formato exato esperado pela biblioteca `Lightweight Charts` (time, open, high, low, close).
*   **Cockpit:** Consolidar os dados de alocação (Pizza) e evolução no backend para evitar que o JavaScript precise fazer múltiplos cálculos pesados no navegador.
