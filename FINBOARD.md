# Finboard — Documentação da Lógica do App

## Visão Geral

Finboard é um painel pessoal de investimentos. O backend é uma API REST em **FastAPI** com banco **SQLite**. O frontend é servido como arquivos estáticos em `/frontend`. O servidor sobe com:

```
python -m uvicorn backend.main:app --reload
```

Acesso: `http://localhost:8000` | Docs interativos: `http://localhost:8000/docs`

---

## Arquitetura

```
finboard/
├── backend/
│   ├── main.py              ← entrada da app, registra routers, evento de startup
│   ├── database.py          ← modelos SQLAlchemy + função criar_banco()
│   ├── models_extra.py      ← tabela scores_cache
│   ├── scorer_job.py        ← job background que recalcula scores a cada 30min
│   ├── ssl_patch.py         ← patch curl_cffi para ambientes com proxy self-signed
│   ├── data/
│   │   ├── brapi.py         ← fonte de preços (brapi.dev + yfinance + câmbio + ibovespa)
│   │   ├── cache.py         ← cache de preços no SQLite (TTL 15 min)
│   │   ├── history.py       ← histórico de preços
│   │   ├── tesouro.py       ← dados Tesouro Direto
│   │   └── yfinance_client.py
│   ├── scoring/
│   │   ├── engine.py        ← orquestra valuation + momento + macro → score final
│   │   ├── valuation.py     ← P/L, P/VP, DY, ROE, Margem por classe de ativo
│   │   ├── momento.py       ← MM50, MM200, RSI, retorno 6m/12m
│   │   ├── macro.py         ← regime macro (DEFENSIVO/NEUTRO/AGRESSIVO) via BACEN
│   │   ├── premio_risco.py  ← yield esperado vs CDI benchmark
│   │   └── utils.py         ← normalizar_dy(), converter_numpy()
│   └── routers/
│       ├── ativos.py        ← CRUD carteira + compra/venda
│       ├── carteira.py      ← resumo patrimonial
│       ├── renda_fixa.py    ← CRUD renda fixa
│       ├── mercado.py       ← preços, ibovespa, câmbio, histórico
│       ├── watchlist.py     ← CRUD watchlist
│       ├── scoring.py       ← endpoints de score + radar + regime macro
│       ├── dividendos.py    ← CRUD + importação via yfinance + retorno total
│       ├── importexport.py  ← exportar/importar carteira e watchlist (CSV/XLSX)
│       ├── config.py        ← configurações de Selic prevista
│       └── premio_risco.py  ← endpoint yield vs CDI de toda a carteira
```

---

## Banco de Dados (SQLite — `finboard.db`)

| Tabela | Descrição |
|---|---|
| `ativos` | Carteira variável: ações, FIIs, ETFs, etc. |
| `renda_fixa` | CDB, LCI, LCA, LC — com indexador, taxa, vencimento |
| `precos_cache` | Cache de cotações com TTL de 15 min |
| `scores` | Histórico de scores (tabela legada) |
| `scores_cache` | Cache de scores calculados pelo job (carteira e watchlist) |
| `alertas` | Alertas gerados pela app |
| `configuracoes` | Chave-valor: previsões de Selic, etc. |
| `historico_agente` | Histórico de perguntas/respostas de agente IA |
| `watchlist` | Ativos monitorados fora da carteira |
| `dividendos` | Proventos recebidos por ticker |

### Soft delete
Ativos e renda fixa usam campo `ativo = False` para "remover" sem apagar do banco. Reativar recadastra sem duplicar.

---

## Startup (main.py)

Na inicialização da FastAPI (`@app.on_event("startup")`):
1. **`criar_banco()`** — cria todas as tabelas SQLAlchemy se não existirem.
2. **`iniciar_job()`** — sobe thread daemon que roda o scoring a cada 30 min.

---

## Fontes de Dados de Preço

### Roteador inteligente (`brapi.py → buscar_preco`)

| Ativo | Fonte primária | Fallback |
|---|---|---|
| ETFs BR (BOVA11, IVVB11, etc.) | brapi.dev | yfinance |
| Ações BR e FIIs | yfinance (`TICKER.SA`) | brapi.dev |
| ETFs / ações EUA | yfinance (ticker direto) | — |
| Câmbio USD/BRL | yfinance (`USDBRL=X`) | — |
| Ibovespa | yfinance (`^BVSP`) | — |

### Cache de preços (`cache.py`)
- TTL: **15 minutos** — verifica tabela `precos_cache` antes de chamar a API.
- UPSERT: atualiza o registro existente ou insere novo.
- Limpeza manual disponível via `invalidar_cache(ticker)`.

---

## Sistema de Scoring

Cada ativo recebe um **score final de 0 a 10** composto por três dimensões:

```
score_final = (valuation × 0.40) + (momento × 0.30) + (macro × 0.30)
```

### 1. Valuation (`scoring/valuation.py`)

Fonte: `yfinance.Ticker.info`

**Ação (max 10 pontos):**
| Indicador | Critério | Pontos |
|---|---|---|
| P/L | < 8 | 3 |
| P/L | 8–12 | 2 |
| P/L | 12–20 | 1 |
| P/VP | < 1 | 2 |
| P/VP | 1–2 | 1 |
| DY | 6%–15% | 2 |
| DY | 3%–6% | 1 |
| DY | > 15% (suspeito) | 1 |
| ROE | > 20% | 2 |
| ROE | 10%–20% | 1 |
| Margem líquida | > 10% | 1 |

**FII (max 8 pontos):**
| Indicador | Critério | Pontos |
|---|---|---|
| P/VP | < 0.85 | 4 |
| P/VP | 0.85–0.95 | 3 |
| P/VP | 0.95–1.05 | 2 |
| P/VP | 1.05–1.15 | 1 |
| DY | > 10% | 4 |
| DY | 8%–10% | 3 |
| DY | 6%–8% | 2 |
| DY | 4%–6% | 1 |

**ETF BR/EUA (max 6 pontos):**
| Indicador | Critério | Pontos |
|---|---|---|
| P/L | < 15 | 3 |
| P/L | 15–22 | 2 |
| P/L | 22–30 | 1 |
| DY | > 3% | 3 |
| DY | 1.5%–3% | 2 |
| DY | 0.5%–1.5% | 1 |

Score = `(pontos / max_pontos) × 10`, arredondado em 1 decimal.

> **Normalização do DY:** yfinance retorna decimal para ativos EUA (0.1326) e percentual para BR (13.26). A função `normalizar_dy()` unifica: se `raw > 1` já é percentual, senão multiplica por 100.

### 2. Momento (`scoring/momento.py`)

Fonte: `yfinance.Ticker.history(period="1y", auto_adjust=False)`

> `auto_adjust=False` evita NaN em FIIs BR que têm dividendos mensais — o ajuste automático falha nesses casos e propaga NaN em todo o histórico.

| Indicador | Critério | Pontos |
|---|---|---|
| MM200 | Preço acima da média de 200 dias | 3 |
| MM50 | Preço acima da média de 50 dias | 2 |
| RSI | 40–65 (zona saudável) | 2 |
| RSI | 30–40 ou 65–70 | 1 |
| RSI | < 30 ou > 70 | 0 |
| Retorno 6m | > 10% | 2 |
| Retorno 6m | 0–10% | 1 |
| Retorno 12m | > 0% | 1 |

- **Max pontos dinâmico:** 10 com MM200 disponível, 7 sem (ativos com menos de 200 dias de histórico).
- Score = `(pontos / max_pontos) × 10`.

### 3. Macro (`scoring/macro.py`)

Fontes: API BACEN SGS e BACEN Olinda.

**Dados consultados:**
| Dado | Série/endpoint |
|---|---|
| Selic atual | SGS série 432 |
| IPCA 12m acumulado | SGS série 13522 |
| Selic esperada (Focus) | Olinda ExpectativasMercadoAnuais |

**Cache em memória:** TTL 6 horas. Evita chamadas repetidas à API do BACEN.

**Determinação do regime:**

1. Pontuação baseada em Selic atual:
   - > 13% → −2 | 11–13% → −1 | < 9% → +2 | outros → +1
2. Variação Selic esperada vs atual (Focus):
   - Queda > 1.5% → +2 | queda 0.5–1.5% → +1 | alta > 0.5% → −1
3. IPCA:
   - < 4% → +1 | > 6% → −1

| Pontuação total | Regime |
|---|---|
| ≥ 2 | **AGRESSIVO** (renda variável favorecida) |
| −1 a 1 | **NEUTRO** |
| ≤ −1 | **DEFENSIVO** (renda fixa favorecida) |

**Score macro por classe e regime:**

| Classe | DEFENSIVO | NEUTRO | AGRESSIVO |
|---|---|---|---|
| ACAO | 4.0 | 6.0 | 8.5 |
| FII_PAPEL | 8.5 | 7.0 | 5.5 |
| FII_TIJOLO | 4.0 | 6.0 | 8.5 |
| ETF_BR | 4.5 | 6.0 | 8.0 |
| ETF_EUA | 6.0 | 6.5 | 7.5 |
| TESOURO_IPCA | 9.0 | 7.5 | 6.0 |
| TESOURO_SELIC | 8.0 | 6.5 | 4.5 |
| CDB | 8.5 | 7.0 | 5.0 |

**Ajuste setorial** (somado ao score base):

| Setor | DEFENSIVO | NEUTRO | AGRESSIVO |
|---|---|---|---|
| BANCO | +1.5 | +0.5 | −1.0 |
| SEGURO | +1.0 | +0.5 | −0.5 |
| VAREJO | −1.5 | −0.5 | +1.5 |
| CONSTRUTORA | −1.5 | −0.5 | +1.5 |
| TECH | −1.0 | 0.0 | +1.0 |
| COMMODITY | 0.0 | +0.5 | +0.5 |
| FII_PAPEL | +1.5 | +0.5 | −1.0 |

Mapeamento ticker→setor usa os primeiros 4 caracteres (ex: `ITUB` → `BANCO`).

---

## Job de Scoring (`scorer_job.py`)

- Roda em **thread daemon** separada do loop do FastAPI.
- Intervalo: **30 minutos**.
- Calcula scores para toda a **carteira** e toda a **watchlist**.
- Apaga o cache anterior da origem antes de gravar o novo (DELETE + INSERT).
- Sinal derivado do score final:
  - ≥ 7.0 → **Forte**
  - 5.5–6.9 → **Neutro**
  - < 5.5 → **Fraco**
- Paralelismo: semáforo de 8 tasks simultâneas via `asyncio.Semaphore(8)`.

---

## Prêmio de Risco (`scoring/premio_risco.py`)

Compara o yield esperado do ativo contra o CDI como benchmark.

```
CDI ≈ Selic − 0.1%
benchmark = CDI + prêmio_mínimo_por_classe
```

| Classe | Prêmio mínimo exigido |
|---|---|
| ACAO | +8.5% |
| FII | +3.0% |
| ETF_BR | +5.0% |
| ETF_EUA | +8.0% |
| TESOURO | +0.0% |

**Yield esperado:**
- FII: usa DY se disponível, senão `(1/P/L) × 100`
- Outros: usa `(1/P/L) × 100` se disponível, senão DY

**Sinal:**
- `yield ≥ benchmark` → **ATRATIVO**
- `yield ≥ CDI` → **NEUTRO**
- `yield < CDI` → **ABAIXO_CDI**

Para renda fixa, o yield efetivo é calculado diretamente (CDI × taxa%, IPCA + taxa%, ou prefixado).

Cache em memória: TTL **30 minutos** por ticker.

---

## Endpoints da API

### Ativos (`/ativos`)
| Método | Rota | Descrição |
|---|---|---|
| POST | `/ativos` | Cadastra ativo (reativa se estava inativo) |
| GET | `/ativos` | Lista carteira com preço atual, retorno %, retorno R$, câmbio |
| PUT | `/ativos/{ticker}` | Edita dados cadastrais |
| DELETE | `/ativos/{ticker}` | Soft delete (ativo=False) |
| POST | `/ativos/compra` | Registra nova compra — recalcula preço médio ponderado |
| POST | `/ativos/venda` | Registra venda — remove ativo se quantidade zerar |
| PATCH | `/ativos/{ticker}/preco` | Atualiza preço manualmente no cache |

**Cálculo de preço médio na compra:**
```
novo_pm = (qtd_anterior × pm_anterior + qtd_nova × preco_compra) / (qtd_anterior + qtd_nova)
```

**Conversão de moeda em `/ativos` (GET):**
- Ativos EUA: preço e preço médio convertidos para BRL via câmbio USD/BRL.
- Retorno % calculado na moeda original (USD vs USD), sem distorção cambial.

### Carteira (`/carteira`)
| Método | Rota | Descrição |
|---|---|---|
| GET | `/carteira/resumo` | Patrimônio total, retorno total R$ e %, breakdown por classe |

Renda fixa entra com `valor_atual = valor_aplicado` (sem marcação a mercado).

### Renda Fixa (`/renda-fixa`)
| Método | Rota | Descrição |
|---|---|---|
| POST | `/renda-fixa` | Cadastra título |
| GET | `/renda-fixa` | Lista todos os ativos |

### Mercado
| Método | Rota | Descrição |
|---|---|---|
| GET | `/mercado/preco/{ticker}` | Cotação com cache |
| GET | `/mercado/ibovespa` | Ibovespa (preço + variação) |
| GET | `/mercado/cambio` | USD/BRL atual |
| GET | `/history/{ticker}` | Histórico OHLCV (parâmetro `periodo`: `1y`, `6m`, etc.) |

### Watchlist
| Método | Rota | Descrição |
|---|---|---|
| GET | `/watchlist` | Lista watchlist ativa |
| POST | `/watchlist` | Adiciona ticker |
| DELETE | `/watchlist/{ticker}` | Remove (soft delete) |

### Scoring e Radar
| Método | Rota | Descrição |
|---|---|---|
| GET | `/scoring/{ticker}` | Score de um ativo em tempo real |
| GET | `/scoring/carteira/todos` | Scores de toda a carteira em tempo real |
| GET | `/macro/regime` | Regime macro atual (BACEN) |
| POST | `/macro/invalidar-cache` | Força recálculo macro na próxima chamada |
| GET | `/radar` | Scores da carteira (ou watchlist) do cache do job — `?origem=carteira\|watchlist&forcar=true` |
| GET | `/radar/watchlist` | Atalho para radar da watchlist em tempo real |

### Dividendos
| Método | Rota | Descrição |
|---|---|---|
| POST | `/dividendos` | Registra provento manualmente |
| GET | `/dividendos` | Lista todos os proventos |
| GET | `/dividendos/{ticker}` | Proventos de um ticker |
| POST | `/dividendos/importar/{ticker}` | Importa histórico via yfinance (filtra por data de compra) |
| POST | `/dividendos/importar-todos` | Importa histórico de toda a carteira |
| GET | `/retorno-total/{ticker}` | Retorno de cota + dividendos recebidos |

### Import / Export
| Método | Rota | Descrição |
|---|---|---|
| GET | `/exportar/carteira` | Baixa carteira + dividendos (`?formato=csv\|xlsx`) |
| GET | `/exportar/watchlist` | Baixa watchlist |
| POST | `/importar/carteira` | Importa CSV/XLSX (upsert — atualiza se ticker já existe) |
| POST | `/importar/watchlist` | Importa CSV/XLSX de watchlist |

**Formato do arquivo de importação de carteira:**

| Coluna | Obrigatória | Descrição |
|---|---|---|
| `ticker/emissor` | sim | Ticker do ativo ou nome do emissor RF |
| `classe` | sim | ACAO, FII, ETF_BR, ETF_EUA, RENDA_FIXA |
| `quantidade/valor` | sim | Quantidade de cotas ou valor aplicado |
| `preco_medio/taxa` | sim | Preço médio ou taxa % |
| `secao` | não | "RENDA FIXA" sinaliza linha como renda fixa |
| `mercado` | não | BR (padrão) ou EUA |
| `indexador` | não | CDI, IPCA, PREFIXADO (para RF) |
| `liquidez` | não | DIARIA ou VENCIMENTO (para RF) |
| `data_compra/vencimento` | não | ISO 8601 ou formato Excel |

### Prêmio de Risco
| Método | Rota | Descrição |
|---|---|---|
| GET | `/premio-risco` | Yield esperado vs CDI de toda a carteira + renda fixa |

### Configurações
| Método | Rota | Descrição |
|---|---|---|
| GET | `/configuracoes` | Lê todas as configurações salvas |
| POST | `/configuracoes` | Salva projeções de Selic (12m, pessimista, otimista) |

---

## Dependências Principais

| Biblioteca | Uso |
|---|---|
| `fastapi` + `uvicorn` | Servidor web e API |
| `sqlalchemy` | ORM SQLite |
| `yfinance` | Cotações, histórico, DY, P/L, P/VP, ROE, câmbio |
| `httpx` | Chamadas async à BACEN e brapi.dev |
| `pandas` | Cálculo de médias móveis, RSI, retornos; export Excel/CSV |
| `curl_cffi` | Evita bloqueio do yfinance em ambientes com proxy |
| `openpyxl` | Escrita de arquivos .xlsx |
| `python-dotenv` | Carrega `BRAPI_TOKEN` do `.env` |

---

## Variáveis de Ambiente

| Variável | Obrigatória | Descrição |
|---|---|---|
| `BRAPI_TOKEN` | Não | Token da brapi.dev — sem ele ETFs BR usam yfinance como fallback |

---

## Observações Técnicas

- **SSL desabilitado:** `httpx.AsyncClient(verify=False)` nas chamadas ao BACEN Olinda e brapi.dev — contorno para ambientes corporativos com proxy self-signed.
- **Encoding Windows:** O terminal Windows usa cp1252 por padrão. Caracteres Unicode fora desse range (ex: `✓`) geram `UnicodeEncodeError` e impedem o startup. Use `[OK]` ou configure `PYTHONIOENCODING=utf-8`.
- **Job vs tempo real:** `/radar` serve do cache do job (30min). `/scoring/{ticker}` e `/scoring/carteira/todos` calculam em tempo real mas são mais lentos.
- **Semáforo no scoring em lote:** Máximo 8 tickers calculados em paralelo para não sobrecarregar a API do yfinance.
