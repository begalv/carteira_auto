# Referencia de API — carteira_auto

Documentacao completa de todas as classes publicas, metodos, atributos e estruturas de dados do sistema `carteira_auto`.

Organizado pelo fluxo de dados: Core -> Models -> Config -> Fetchers -> Lake -> I/O -> Nodes -> Analyzers -> Alerts -> Utils -> CLI -> Registry.

---

## 1. Core — Motor do Sistema

Modulo: `carteira_auto.core.engine`

### PipelineContext

Container para dados compartilhados entre nodes. Herda de `dict`.

| Metodo / Propriedade | Tipo | Descricao |
|---|---|---|
| `get_typed(key, expected_type)` | `Any` | Obtem valor com verificacao de tipo. Levanta `TypeError` se incompativel. |
| `errors` (property) | `dict[str, str]` | Erros registrados em `ctx["_errors"]` durante execucao. |
| `has_errors` (property) | `bool` | `True` se houve erros durante a execucao. |

```python
ctx = PipelineContext()
ctx["portfolio"] = portfolio
portfolio = ctx.get_typed("portfolio", Portfolio)
```

### Node (ABC)

Bloco de execucao do DAG. Cada subclasse declara `name`, `dependencies` e implementa `run()`.

| Atributo / Metodo | Tipo | Descricao |
|---|---|---|
| `name` | `str` | Identificador unico do node. |
| `dependencies` | `list[str]` | Nomes dos nodes predecessores. |
| `run(ctx)` | `PipelineContext` | *Abstrato.* Executa logica e retorna contexto atualizado. |
| `__init_subclass__(**kwargs)` | `None` | Garante que cada subclasse tenha sua propria copia de `dependencies`. |

```python
class MeuNode(Node):
    name = "meu_node"
    dependencies = ["load_portfolio"]

    def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx["resultado"] = calcular(ctx["portfolio"])
        return ctx
```

### DAGEngine

Engine que registra nodes e resolve dependencias via topological sort (Kahn's Algorithm).

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `__init__` | `fail_fast: bool = False` | `None` | Se `fail_fast=True`, para no primeiro erro. |
| `register` | `node: Node` | `None` | Registra um node. Substitui se ja existe. |
| `register_many` | `nodes: list[Node]` | `None` | Registra multiplos nodes. |
| `get_node` | `name: str` | `Node` | Retorna node pelo nome. Levanta `NodeNotFoundError`. |
| `list_nodes` | — | `list[str]` | Lista nomes de todos os nodes registrados. |
| `resolve` | `target: str` | `list[Node]` | Resolve dependencias e retorna ordem de execucao. |
| `dry_run` | `target: str` | `list[str]` | Mostra plano de execucao sem executar. |
| `run` | `target: str, ctx: PipelineContext \| None` | `PipelineContext` | Resolve e executa o pipeline. Decorado com `@log_execution` e `@timer`. |

```python
engine = DAGEngine(fail_fast=True)
engine.register(LoadPortfolioNode())
engine.register(FetchPortfolioPricesNode())

plan = engine.dry_run("fetch_portfolio_prices")
# ["load_portfolio", "fetch_portfolio_prices"]

ctx = engine.run("fetch_portfolio_prices")
```

### Excecoes

| Excecao | Descricao |
|---|---|
| `NodeExecutionError(node_name, original_error)` | Erro durante execucao de um node. Possui `node_name` e `original_error`. |
| `CycleDetectedError` | Ciclo detectado no grafo de dependencias. |
| `MissingDependencyError` | Node depende de outro nao registrado. |
| `NodeNotFoundError` | Node nao encontrado no engine. |

### Result — Ok[T] / Err[T]

Modulo: `carteira_auto.core.result`

Tipo para tratamento explicito de erros, inspirado no Rust.

| Classe | Atributos | Metodos |
|---|---|---|
| `Ok[T]` | `value: T` | `is_ok() -> True`, `is_err() -> False`, `unwrap() -> T`, `unwrap_or(default) -> T` |
| `Err[T]` | `error: str`, `details: dict = {}` | `is_ok() -> False`, `is_err() -> True`, `unwrap() -> raises ValueError`, `unwrap_or(default) -> default` |

Type alias: `Result = Ok[T] | Err[T]`

```python
from carteira_auto.core.result import Result, Ok, Err

def calcular(dados) -> Result[float]:
    try:
        return Ok(dados.mean())
    except Exception as e:
        return Err(str(e))

r = calcular(df)
valor = r.unwrap_or(0.0)
```

---

## 2. Models — Estruturas de Dados

Modulo: `carteira_auto.core.models`

Todos os modelos utilizam Pydantic `BaseModel` com validacao automatica.

### Asset

Ativo na carteira — mapeia uma linha da aba "Carteira".

| Campo | Tipo | Descricao | Validacao |
|---|---|---|---|
| `ticker` | `str` | Codigo do ativo (ex: "PETR4") | Nao vazio (strip + check) |
| `nome` | `str` | Nome do ativo / gestora | Nao vazio |
| `classe` | `str \| None` | Classe do ativo (Acoes, Renda Fixa, etc.) | — |
| `setor` | `str \| None` | Setor | — |
| `subsetor` | `str \| None` | Subsetor | — |
| `segmento` | `str \| None` | Segmento | — |
| `pct_meta` | `float \| None` | % meta de alocacao | >= 0 |
| `valor_meta` | `float \| None` | Valor meta em R$ | >= 0 |
| `pct_atual` | `float \| None` | % atual na carteira | >= 0 |
| `pct_inicial` | `float \| None` | % inicial quando comprou | >= 0 |
| `posicao_atual` | `float \| None` | Valor da posicao atual R$ | >= 0 |
| `preco_posicao` | `float \| None` | Preco de aquisicao R$ | >= 0 |
| `valorizacao` | `float \| None` | Valorizacao absoluta R$ | — |
| `valorizacao_pct` | `float \| None` | Valorizacao percentual | — |
| `proventos_recebidos` | `float \| None` | Total de proventos R$ | — |
| `diferenca` | `float \| None` | Diferenca meta vs atual R$ | — |
| `rentabilidade` | `float \| None` | Rentabilidade individual | — |
| `rentabilidade_proporcional` | `float \| None` | Rentabilidade proporcional a carteira | — |
| `preco_atual` | `float \| None` | Preco de mercado atual R$ | >= 0 |
| `preco_medio` | `float \| None` | Preco medio de compra R$ | >= 0 |
| `n_cotas_atual` | `float \| None` | Numero de cotas/acoes | >= 0 |

**Campos fundamentalistas** — populados via Yahoo Finance (`get_batch_info`), nao pela planilha Excel.

| Campo | Tipo | Descricao | Validacao |
|---|---|---|---|
| **Valuation** | | | |
| `p_l` | `float \| None` | Preco/Lucro (P/E) — vezes | — (pode ser negativo) |
| `p_vp` | `float \| None` | Preco/Valor Patrimonial (P/BV) — vezes | — |
| `ev_ebitda` | `float \| None` | EV/EBITDA — vezes | — |
| `dy_12m` | `float \| None` | Dividend Yield 12m — % a.a. | — |
| `market_cap` | `float \| None` | Capitalizacao de mercado — R$ MM | — |
| **Qualidade** | | | |
| `roe` | `float \| None` | Return on Equity — % a.a. | — (pode ser negativo) |
| `roa` | `float \| None` | Return on Assets — % a.a. | — |
| `margem_liquida` | `float \| None` | Margem Liquida — % | — (pode ser negativo) |
| `margem_ebitda` | `float \| None` | Margem EBITDA — % | — |
| **Crescimento** | | | |
| `receita_liquida` | `float \| None` | Receita Liquida — R$ MM (ultimos 12m) | — |
| `ebitda` | `float \| None` | EBITDA — R$ MM (ultimos 12m) | — |
| `lpa` | `float \| None` | Lucro por Acao — R$ (ultimos 12m) | — |
| `vpa` | `float \| None` | Valor Patrimonial por Acao — R$ | — |
| `cagr_receita_5a` | `float \| None` | CAGR Receita 5 anos — % a.a. | — |
| **Endividamento** | | | |
| `divida_liquida_ebitda` | `float \| None` | Divida Liquida/EBITDA — vezes | — (negativo = caixa liquido) |
| **Mercado** | | | |
| `beta_5a` | `float \| None` | Beta 5 anos vs IBOV — adimensional | — |
| `free_float` | `float \| None` | Free Float — % | — |
| `liquidez_media_diaria` | `float \| None` | Liquidez Media Diaria — R$ MM | — |

```python
asset = Asset(ticker="PETR4", nome="Petrobras", preco_atual=38.50)
# Com dados fundamentalistas (populados por FundamentalsNode futuro):
asset = Asset(ticker="ITUB4", nome="Itau", p_l=8.5, roe=19.5, dy_12m=5.3)
```

### SoldAsset

Ativo vendido — mapeia uma linha da aba "Vendas".

| Campo | Tipo | Descricao | Validacao |
|---|---|---|---|
| `ticker` | `str` | Codigo do ativo | Nao vazio |
| `nome` | `str` | Nome do ativo | Obrigatorio |
| `classe` | `str \| None` | Classe | — |
| `setor` | `str \| None` | Setor | — |
| `valor_venda` | `float \| None` | Valor total da venda R$ | — |
| `preco_posicao` | `float \| None` | Preco de aquisicao R$ | >= 0 |
| `valorizacao` | `float \| None` | Valorizacao R$ | — |
| `valorizacao_pct` | `float \| None` | Valorizacao percentual | — |
| `proventos_recebidos` | `float \| None` | Proventos recebidos R$ | — |
| `diferenca` | `float \| None` | Diferenca R$ | — |
| `rentabilidade` | `float \| None` | Rentabilidade do ativo | — |
| `preco_na_venda` | `float \| None` | Preco no momento da venda R$ | >= 0 |
| `preco_medio_compra` | `float \| None` | Preco medio de compra R$ | >= 0 |
| `n_cotas_vendidas` | `float \| None` | Cotas vendidas | >= 0 |
| `posicao_ativa` | `bool \| None` | Se o ativo ainda esta em carteira | — |
| `mes` | `str \| None` | Mes da venda | — |

### Portfolio

Estado completo da carteira num ponto no tempo.

| Campo | Tipo | Descricao | Validacao |
|---|---|---|---|
| `assets` | `list[Asset]` | Lista de ativos | Nao vazio (minimo 1) |
| `sold_assets` | `list[SoldAsset]` | Vendas realizadas | Default: `[]` |

```python
portfolio = Portfolio(assets=[asset1, asset2], sold_assets=[venda1])
```

### PortfolioMetrics

Metricas consolidadas da carteira.

| Campo | Tipo | Descricao |
|---|---|---|
| `total_value` | `float` | Valor total da carteira R$ |
| `total_cost` | `float` | Custo total R$ |
| `total_return` | `float` | Retorno absoluto R$ |
| `total_return_pct` | `float` | Retorno percentual |
| `dividend_yield` | `float \| None` | DY da carteira |
| `allocations` | `list[AllocationResult]` | Alocacao por classe |

### RiskMetrics

Metricas de risco da carteira — calculadas sobre historico de 5 anos.

| Campo | Tipo | Descricao | Unidade |
|---|---|---|---|
| `volatility` | `float \| None` | Volatilidade anualizada (desvio padrao) | % a.a. |
| `var_95` | `float \| None` | Value-at-Risk 95% (perda diaria maxima esperada) | % |
| `var_99` | `float \| None` | Value-at-Risk 99% (perda diaria maxima esperada) | % |
| `sharpe_ratio` | `float \| None` | Sharpe ratio anualizado (retorno exc. / vol.) | adimensional |
| `max_drawdown` | `float \| None` | Maximo drawdown (queda pico a vale) | % |
| `beta` | `float \| None` | Beta contra IBOV (sensibilidade ao mercado) | adimensional |

| Metodo | Retorno | Descricao |
|---|---|---|
| `is_complete()` | `bool` | `True` se todas as metricas foram calculadas. |

### MarketMetrics

Metricas de benchmarks de mercado — periodo padrao de 5 anos.

| Campo | Tipo | Descricao | Fonte |
|---|---|---|---|
| `ibov_return` | `float \| None` | Retorno total IBOV — % acumulado 5a | Yahoo `^BVSP` |
| `ifix_return` | `float \| None` | Retorno total IFIX (FIIs) — % acumulado 5a | Yahoo `IFIX.SA` |
| `cdi_return` | `float \| None` | CDI acumulado — % (composicao de taxas % a.d.) | BCB SGS 12 |
| `sp500_return` | `float \| None` | Retorno total S&P 500 em USD — % acumulado 5a | Yahoo `^GSPC` |
| `dolar_retorno` | `float \| None` | Variacao USD/BRL — % acumulado 5a | Yahoo `BRL=X` |
| `ouro_retorno` | `float \| None` | Variacao ouro em USD — % acumulado 5a | Yahoo `GC=F` |
| `selic_retorno` | `float \| None` | Selic acumulada — % (composicao diaria da meta) | BCB SGS 432 |
| `brl_usd` | `float \| None` | Taxa cambio BRL/USD corrente — R$ por USD | BCB SGS 10813 |

### MacroContext

Contexto macroeconomico consolidado — indicadores BCB e IBGE.

| Campo | Tipo | Descricao | Fonte |
|---|---|---|---|
| **Taxas de juros** | | | |
| `selic` | `float \| None` | Taxa Selic meta — % a.a. | BCB SGS 432 (COPOM ~8x/ano) |
| `cdi` | `float \| None` | CDI acumulado 12m — % a.a. (composicao de % a.d.) | BCB SGS 12 (diario) |
| `poupanca` | `float \| None` | Rendimento poupanca — % a.m. | BCB SGS 25 (mensal) |
| `tr` | `float \| None` | Taxa Referencial — % a.m. | BCB SGS 226 (mensal) |
| **Inflacao** | | | |
| `ipca` | `float \| None` | IPCA acumulado 12m — % | BCB SGS 433 (mensal) |
| `igpm` | `float \| None` | IGP-M acumulado 12m — % | BCB SGS 189 (mensal) |
| `inpc` | `float \| None` | INPC acumulado 12m — % | BCB SGS 188 (mensal) |
| **Cambio** | | | |
| `cambio` | `float \| None` | Dolar PTAX compra — R$/USD | BCB SGS 10813 (dias uteis) |
| `dolar_ptax_venda` | `float \| None` | Dolar PTAX venda — R$/USD | BCB SGS 1 (dias uteis) |
| **Atividade economica** | | | |
| `pib_growth` | `float \| None` | PIB variacao % vs mesmo trim. ano anterior | IBGE SIDRA 5932 (trimestral) |
| `desocupacao` | `float \| None` | Taxa de desocupacao PNAD — % | IBGE SIDRA 6381 (trimestral) |
| **Sumario** | | | |
| `summary` | `str \| None` | Sumario textual gerado automaticamente | — |

### AllocationResult

| Campo | Tipo | Descricao |
|---|---|---|
| `asset_class` | `str` | Classe do ativo |
| `current_pct` | `float` | % atual |
| `target_pct` | `float` | % meta |
| `deviation` | `float` | Desvio (atual - meta) |
| `action` | `Literal["comprar", "vender", "manter"] \| None` | Acao recomendada |

### RebalanceRecommendation

| Campo | Tipo | Descricao |
|---|---|---|
| `ticker` | `str` | Ativo |
| `action` | `Literal["comprar", "vender"]` | Acao |
| `quantity` | `float \| None` | Quantidade de cotas |
| `value` | `float \| None` | Valor da operacao R$ |
| `reason` | `str \| None` | Motivo |

### CurrencyMetrics

Metricas cambiais — calculadas pelo CurrencyAnalyzer.

| Campo | Tipo | Descricao | Fonte |
|---|---|---|---|
| `usd_brl` | `float \| None` | Dolar PTAX compra corrente — R$/USD | BCB SGS 10813 |
| `usd_brl_ptax_venda` | `float \| None` | Dolar PTAX venda corrente — R$/USD | BCB SGS 1 |
| `usd_brl_change_1m` | `float \| None` | Variacao % USD/BRL 1 mes | — |
| `usd_brl_change_3m` | `float \| None` | Variacao % USD/BRL 3 meses | — |
| `usd_brl_change_12m` | `float \| None` | Variacao % USD/BRL 12 meses | — |
| `dxy` | `float \| None` | Dollar Index corrente | Yahoo DX-Y.NYB |
| `dxy_change_1m` | `float \| None` | Variacao % DXY 1 mes | — |
| `selic_rate` | `float \| None` | Selic meta — % a.a. | BCB SGS 432 |
| `fed_funds_rate` | `float \| None` | Fed Funds Rate — % a.a. | FRED DFF |
| `carry_spread` | `float \| None` | Spread Selic - Fed Funds em pp | — |
| `taxa_cambio_real_efetiva` | `float \| None` | Indice taxa cambio real efetiva (IPCA) | BCB SGS 11752 |
| `summary` | `str \| None` | Sumario textual | — |

### CommodityMetrics

Metricas de commodities — calculadas pelo CommodityAnalyzer.

| Campo | Tipo | Descricao | Fonte |
|---|---|---|---|
| `oil_wti` | `float \| None` | Petroleo WTI — USD/bbl | Yahoo CL=F |
| `oil_brent` | `float \| None` | Petroleo Brent — USD/bbl | Yahoo BZ=F |
| `oil_change_1m` | `float \| None` | Variacao % Brent 1m | — |
| `oil_change_3m` | `float \| None` | Variacao % Brent 3m | — |
| `oil_change_12m` | `float \| None` | Variacao % Brent 12m | — |
| `gold` | `float \| None` | Ouro — USD/oz | Yahoo GC=F |
| `gold_change_1m` | `float \| None` | Variacao % ouro 1m | — |
| `gold_change_3m` | `float \| None` | Variacao % ouro 3m | — |
| `gold_change_12m` | `float \| None` | Variacao % ouro 12m | — |
| `silver` | `float \| None` | Prata — USD/oz | Yahoo SI=F |
| `silver_change_1m` | `float \| None` | Variacao % prata 1m | — |
| `soybean` | `float \| None` | Soja — USD/bushel | Yahoo ZS=F |
| `soybean_change_1m` | `float \| None` | Variacao % soja 1m | — |
| `soybean_change_3m` | `float \| None` | Variacao % soja 3m | — |
| `corn` | `float \| None` | Milho — USD/bushel | Yahoo ZC=F |
| `wheat` | `float \| None` | Trigo — USD/bushel | Yahoo ZW=F |
| `commodity_index_change_3m` | `float \| None` | Variacao media ponderada 3m (proxy ciclo) | — |
| `cycle_signal` | `str \| None` | Sinal do ciclo: expansion/peak/contraction/trough | — |
| `summary` | `str \| None` | Sumario textual | — |

### FiscalMetrics

Metricas fiscais — calculadas pelo FiscalAnalyzer.

| Campo | Tipo | Descricao | Fonte |
|---|---|---|---|
| `divida_bruta_pib` | `float \| None` | Divida Bruta / PIB — % | BCB SGS 13762 |
| `divida_liquida_pib` | `float \| None` | Divida Liquida / PIB — % | BCB SGS 4503 |
| `resultado_primario_pib` | `float \| None` | Resultado Primario 12m / PIB — % | BCB SGS 5793 |
| `resultado_nominal` | `float \| None` | Resultado Nominal 12m — R$ milhoes | BCB SGS 4649 |
| `juros_nominais_pib` | `float \| None` | Juros Nominais 12m / PIB — % | BCB SGS 5727 |
| `divida_bruta_pib_change_12m` | `float \| None` | Variacao divida bruta/PIB 12m — pp | — |
| `resultado_primario_pib_change_12m` | `float \| None` | Variacao resultado primario/PIB 12m — pp | — |
| `fiscal_trajectory` | `str \| None` | Trajetoria: improving/stable/warning/deteriorating/critical/severe | — |
| `summary` | `str \| None` | Sumario textual | — |

### Modelos Economicos

Modulo: `carteira_auto.core.models.economic`

| Modelo | Campos Principais | Descricao |
|---|---|---|
| `MacroIndicator` | `name, value, date, source, unit` | Indicador macro pontual (Selic, IPCA, etc.) |
| `MacroSnapshot` | `indicators: list[MacroIndicator], timestamp` | Conjunto de indicadores num momento |
| `MarketIndicator` | `name, value, date, source, unit` | Indicador de mercado (IBOV, IFIX) |
| `MarketSnapshot` | `indicators: list[MarketIndicator], timestamp` | Conjunto de indicadores de mercado |
| `SectorIndicator` | `sector, ticker, return_pct, volume, market_cap, date` | Indicador de setor do mercado financeiro |
| `EconomicSectorIndicator` | `sector, gdp_share, employment, growth_rate, date, source` | Indicador de setor da economia real |

---

## 3. Config — Configuracao

Modulo: `carteira_auto.config.settings`

### Settings

Dataclass principal de configuracao. Instancia global: `settings`.

| Atributo | Tipo | Descricao |
|---|---|---|
| `ENVIRONMENT` | `str` | `"development"` ou `"production"` |
| `DEBUG` | `bool` | Modo debug (env `DEBUG`) |
| `paths` | `PathsConfig` | Caminhos de diretorios e arquivos |
| `yahoo` | `YahooFetcherConfig` | Config do Yahoo Finance |
| `bcb` | `BCBConfig` | Config do BCB |
| `ibge` | `IBGEConfig` | Config do IBGE |
| `ddm` | `DDMConfig` | Config do Dados de Mercado |
| `fred` | `FREDConfig` | Config do FRED |
| `cvm` | `CVMConfig` | Config da CVM |
| `tesouro` | `TesouroConfig` | Config do Tesouro Direto |
| `newsapi` | `NewsAPIConfig` | Config do NewsAPI |
| `coingecko` | `CoinGeckoConfig` | Config do CoinGecko |
| `lake` | `DataLakeConfig` | Config do Data Lake |
| `portfolio` | `PortfolioConfig` | Config da carteira |
| `logging` | `LoggingConfig` | Config de logging |
| `API_KEYS` | `dict[str, str \| None]` | Chaves de API (ddm, fred, newsapi, etc.) |

| Propriedade | Retorno | Descricao |
|---|---|---|
| `is_production` | `bool` | `True` se `ENVIRONMENT == "production"` |
| `is_development` | `bool` | `True` se `ENVIRONMENT == "development"` |

```python
from carteira_auto.config import settings
print(settings.paths.PORTFOLIO_FILE)
print(settings.API_KEYS["fred"])
```

### Sub-configs

#### PathsConfig

| Atributo | Tipo | Descricao |
|---|---|---|
| `ROOT_DIR` | `Path` | Raiz do projeto |
| `DATA_DIR` | `Path` | `ROOT_DIR/data` |
| `RAW_DATA_DIR` | `Path` | `DATA_DIR/raw` |
| `PROCESSED_DATA_DIR` | `Path` | `DATA_DIR/processed` |
| `OUTPUTS_DIR` | `Path` | `DATA_DIR/outputs` |
| `LOGS_DIR` | `Path` | `OUTPUTS_DIR/logs` |
| `PORTFOLIOS_DIR` | `Path` | `OUTPUTS_DIR/portfolios` |
| `REPORTS_DIR` | `Path` | `OUTPUTS_DIR/reports` |
| `SNAPSHOTS_DIR` | `Path` | `OUTPUTS_DIR/snapshots` |
| `LAKE_DIR` | `Path` | `DATA_DIR/lake` |
| `TEMPLATES_DIR` | `Path` | `DATA_DIR/templates` |
| `PORTFOLIO_FILE` | `Path` | `RAW_DATA_DIR/Carteira 2026.xlsx` |

| Metodo | Retorno | Descricao |
|---|---|---|
| `ensure_directories()` | `None` | Cria todos os diretorios necessarios. |
| `get_portfolio_output_path(suffix)` | `Path` | Caminho de saida: `Carteira_YYYY-MM-DD{suffix}.xlsx` |
| `get_log_path(log_name)` | `Path` | Caminho para arquivo de log. |

#### BaseFetcherConfig

Config base herdada por todos os fetchers.

| Atributo | Default | Descricao |
|---|---|---|
| `TIMEOUT` | `30` | Timeout HTTP em segundos |
| `RETRIES` | `3` | Tentativas de retry |
| `RATE_LIMIT` | `30` | Requisicoes por minuto |
| `CACHE_TTL` | `3600` | TTL do cache em segundos |

#### Configs especificas de fetcher

| Config | CACHE_TTL | RATE_LIMIT | BASE_URL |
|---|---|---|---|
| `YahooFetcherConfig` | 300 (5min) | 30 | — |
| `BCBConfig` | 3600 (1h) | 30 | `api.bcb.gov.br/...` |
| `IBGEConfig` | 7200 (2h) | 30 | `apisidra.ibge.gov.br/values` |
| `DDMConfig` | 1800 (30min) | 60 | `api.dadosdemercado.com.br/v1` |
| `FREDConfig` | 3600 (1h) | 120 | `api.stlouisfed.org/fred/...` |
| `CVMConfig` | 86400 (24h) | 30 | `dados.cvm.gov.br/dados` |
| `TesouroConfig` | 3600 (1h) | 30 | `tesourotransparente.gov.br/...` |
| `NewsAPIConfig` | 1800 (30min) | 100 | `newsapi.org/v2` |
| `CoinGeckoConfig` | 300 (5min) | 10 | `api.coingecko.com/api/v3` |

#### DataLakeConfig

| Atributo | Default | Descricao |
|---|---|---|
| `PRICES_TTL` | 86400 (24h) | TTL de precos |
| `MACRO_TTL` | 86400 (24h) | TTL de macro |
| `FUNDAMENTALS_TTL` | 604800 (7d) | TTL de fundamentos |
| `NEWS_TTL` | 3600 (1h) | TTL de noticias |
| `DEFAULT_LOOKBACK_YEARS` | 5 | Anos de historico padrao |

#### PortfolioConfig

| Atributo | Default | Descricao |
|---|---|---|
| `DECIMAL_PLACES` | 4 | Casas decimais |
| `CURRENCY_DECIMAL_PLACES` | 2 | Casas para moeda |
| `REBALANCE_THRESHOLD` | 0.05 (5%) | Threshold de rebalanceamento |
| `MIN_TRADE_VALUE` | 100.0 | Valor minimo de operacao R$ |
| `RISK_FREE_DAILY` | 0.0004 | CDI diario (~10.5% a.a.) |
| `TAX_RATE_STOCKS` | 0.15 (15%) | Imposto sobre acoes |
| `TAX_RATE_FII` | 0.20 (20%) | Imposto sobre FIIs |
| `TAX_EXEMPTION` | 20000.0 | Isencao mensal de vendas R$ |
| `TARGET_ALLOCATIONS` | `dict` | Metas: RF 24%, Fundos 27%, Acoes 31%, Internacional 18% |

### Constants

Modulo: `carteira_auto.config.constants`

Instancia global: `constants`.

| Atributo | Tipo | Descricao |
|---|---|---|
| `MARKET_SESSIONS` | `dict[str, tuple]` | Horarios: B3 (10-17), NYSE (09:30-16), CRYPTO (24/7) |
| `HOLIDAYS_B3` | `list[str]` | Feriados da B3 em 2026 |
| `CARTEIRA_SHEET_NAMES` | `dict` | Nomes das abas: "Carteira", "Rentabilidade Carteira", "Vendas" |
| `CARTEIRA_COLUMNS` | `list[str]` | 21 colunas da aba Carteira |
| `CARTEIRA_FIELD_MAP` | `dict[str, str]` | Mapeamento coluna Excel -> campo do modelo |
| `VENDAS_COLUMNS` | `list[str]` | 15 colunas da aba Vendas |
| `VENDAS_FIELD_MAP` | `dict[str, str]` | Mapeamento coluna Excel -> campo do modelo |
| `NON_YAHOO_TICKERS` | `set[str]` | Tickers sem Yahoo: `{"LFT", "NTNB", "NTNF", "LTN"}` |
| `BCB_SERIES_CODES` | `dict[str, int]` | Codigos SGS: selic=432, cdi=12, ipca=433, ptax_compra=10813, etc. |
| `IBGE_TABLE_IDS` | `dict[str, int]` | Tabelas SIDRA: ipca=1737, pib_trimestral=5932, pnad=6381 |
| `VALID_TICKER_PATTERNS` | `dict[str, str]` | Regex de validacao para B3, Yahoo, crypto, futuros |
| `REPORT_SECTIONS` | `list[str]` | Secoes do relatorio |

---

## 4. Data Fetchers — Coleta de Dados

Modulo: `carteira_auto.data.fetchers`

### YahooFinanceFetcher

Busca dados do Yahoo Finance com cache, retry e paralelismo.

```python
fetcher = YahooFinanceFetcher(max_workers=8)
```

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `__init__` | `max_workers: int \| None` | — | Default: `min(32, cpu_count + 4)` |
| `normalize_br_ticker` | `ticker: str` | `str` | Adiciona `.SA` para tickers B3. Estatico. |
| `get_historical_price_data` | `symbols: str \| list[str], period="5y", interval="1d", start=None, end=None` | `pd.DataFrame` | OHLCV historico via `yf.download`. Cache 24h. |
| `get_current_price` | `symbol: str` | `float \| None` | Preco mais recente. Cache 5min. |
| `get_multiple_prices` | `symbols: list[str]` | `dict[str, float \| None]` | Precos atuais em lote. Normaliza e filtra tickers automaticamente. |
| `get_basic_info` | `symbol: str` | `dict \| None` | Infos basicas: preco, setor, market cap. Cache 24h. |
| `get_financials` | `symbol: str` | `dict \| None` | DRE, balanco, fluxo de caixa. Cache 24h. |
| `get_dividends` | `symbol: str` | `dict \| None` | Historico de dividendos e splits. Cache 24h. |
| `get_earnings` | `symbol: str` | `dict \| None` | Lucros e estimativas. Cache 24h. |
| `get_holders` | `symbol: str` | `dict \| None` | Acionistas e insiders. Cache 24h. |
| `get_recommendations` | `symbol: str` | `dict \| None` | Recomendacoes de analistas. Cache 24h. |
| `get_dividend_yield` | `symbol: str` | `float \| None` | Dividend yield (tenta info, depois calcula). Cache 24h. |
| `get_batch_info` | `symbols: list[str], fields: list[str] \| None` | `dict[str, dict]` | Multiplos dados em paralelo por ticker. |
| `get_market_summary` | `market: str = "us"` | `dict \| None` | Resumo do mercado. Cache 5min. |
| `search_tickers` | `query: str, limit: int = 10` | `list[dict]` | Busca tickers por nome. Cache 1h. |
| `get_market_calendar` | `days: int = 30` | `pd.DataFrame \| None` | Calendario de eventos. Cache 1h. |
| `get_sector_performance` | `sector: str = "technology"` | `dict \| None` | Performance de setor. Cache 1h. |
| `get_industry_performance` | `industry: str = "software"` | `dict \| None` | Performance de industria. Cache 1h. |
| `validate_symbol` | `symbol: str` | `tuple[bool, str]` | Valida se simbolo existe no Yahoo. |

```python
fetcher = YahooFinanceFetcher()
prices = fetcher.get_multiple_prices(["PETR4", "VALE3", "ITUB4"])
df = fetcher.get_historical_price_data(["PETR4.SA"], period="1y")
```

### BCBFetcher

Dados do Banco Central do Brasil. Modulo `bcb/` com 6 mixins: SGS, Focus, PTAX, TaxaJuros, MercadoImobiliario, Base. 105 metodos publicos.

```python
from carteira_auto.data.fetchers.bcb import BCBFetcher
bcb = BCBFetcher()
```

Retorno padrao SGS: DataFrame com colunas `['data', 'valor']`.

#### BCBSGSMixin — Series Temporais SGS (57 series, 60 metodos)

**Juros e rendimento:**

| Metodo | Retorno | Descricao |
|---|---|---|
| `get_selic(period_days=1825)` | `pd.DataFrame` | Taxa Selic meta — % a.a. \| SGS 432 |
| `get_cdi(period_days=1825)` | `pd.DataFrame` | CDI — % a.d. \| SGS 12 |
| `get_cdi_annual(period_days=1825)` | `pd.DataFrame` | CDI anualizado — % a.a. |
| `get_tr(period_days=1825)` | `pd.DataFrame` | Taxa Referencial — % a.m. \| SGS 226 |
| `get_poupanca(period_days=1825)` | `pd.DataFrame` | Rendimento poupanca — % a.m. \| SGS 25 |

**Inflacao:**

| Metodo | Retorno | Descricao |
|---|---|---|
| `get_ipca(period_days=1825)` | `pd.DataFrame` | IPCA — % mensal \| SGS 433 |
| `get_igpm(period_days=1825)` | `pd.DataFrame` | IGP-M — % mensal \| SGS 189 |
| `get_inpc(period_days=1825)` | `pd.DataFrame` | INPC — % mensal \| SGS 188 |
| `get_ipca15(period_days=1825)` | `pd.DataFrame` | IPCA-15 previa — % mensal |
| `get_igpdi(period_days=1825)` | `pd.DataFrame` | IGP-DI — % mensal |
| `get_core_ipca_ex0(period_days=1825)` | `pd.DataFrame` | Nucleo IPCA (ex-alimentos e energia) |
| `get_ipca_expectation_12m(period_days=1825)` | `pd.DataFrame` | Expectativa IPCA 12m |
| `get_real_interest_rate(period_days=1825)` | `pd.DataFrame` | Juros real (Selic - IPCA) |

**Cambio:**

| Metodo | Retorno | Descricao |
|---|---|---|
| `get_ptax(period_days=30)` | `pd.DataFrame` | PTAX compra USD/BRL \| SGS 10813 |
| `get_ptax_venda(period_days=30)` | `pd.DataFrame` | PTAX venda USD/BRL \| SGS 1 |
| `get_real_effective_exchange(period_days=1825)` | `pd.DataFrame` | Taxa cambio real efetiva |

**Fiscal:**

| Metodo | Retorno | Descricao |
|---|---|---|
| `get_gross_debt_gdp(period_days=3650)` | `pd.DataFrame` | Divida bruta/PIB — % \| SGS 13762 |
| `get_net_debt_gdp(period_days=3650)` | `pd.DataFrame` | Divida liquida/PIB — % \| SGS 4503 |
| `get_primary_result_gdp(period_days=3650)` | `pd.DataFrame` | Resultado primario/PIB — % \| SGS 5793 |
| `get_nominal_result(period_days=3650)` | `pd.DataFrame` | Resultado nominal 12m — R$ MM |
| `get_nominal_interest_gdp(period_days=3650)` | `pd.DataFrame` | Juros nominais/PIB — % \| SGS 5727 |

**Atividade economica:**

| Metodo | Retorno | Descricao |
|---|---|---|
| `get_ibcbr(period_days=1825)` | `pd.DataFrame` | IBC-Br (proxy do PIB mensal) |
| `get_business_confidence(period_days=1825)` | `pd.DataFrame` | Indice de confianca empresarial |
| `get_capacity_utilization(period_days=1825)` | `pd.DataFrame` | Utilizacao da capacidade instalada |
| `get_embi(period_days=1825)` | `pd.DataFrame` | EMBI+ Brasil (risco pais) |
| `get_ibovespa_bcb(period_days=1825)` | `pd.DataFrame` | Ibovespa via BCB |
| `get_ouro_bmf(period_days=1825)` | `pd.DataFrame` | Ouro BM&F |

**Credito e monetario:**

| Metodo | Retorno | Descricao |
|---|---|---|
| `get_credit_gdp(period_days=3650)` | `pd.DataFrame` | Credito/PIB — % |
| `get_default_rate(period_days=1825)` | `pd.DataFrame` | Inadimplencia PF |
| `get_default_rate_corporate(period_days=1825)` | `pd.DataFrame` | Inadimplencia PJ |
| `get_default_rate_total(period_days=1825)` | `pd.DataFrame` | Inadimplencia total |
| `get_default_rate_pf_15_90(period_days=1825)` | `pd.DataFrame` | Inadimplencia PF 15-90 dias |
| `get_default_rate_pf_90_plus(period_days=1825)` | `pd.DataFrame` | Inadimplencia PF >90 dias |
| `get_default_rate_credit_card(period_days=1825)` | `pd.DataFrame` | Inadimplencia cartao |
| `get_m1(period_days=1825)` | `pd.DataFrame` | Agregado M1 |
| `get_m2(period_days=1825)` | `pd.DataFrame` | Agregado M2 |
| `get_m4(period_days=1825)` | `pd.DataFrame` | Agregado M4 |
| `get_monetary_base(period_days=1825)` | `pd.DataFrame` | Base monetaria |
| `get_reserve_requirements(period_days=1825)` | `pd.DataFrame` | Depositos compulsorios |

**Setor externo:**

| Metodo | Retorno | Descricao |
|---|---|---|
| `get_trade_balance(period_days=1825)` | `pd.DataFrame` | Balanca comercial |
| `get_international_reserves(period_days=1825)` | `pd.DataFrame` | Reservas internacionais |
| `get_current_account(period_days=1825)` | `pd.DataFrame` | Transacoes correntes |
| `get_fdi_net(period_days=1825)` | `pd.DataFrame` | IED liquido |
| `get_external_debt(period_days=3650)` | `pd.DataFrame` | Divida externa |
| `get_fx_flow(period_days=1825)` | `pd.DataFrame` | Fluxo cambial mensal |
| `get_terms_of_trade(period_days=3650)` | `pd.DataFrame` | Termos de troca |

**Trabalho e renda:**

| Metodo | Retorno | Descricao |
|---|---|---|
| `get_real_wage_bill(period_days=1825)` | `pd.DataFrame` | Massa salarial real |
| `get_real_average_income(period_days=1825)` | `pd.DataFrame` | Renda media real |
| `get_unemployment_rate(period_days=1825)` | `pd.DataFrame` | Taxa de desemprego |
| `get_minimum_wage(period_days=3650)` | `pd.DataFrame` | Salario minimo |
| `get_formal_employment_balance(period_days=1825)` | `pd.DataFrame` | Saldo CAGED |
| `get_hours_worked(period_days=1825)` | `pd.DataFrame` | Horas trabalhadas PNAD |

**Expropriacao financeira:**

| Metodo | Retorno | Descricao |
|---|---|---|
| `get_banking_spread_pf(period_days=1825)` | `pd.DataFrame` | Spread bancario PF |
| `get_credit_cost_pf(period_days=1825)` | `pd.DataFrame` | Custo do credito PF |
| `get_household_debt_ratio(period_days=1825)` | `pd.DataFrame` | Endividamento das familias |
| `get_household_debt_service(period_days=1825)` | `pd.DataFrame` | Comprometimento de renda |
| `get_consumer_confidence(period_days=1825)` | `pd.DataFrame` | Confianca do consumidor |

**Generico:**

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `get_indicator` | `series_code: int, start_date, end_date` | `pd.DataFrame` | Qualquer serie SGS por codigo |
| `get_all_indicators` | — | `dict[str, pd.DataFrame]` | Todos os indicadores configurados |
| `get_latest_values` | — | `dict[str, float \| None]` | Ultimo valor de cada indicador |

#### BCBFocusMixin — Expectativas Focus (21 metodos)

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `get_focus_selic` | `period_months=24` | `pd.DataFrame` | Expectativas anuais Selic |
| `get_focus_ipca` | `period_months=24` | `pd.DataFrame` | Expectativas anuais IPCA |
| `get_focus_pib` | `period_months=24` | `pd.DataFrame` | Expectativas anuais PIB |
| `get_focus_cambio` | `period_months=24` | `pd.DataFrame` | Expectativas anuais cambio |
| `get_focus_igpm` | `period_months=24` | `pd.DataFrame` | Expectativas anuais IGP-M |
| `get_focus_all` | `period_months=24` | `dict[str, pd.DataFrame]` | Todas expectativas anuais |
| `get_focus_top5` | `indicator, period_months=24` | `pd.DataFrame` | Top 5 analistas (anual) |
| `get_focus_top5_all` | `period_months=24` | `dict[str, pd.DataFrame]` | Top 5 todos indicadores |
| `get_focus_monthly` | `indicator, period_months=24` | `pd.DataFrame` | Expectativas mensais |
| `get_focus_monthly_all` | `period_months=24` | `dict[str, pd.DataFrame]` | Expectativas mensais todos |
| `get_focus_top5_monthly` | `indicator, period_months=24` | `pd.DataFrame` | Top 5 analistas (mensal) |
| `get_focus_quarterly` | `indicator, period_months=24` | `pd.DataFrame` | Expectativas trimestrais |
| `get_focus_quarterly_all` | `period_months=24` | `dict[str, pd.DataFrame]` | Expectativas trimestrais todos |
| `get_focus_top5_quarterly` | `indicator, period_months=24` | `pd.DataFrame` | Top 5 analistas (trimestral) |
| `get_focus_selic_copom` | `period_months=24` | `pd.DataFrame` | Selic por reuniao COPOM |
| `get_focus_top5_selic` | `period_months=24` | `pd.DataFrame` | Top 5 analistas Selic |
| `get_focus_ipca12m` | `period_months=24` | `pd.DataFrame` | IPCA rolling 12m |
| `get_focus_ipca24m` | `period_months=24` | `pd.DataFrame` | IPCA rolling 24m |
| `get_focus_top5_ipca12m` | `period_months=24` | `pd.DataFrame` | Top 5 IPCA 12m |
| `get_focus_top5_ipca24m` | `period_months=24` | `pd.DataFrame` | Top 5 IPCA 24m |
| `get_focus_reference_dates` | — | `pd.DataFrame` | Datas de referencia disponiveis |

#### BCBPTAXMixin — Cotacoes PTAX OData (3 metodos)

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `get_ptax_currency` | `currency_code, start_date, end_date, period_days=30` | `pd.DataFrame` | PTAX por moeda (AUD, CAD, CHF, DKK, EUR, GBP, JPY, NOK, SEK, USD) |
| `get_ptax_all_currencies` | `reference_date` | `pd.DataFrame` | PTAX todas as moedas numa data |
| `get_available_currencies` | — | `pd.DataFrame` | Moedas disponiveis |

#### BCBTaxaJurosMixin — Taxas de Credito (6 metodos)

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `get_lending_rates` | `modality, period_months=12` | `pd.DataFrame` | Taxas de credito por modalidade e banco |
| `get_all_lending_rates` | `period_months=12` | `dict[str, pd.DataFrame]` | Todas as taxas agrupadas por modalidade |
| `get_lending_rate_modalities` | — | `pd.DataFrame` | Modalidades de credito disponiveis |
| `get_lending_rates_daily` | `modality, segment, period_months=3` | `pd.DataFrame` | Taxas diarias (media 5 dias) |
| `get_lending_rates_unified` | `modality, segment, period_months=3` | `pd.DataFrame` | Taxas unificadas (alternativa ao diario) |
| `get_lending_rate_dates` | — | `pd.DataFrame` | Datas disponiveis |

#### BCBMercadoImobiliarioMixin — Indicadores Imobiliarios (15 metodos)

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `get_ivg` | `period_months=60` | `pd.DataFrame` | Indice de Valores de Garantia (IVG) |
| `get_mvg` | `period_months=60` | `pd.DataFrame` | Valor Medio de Garantia (MVG) |
| `get_credito_imobiliario_sfh` | `period_months=60` | `pd.DataFrame` | Estoque credito SFH |
| `get_credito_imobiliario_fgts` | `period_months=60` | `pd.DataFrame` | Estoque credito FGTS |
| `get_credito_imobiliario_livre` | `period_months=60` | `pd.DataFrame` | Estoque credito livre |
| `get_inadimplencia_imobiliaria_sfh` | `period_months=60` | `pd.DataFrame` | Inadimplencia SFH |
| `get_inadimplencia_imobiliaria_livre` | `period_months=60` | `pd.DataFrame` | Inadimplencia livre |
| `get_taxa_credito_imobiliario_sfh` | `period_months=60` | `pd.DataFrame` | Taxa SFH |
| `get_taxa_credito_imobiliario_livre` | `period_months=60` | `pd.DataFrame` | Taxa livre |
| `get_contratacao_imobiliaria_sfh` | `period_months=60` | `pd.DataFrame` | Contratacoes SFH |
| `get_contratacao_imobiliaria_livre` | `period_months=60` | `pd.DataFrame` | Contratacoes livre |
| `get_imoveis_apartamento` | `period_months=60` | `pd.DataFrame` | Estoque imoveis apartamento |
| `get_imoveis_casa` | `period_months=60` | `pd.DataFrame` | Estoque imoveis casa |
| `get_imoveis_valor_medio` | `period_months=60` | `pd.DataFrame` | Valor medio do imovel |
| `get_mercado_imobiliario_all` | `period_months=60` | `dict[str, pd.DataFrame]` | Todos os 14 indicadores |

```python
bcb = BCBFetcher()
selic = bcb.get_selic(period_days=30)
focus = bcb.get_focus_all()
ptax_eur = bcb.get_ptax_currency("EUR")
taxas = bcb.get_lending_rates("consignado")
ivg = bcb.get_ivg()
```

### IBGEFetcher

Dados do IBGE via SIDRA API, CNAE e indicadores por pais. 17 tabelas SIDRA + CNAE + paises.

**Inflacao:**

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `get_ipca` | `months=12` | `pd.DataFrame` | IPCA variacao mensal — % \| Tabela 1737 |
| `get_ipca_detailed` | `months=12` | `pd.DataFrame` | IPCA por grupos — % \| Tabela 1737 |
| `get_ipca_new` | `months=12` | `pd.DataFrame` | IPCA serie 2020+ — variacao, acumulada, peso \| Tabela 7060 |
| `get_ipca_subitems` | `months=6` | `pd.DataFrame` | IPCA por subitens — % \| Tabela 1419 |
| `get_ipca15` | `months=12` | `pd.DataFrame` | IPCA-15 previa — % \| Tabela 7062 |
| `get_ipca_groups` | `months=12` | `pd.DataFrame` | IPCA variacao + peso por grupos \| Tabela 7060 |

**PIB:**

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `get_pib` | `quarters=8` | `pd.DataFrame` | PIB variacao % trimestral \| Tabela 5932 |
| `get_pib_dessaz` | `quarters=20` | `pd.DataFrame` | PIB dessazonalizado — indice trimestral |
| `get_pib_nominal` | `years=5` | `pd.DataFrame` | PIB nominal R$ bilhoes |

**Emprego e renda:**

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `get_unemployment` | `quarters=8` | `pd.DataFrame` | Desocupacao PNAD — % \| Tabela 6381 |
| `get_underemployment` | `quarters=8` | `pd.DataFrame` | Subutilizacao — % \| Tabela 6382 |
| `get_average_income` | `quarters=12` | `pd.DataFrame` | Rendimento medio — R$ \| Tabela 6387 |
| `get_population` | `quarters=8` | `pd.DataFrame` | Populacao — milhoes |
| `get_gini` | `years=10` | `pd.DataFrame` | Indice de Gini — anual |
| `get_analfabetismo` | `years=10` | `pd.DataFrame` | Analfabetismo 15+ — % \| Tabela 7113 |

**Atividade setorial:**

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `get_industrial_production` | `months=12` | `pd.DataFrame` | PIM-PF — producao industrial — % \| Tabela 8888 |
| `get_retail_sales` | `months=12` | `pd.DataFrame` | PMC — comercio varejista — % \| Tabela 8881 |
| `get_services` | `months=12` | `pd.DataFrame` | PMS — servicos — % \| Tabela 8688 |
| `get_construction_cost` | `months=12` | `pd.DataFrame` | SINAPI — custo construcao \| Tabela 2296 |

**CNAE (classificacao setorial):**

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `get_cnae_sections` | — | `pd.DataFrame` | Secoes CNAE (~10) |
| `get_cnae_divisions` | — | `pd.DataFrame` | Divisoes CNAE (~90) |
| `get_cnae_classes` | — | `pd.DataFrame` | Classes CNAE (~645) |
| `get_cnae_subclasses` | `class_code=None` | `pd.DataFrame` | Subclasses CNAE (~2.093) |
| `get_cnae_search` | `term: str` | `pd.DataFrame` | Busca CNAE por termo |

**Paises:**

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `get_country_list` | — | `pd.DataFrame` | Lista de paises com metadados |
| `get_country_info` | `country_code: str` | `dict` | Info detalhada de um pais |

```python
ibge = IBGEFetcher()
pib = ibge.get_pib(quarters=4)
gini = ibge.get_gini(years=5)
cnae = ibge.get_cnae_search("software")
```

### FREDFetcher

Dados economicos do Federal Reserve (FRED). 38 series configuradas em `Constants.FRED_SERIES`. Requer `FRED_API_KEY` no `.env`.

**Base (4 metodos):**

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `get_series` | `series_id, start_date, end_date` | `pd.DataFrame` | Serie temporal. Colunas: `date, value, series_id`. |
| `get_series_info` | `series_id` | `dict` | Metadados (nome, unidade, frequencia). |
| `get_multiple_series` | `series_ids, start_date, end_date` | `dict[str, pd.DataFrame]` | Multiplas series em paralelo. |
| `get_macro_bundle` | `start_date, end_date` | `dict[str, pd.DataFrame]` | Bundle padrao: DFF, DGS10, T10Y2Y, VIXCLS, CPIAUCSL, DEXBZUS. |

**Convenience methods (23 metodos) + list_series:**

| Metodo | Serie FRED | Descricao |
|---|---|---|
| `get_fed_funds_rate` | DFF | Fed Funds Rate efetiva — diaria |
| `get_treasury_3m` | DGS3MO | Treasury 3 meses — ponta curta |
| `get_treasury_2y` | DGS2 | Treasury 2 anos |
| `get_treasury_10y` | DGS10 | Treasury 10 anos |
| `get_treasury_30y` | DGS30 | Treasury 30 anos — ponta longa |
| `get_yield_curve_spread` | T10Y2Y | Spread 10Y-2Y — inversao de curva |
| `get_tips_real_yield` | DFII10 | TIPS 10Y — juros real EUA |
| `get_vix` | VIXCLS | VIX — volatilidade esperada S&P 500 |
| `get_us_cpi` | CPIAUCSL | CPI EUA — mensal, base 1982-84=100 |
| `get_core_pce` | PCEPILFE | Core PCE — preferido do Fed |
| `get_brl_usd` | DEXBZUS | BRL/USD — diaria |
| `get_eur_usd` | DEXUSEU | EUR/USD — par mais negociado |
| `get_cny_usd` | DEXCHUS | CNY/USD — cambio China |
| `get_dollar_index` | DTWEXBGS | DXY ponderado por comercio |
| `get_us_gdp` | GDPC1/GDP | PIB EUA (real ou nominal) |
| `get_us_unemployment` | UNRATE | Desemprego EUA — mensal |
| `get_industrial_production` | INDPRO | Producao industrial EUA |
| `get_nonfarm_payrolls` | PAYEMS | Nonfarm Payrolls — criacao de empregos |
| `get_consumer_sentiment` | UMCSENT | Sentimento do consumidor Michigan |
| `get_high_yield_spread` | BAMLH0A0HYM2 | HY spread OAS — apetite a risco |
| `get_breakeven_inflation` | T10YIE | Breakeven 10Y — expectativa inflacao |
| `get_wti_oil` | DCOILWTICO | Petroleo WTI |
| `get_gold_price` | GOLDAMGBD228NLBM | Ouro London Fix |
| `list_series` | — | Series disponiveis (estatico) |

Series configuradas (38): DFF, FEDFUNDS, DPRIME, DGS3MO, DGS1, DGS2, DGS5, DGS10, DGS20, DGS30, T10Y2Y, T5YIE, T10YIE, DFII5, DFII10, GDP, GDPC1, CPIAUCSL, CPILFESL, PCEPILFE, PCE, UNRATE, PAYEMS, ICSA, INDPRO, UMCSENT, HOUST, CSUSHPINSA, VIXCLS, BAMLH0A0HYM2, SP500, DCOILWTICO, GOLDAMGBD228NLBM, DEXBZUS, DEXUSEU, DEXJPUS, DEXCHUS, DTWEXBGS.

```python
fred = FREDFetcher()
bundle = fred.get_macro_bundle()
vix = fred.get_vix()
oil = fred.get_wti_oil()
```

### CVMFetcher

Dados abertos da CVM (demonstracoes financeiras e cadastro de empresas).

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `get_company_registry` | — | `pd.DataFrame` | Cadastro oficial. Colunas: `cnpj, razao_social, nome_pregao, cod_cvm, setor, situacao`. |
| `build_ticker_cnpj_map` | — | `dict[str, str]` | Mapa `{ticker: cnpj}` via DDM + fallback CVM. |
| `get_cnpj_by_ticker` | `ticker: str` | `str \| None` | CNPJ por ticker (heuristica de prefixo). |
| `get_dfp` | `cnpj: str, year: int, statement: str = "DRE"` | `pd.DataFrame` | DFP anual auditada. Statements: DRE, BPA, BPP, DFC_MD, DVA. |
| `get_itr` | `cnpj: str, year: int, quarter: int, statement: str = "DRE"` | `pd.DataFrame` | ITR trimestral. Quarter: 1-4. |
| `get_dfp_by_ticker` | `ticker: str, year: int, statement: str` | `pd.DataFrame` | DFP por ticker (resolve CNPJ automaticamente). |
| `get_itr_by_ticker` | `ticker: str, year: int, quarter: int, statement: str` | `pd.DataFrame` | ITR por ticker. |

```python
cvm = CVMFetcher()
cnpj = cvm.get_cnpj_by_ticker("PETR4")
dre = cvm.get_dfp(cnpj, 2024, "DRE")
# Ou diretamente:
dre = cvm.get_dfp_by_ticker("PETR4", 2024, "DRE")
```

### TesouroDiretoFetcher

Dados historicos do Tesouro Direto (Tesouro Transparente). Sem autenticacao.

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `get_current_rates` | — | `pd.DataFrame` | Taxas e PUs atuais. Colunas: `tipo, vencimento, data, taxa_compra, taxa_venda, pu_compra, pu_venda, pu_base`. |
| `get_price_history` | — | `pd.DataFrame` | Historico completo desde 2002 (~10MB). Cache 24h. |
| `get_price_history_by_type` | `tipo: str` | `pd.DataFrame` | Historico filtrado. Tipos: "LFT", "NTN-B", "NTN-B CUPOM", "LTN", "NTN-F". |
| `get_lft_history` | — | `pd.DataFrame` | Historico LFT (Tesouro Selic). |
| `get_ntnb_history` | `com_cupom: bool = False` | `pd.DataFrame` | Historico NTN-B (IPCA+). |
| `get_ltn_history` | — | `pd.DataFrame` | Historico LTN (Prefixado). |
| `get_ntnf_history` | — | `pd.DataFrame` | Historico NTN-F (Prefixado com cupom). |
| `get_ntnb_curve` | — | `pd.DataFrame` | Curva IPCA+ atual (taxa por vencimento). |
| `get_available_titles` | — | `list[str]` | Tipos de titulos no historico. |

```python
tesouro = TesouroDiretoFetcher()
taxas = tesouro.get_current_rates()
curva = tesouro.get_ntnb_curve()
```

### DDMFetcher

Dados de Mercado (DDM) — API REST. Requer `DADOS_MERCADO_API_KEY` no `.env`.

#### Empresas (`/v1/companies/{ticker}/`)

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `get_companies` | — | `list[dict]` | Lista de companhias abertas. |
| `get_stock_data` | `ticker: str` | `list[dict]` | Indicadores de mercado (P/L, EV/EBITDA). |
| `get_financials` | `ticker: str` | `list[dict]` | Indicadores financeiros (ROE, margens). |
| `get_dividends` | `ticker: str` | `list[dict]` | Historico de dividendos e JCP. |
| `get_balance_sheet` | `ticker: str` | `list[dict]` | Balanco patrimonial. |
| `get_income_statement` | `ticker: str` | `list[dict]` | DRE historica. |
| `get_cash_flow` | `ticker: str` | `list[dict]` | Fluxo de caixa. |
| `get_shares` | `ticker: str` | `list[dict]` | Numero de acoes. |
| `get_corporate_events` | `ticker: str` | `list[dict]` | Splits e bonificacoes. |

#### Tickers e Bolsa (`/v1/tickers/`)

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `get_quotations` | `ticker: str, period_init, period_end` | `list[dict]` | Cotacoes OHLCV. |
| `get_asset_list` | — | `list[dict]` | Lista de ativos da B3. |
| `get_market_indices` | — | `list[dict]` | Indices (IBOV, IFIX, SMLL). |
| `get_index_details` | `index: str` | `list[dict]` | Composicao de um indice. |
| `get_risk_indicators` | `ticker, index="IBOV", period_init, period_end` | `list[dict]` | Beta, alpha, etc. |
| `get_dividend_yield` | `ticker: str` | `list[dict]` | DY historico anual. |
| `get_foreign_investors` | — | `list[dict]` | Fluxo de estrangeiros. |

#### FIIs (`/v1/reits/`)

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `get_fii_list` | — | `list[dict]` | Lista de FIIs. |
| `get_fii_dividends` | `ticker: str, date_from` | `list[dict]` | Dividendos de FII. |

#### Fundos (`/v1/funds/`)

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `get_fund_list` | — | `list[dict]` | Lista de fundos. |
| `get_fund_quotes` | `fund_id: str` | `list[dict]` | Historico de cotas. |

#### Titulos Publicos (`/v1/treasury/`, `/v1/bonds/`)

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `get_treasury_list` | — | `list[dict]` | Titulos disponiveis. |
| `get_treasury_prices` | — | `list[dict]` | Precos atuais. |
| `get_all_treasury_list` | — | `list[dict]` | Todos titulos (incluindo vencidos). |
| `get_treasury_price_history` | `isin: str \| None` | `list[dict]` | Historico por ISIN. |

#### Macro (`/v1/macro/`)

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `get_macro_series` | `indicator: str` | `list[dict]` | Serie macro (selic, cdi, ipca, igp-m). |
| `get_economic_indices` | — | `dict[str, list[dict]]` | Principais indicadores brasileiros. |
| `get_focus_bulletin` | `indicator: str = "selic"` | `list[dict]` | Boletim Focus. |
| `get_interest_curves` | `curve: str = "ettj_ipca"` | `list[dict]` | Curva de juros (ETTJ). |
| `get_market_expectations` | — | `list[dict]` | Expectativas Focus IPCA. |

#### Moedas (`/v1/currencies/`)

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `get_currencies` | — | `list[dict]` | Moedas disponiveis. |
| `get_currency_conversion` | `from_currency="USD", to_currency="BRL", reference_date` | `dict` | Taxa de cambio. |

#### Noticias (`/v1/news`)

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `get_news` | `ticker: str \| None` | `list[dict]` | Ultimas 100 noticias. Filtravel por ticker. |

```python
ddm = DDMFetcher()
dre = ddm.get_income_statement("PETR4")
focus = ddm.get_focus_bulletin("selic")
fx = ddm.get_currency_conversion("USD", "BRL")
```

---

## 5. Data Lake — Persistencia

Modulo: `carteira_auto.data.lake`

### DataLake

Interface unificada que agrega PriceLake, MacroLake, FundamentalsLake, NewsLake e ReferenceLake. Cada sub-lake gerencia seu proprio arquivo SQLite.

```python
lake = DataLake(Path("data/lake"))
```

| Atributo | Tipo | Descricao |
|---|---|---|
| `prices` | `PriceLake` | Sub-lake de precos OHLCV |
| `macro` | `MacroLake` | Sub-lake de indicadores macro |
| `fundamentals` | `FundamentalsLake` | Sub-lake de fundamentos |
| `news` | `NewsLake` | Sub-lake de noticias |
| `reference` | `ReferenceLake` | Sub-lake de dados de referencia (12 tabelas) |

#### Precos

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `store_prices` | `df: pd.DataFrame, source: str = "yahoo"` | `int` | Persiste precos OHLCV. Retorna registros inseridos. |
| `get_prices` | `tickers: list[str], start, end, columns, lookback` | `pd.DataFrame` | Consulta precos. Default colunas: `["close"]`. |
| `get_latest_prices` | `tickers: list[str]` | `dict[str, float]` | Ultimo preco de fechamento. |

#### Macro

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `store_macro` | `indicator, df, source, unit, frequency` | `int` | Persiste serie macro. |
| `get_macro` | `indicator: str, start, end` | `pd.DataFrame` | Consulta serie macro. |
| `get_macro_latest` | `indicator: str` | `float \| None` | Ultimo valor de indicador. |

#### Fundamentos

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `store_fundamentals` | `ticker, period, indicators: dict, source` | `int` | Persiste indicadores. |
| `store_statement` | `ticker, period, statement_type, data: dict, source` | `None` | Persiste demonstracao financeira. |
| `get_fundamentals` | `ticker: str, periods: int = 8, indicators` | `pd.DataFrame` | Consulta fundamentos. |

#### Noticias

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `store_news` | `articles: list[dict], source: str` | `int` | Persiste artigos. |
| `get_news` | `start, end, category, limit: int = 100` | `pd.DataFrame` | Consulta noticias. |
| `get_sentiment` | `start, end` | `pd.DataFrame` | Serie temporal de sentimento. |

#### Exportacao e Info

| Metodo | Retorno | Descricao |
|---|---|---|
| `export_all_to_parquet()` | `dict[str, Path]` | Exporta tudo para Parquet. |
| `summary()` | `dict` | Contagem de registros e tickers por sub-lake. |

```python
lake = DataLake(settings.paths.LAKE_DIR)
lake.store_prices(df, source="yahoo")
prices = lake.get_prices(["PETR4.SA"], start=date(2024, 1, 1))
latest = lake.get_latest_prices(["PETR4.SA", "VALE3.SA"])
summary = lake.summary()
```

### Sub-lakes

| Classe | Arquivo SQLite | Descricao |
|---|---|---|
| `PriceLake` | `prices.db` | Precos OHLCV por ticker/data |
| `MacroLake` | `macro.db` | Series de indicadores macro |
| `FundamentalsLake` | `fundamentals.db` | Indicadores e demonstracoes financeiras |
| `NewsLake` | `news.db` | Artigos e sentimento |
| `ReferenceLake` | `reference.db` | 12 tabelas de dados estruturais nao-temporais |

### ReferenceLake

Dados de referencia estruturais. 12 tabelas com `source` e `updated_at`.

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `store_index_composition` | `index_code, df, source, ref_date` | `int` | Composicao de indice |
| `get_index_composition` | `index_code, ref_date` | `pd.DataFrame` | Consulta composicao |
| `get_available_indexes` | — | `list[str]` | Indices disponiveis |
| `store_focus_expectations` | `indicator, data, source` | `int` | Expectativas Focus |
| `get_focus_expectations` | `indicator, limit=100` | `pd.DataFrame` | Consulta Focus |
| `store_analyst_targets` | `ticker, targets, source` | `int` | Targets de analistas |
| `get_analyst_targets` | `ticker` | `dict \| None` | Consulta targets |
| `store_upgrades_downgrades` | `ticker, df, source` | `int` | Upgrades/downgrades |
| `store_lending_rates` | `data, source` | `int` | Taxas de credito |
| `store_cnae` | `classifications` | `int` | Classificacoes CNAE |
| `store_ticker_cnpj` | `mapping, source` | `int` | Mapeamento ticker→CNPJ |
| `get_ticker_cnpj` | `ticker` | `str \| None` | Consulta CNPJ por ticker |
| `get_all_ticker_cnpj` | — | `dict[str, str]` | Mapeamento completo |
| `store_major_holders` | `ticker, holders, source` | `int` | Participacao acionaria |
| `get_major_holders` | `ticker` | `dict \| None` | Consulta holders |
| `store_fund_registry` | `funds, source` | `int` | Cadastro de fundos |
| `get_fund_registry` | `fund_type, situation` | `pd.DataFrame` | Consulta fundos |
| `store_fund_portfolios` | `cnpj, df, source, ref_date` | `int` | Carteira de fundo (CDA) |
| `get_fund_portfolio` | `cnpj, ref_date` | `pd.DataFrame` | Consulta carteira |
| `store_intermediaries` | `intermediaries, source` | `int` | Intermediarios |
| `store_asset_registry` | `assets, asset_type, source` | `int` | Registro de ativos |
| `get_asset_registry` | `asset_type` | `pd.DataFrame` | Consulta registro |
| `count_records` | — | `dict[str, int]` | Contagem por tabela |
| `export_to_parquet` | `output_path` | `Path` | Exporta para Parquet |

---

## 6. Data I/O — Carga e Exportacao

### PortfolioLoader

Modulo: `carteira_auto.data.loaders`

Importa a planilha de carteira e retorna um `Portfolio`.

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `__init__` | `file_path: Path \| None` | — | Default: `settings.paths.PORTFOLIO_FILE` |
| `load_portfolio` | — | `Portfolio` | Le abas "Carteira" e "Vendas". Decorado com `@log_execution` e `@timer`. |

Herda de `ExcelLoader` (context manager, `open()`, `close()`, `read_sheet()`).

```python
loader = PortfolioLoader()
portfolio = loader.load_portfolio()
print(f"{len(portfolio.assets)} ativos carregados")
```

### ExcelExporter

Modulo: `carteira_auto.data.exporters`

Exportador generico que copia planilha e aplica modificacoes preservando formatacao.

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `__init__` | `source_path: Path, output_path: Path` | — | Caminhos de origem e saida. |
| `open` | — | `ExcelExporter` | Copia planilha e abre para edicao. |
| `save` | — | `None` | Salva modificacoes. |
| `close` | — | `None` | Fecha workbook. |
| `get_sheet` | `sheet_name: str, required: bool = True` | `Worksheet \| None` | Obtem aba do workbook. |

Suporta context manager (`with ExcelExporter(...) as exp:`).

### PortfolioPriceExporter

Herda de `ExcelExporter`. Atualiza apenas a coluna "Preco Atual".

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `__init__` | `source_path: Path \| None, output_path: Path \| None` | — | Defaults de `settings`. |
| `export_prices` | `portfolio: Portfolio` | `Path` | Atualiza coluna e retorna path. Decorado com `@log_execution` e `@timer`. |

```python
exporter = PortfolioPriceExporter()
output_path = exporter.export_prices(portfolio)
```

### SnapshotStore

Modulo: `carteira_auto.data.storage`

Persiste metricas em JSON para consulta futura.

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `save_metadata` | `data: dict, snapshot_date: date \| None` | `Path` | Salva JSON com metricas do dia. |
| `load_metadata` | `snapshot_date: date` | `dict \| None` | Le JSON de uma data. |
| `list_snapshots` | — | `list[date]` | Lista datas disponiveis (JSON + Excel). |
| `get_time_series` | `metric: str, start, end` | `pd.DataFrame` | Agrega metrica em serie temporal. |

```python
store = SnapshotStore()
store.save_metadata({"total_value": 500000, "selic": 14.25})
snapshots = store.list_snapshots()
ts = store.get_time_series("total_value", start=date(2026, 1, 1))
```

---

## 7. Nodes — Unidades de Pipeline

Modulo: `carteira_auto.core.nodes`

Cada node e uma subclasse de `Node` com `name`, `dependencies` e `run(ctx)`.

### Portfolio Nodes

| Node | name | dependencies | Le do ctx | Escreve no ctx |
|---|---|---|---|---|
| `LoadPortfolioNode` | `load_portfolio` | `[]` | — | `portfolio: Portfolio`, `source_path: Path` |
| `FetchPricesNode` | `fetch_prices` | `[]` | `tickers: list[str]` (opcional) | `prices: dict[str, float \| None]` |
| `FetchPortfolioPricesNode` | `fetch_portfolio_prices` | `["load_portfolio"]` | `portfolio` | `portfolio` (atualizado), `prices` |
| `ExportPortfolioPricesNode` | `export_portfolio_prices` | `["fetch_portfolio_prices"]` | `portfolio`, `source_path` | `output_path: Path` |

```python
node = LoadPortfolioNode(source_path=Path("planilha.xlsx"))
node = ExportPortfolioPricesNode(output_path=Path("saida.xlsx"))
```

### Fetch Helpers

Modulo: `carteira_auto.core.nodes.fetch_helpers`

Helper de fallback hierarquico entre fetchers diferentes. Usado pelos IngestNodes.

| Classe/Funcao | Descricao |
|---|---|
| `FetchStrategy(name, callable, transform=None)` | Dataclass: identifica uma fonte (nome + funcao + transformacao opcional) |
| `FetchResult(data, source, attempts, errors)` | Dataclass: resultado do fallback. Properties: `success`, `used_fallback` |
| `fetch_with_fallback(strategies, fetch_logger, critical, label)` | Executa fetchers em ordem ate obter dados validos. Loga warning em fallback, error se todas falharem. |

```python
from carteira_auto.core.nodes.fetch_helpers import FetchStrategy, fetch_with_fallback

result = fetch_with_fallback(
    strategies=[
        FetchStrategy(name="bcb", callable=lambda: bcb.get_selic()),
        FetchStrategy(name="ddm", callable=lambda: ddm.get_macro_series("selic")),
    ],
    label="selic",
    critical=True,
)
if result.success:
    lake.store_macro("selic", result.data, source=result.source)
```

### Ingest Nodes

| Node | name | dependencies | Le do ctx | Escreve no ctx |
|---|---|---|---|---|
| `IngestPricesNode` | `ingest_prices` | `[]` | `portfolio` (opcional) | `ingest_prices_count: int`, `data_lake: DataLake` |
| `IngestMacroNode` | `ingest_macro` | `[]` | — | `ingest_macro_count: int`, `data_lake: DataLake` |
| `IngestFundamentalsNode` | `ingest_fundamentals` | `[]` | `portfolio` (opcional) | `ingest_fundamentals_count: int`, `data_lake: DataLake` |
| `IngestNewsNode` | `ingest_news` | `[]` | — | `ingest_news_count: int`, `data_lake: DataLake` |
| `IngestCVMNode` | `ingest_cvm` | `[]` | `portfolio` (opcional) | `ingest_cvm_count: int`, `data_lake: DataLake` |
| `IngestTesouroDiretoNode` | `ingest_tesouro_direto` | `[]` | — | `ingest_tesouro_direto_count: int`, `data_lake: DataLake` |

`IngestPricesNode` aceita `mode` no construtor: `"daily"` (5 dias) ou `"full"` (backfill historico).

Inclui tickers de benchmarks (`^BVSP`, `^GSPC`, `^IXIC`), commodities (`CL=F`, `GC=F`, `SI=F`, `ZS=F`), crypto (`BTC-USD`, `ETH-USD`), cambio (`BRL=X`, `EURBRL=X`, `DX-Y.NYB`) e universo de screening BR (~80 acoes).

```python
node = IngestPricesNode(mode="full", lookback_years=5)
ctx = node.run(ctx)
```

### Alert Node

| Node | name | dependencies | Le do ctx | Escreve no ctx |
|---|---|---|---|---|
| `EvaluateAlertsNode` | `evaluate_alerts` | `[]` | `portfolio`, `portfolio_metrics`, `macro_context` (todos opcionais) | `alerts: list[Alert]` |

### Storage Node

| Node | name | dependencies | Le do ctx | Escreve no ctx |
|---|---|---|---|---|
| `SaveSnapshotNode` | `save_snapshot` | `[]` | `portfolio_metrics`, `macro_context`, `market_metrics`, `risk_metrics` (opcionais) | `snapshot_path: Path` |

---

## 8. Analyzers — Analise

Modulo: `carteira_auto.analyzers`

Todos os analyzers sao subclasses de `Node` com `run(ctx)`.

### PortfolioAnalyzer

Calcula metricas consolidadas da carteira.

| Atributo | Valor |
|---|---|
| `name` | `"analyze_portfolio"` |
| `dependencies` | `["fetch_portfolio_prices"]` |
| **Le do ctx** | `portfolio: Portfolio` |
| **Escreve no ctx** | `portfolio_metrics: PortfolioMetrics` |

Calcula: valor total, custo total, retorno, dividend yield, alocacao por classe vs meta.

### RiskAnalyzer

Calcula metricas de risco via dados historicos de 5 anos.

| Atributo | Valor |
|---|---|
| `name` | `"analyze_risk"` |
| `dependencies` | `["fetch_portfolio_prices", "analyze_portfolio"]` |
| **Le do ctx** | `portfolio: Portfolio` |
| **Escreve no ctx** | `risk_metrics: RiskMetrics` |

Calcula: volatilidade anualizada, VaR 95% e 99%, Sharpe ratio (rf = CDI diario), max drawdown, beta contra IBOV.

### MacroAnalyzer

Consolida contexto macroeconomico a partir de BCB e IBGE.

| Atributo | Valor |
|---|---|
| `name` | `"analyze_macro"` |
| `dependencies` | `[]` |
| **Le do ctx** | — (busca dados diretamente) |
| **Escreve no ctx** | `macro_context: MacroContext` |

Busca 11 indicadores: Selic, CDI 12m, IPCA 12m, IGP-M 12m, INPC 12m, poupanca, TR, PTAX compra/venda (BCB), PIB trimestral, desocupacao PNAD (IBGE). Falhas parciais sao registradas em `ctx["_errors"]`.

### MarketAnalyzer

Calcula retornos de 8 benchmarks: IBOV, IFIX, CDI, S&P 500, Dolar/BRL, Ouro, Selic acumulada, PTAX atual.

| Atributo | Valor |
|---|---|
| `name` | `"analyze_market"` |
| `dependencies` | `[]` |
| **Le do ctx** | — (busca dados diretamente) |
| **Escreve no ctx** | `market_metrics: MarketMetrics` |

Busca: IBOV 5a (Yahoo), IFIX 5a (Yahoo), CDI 5a (BCB), S&P 500 5a (Yahoo), USD/BRL 5a (Yahoo), Ouro 5a (Yahoo), Selic 5a (BCB), PTAX corrente (BCB). Falhas parciais registradas em `ctx["_errors"]`.

### Rebalancer

Gera recomendacoes de compra/venda.

| Atributo | Valor |
|---|---|
| `name` | `"rebalance"` |
| `dependencies` | `["analyze_portfolio"]` |
| **Le do ctx** | `portfolio: Portfolio`, `portfolio_metrics: PortfolioMetrics` |
| **Escreve no ctx** | `rebalance_recommendations: list[RebalanceRecommendation]` |

Logica: distribui compra/venda entre ativos da classe com desvio acima do threshold (5%), respeitando `MIN_TRADE_VALUE` (R$ 100).

### MarketSectorAnalyzer

Analisa performance de setores do mercado financeiro.

| Atributo | Valor |
|---|---|
| `name` | `"analyze_market_sectors"` |
| `dependencies` | `[]` |
| **Le do ctx** | — |
| **Escreve no ctx** | `market_sectors: list[SectorIndicator]` |

### EconomicSectorAnalyzer

Analisa setores da economia real via IBGE.

| Atributo | Valor |
|---|---|
| `name` | `"analyze_economic_sectors"` |
| `dependencies` | `[]` |
| **Le do ctx** | — |
| **Escreve no ctx** | `economic_sectors: list[EconomicSectorIndicator]` |

### CurrencyAnalyzer

Analisa cenario cambial: USD/BRL, DXY, carry trade Selic-Fed, taxa cambio real efetiva.

| Atributo | Valor |
|---|---|
| `name` | `"analyze_currency"` |
| `dependencies` | `[]` |
| **Le do ctx** | — (busca diretamente via BCBFetcher, FREDFetcher, YahooFinanceFetcher) |
| **Escreve no ctx** | `currency_metrics: CurrencyMetrics` |

Calcula: PTAX compra/venda, variacao USD/BRL (1m, 3m, 12m), DXY e variacao, Selic, Fed Funds Rate, carry spread, taxa cambio real efetiva.

### CommodityAnalyzer

Analisa precos e ciclo de commodities: petroleo, ouro, prata, soja, milho, trigo.

| Atributo | Valor |
|---|---|
| `name` | `"analyze_commodities"` |
| `dependencies` | `[]` |
| **Le do ctx** | — (busca diretamente via YahooFinanceFetcher) |
| **Escreve no ctx** | `commodity_metrics: CommodityMetrics` |

Calcula: precos correntes (WTI, Brent, ouro, prata, soja, milho, trigo), variacoes (1m, 3m, 12m), indice composto, sinal de ciclo (expansion/peak/contraction/trough).

### FiscalAnalyzer

Analisa situacao fiscal brasileira: divida/PIB, resultado primario, trajetoria.

| Atributo | Valor |
|---|---|
| `name` | `"analyze_fiscal"` |
| `dependencies` | `[]` |
| **Le do ctx** | — (busca diretamente via BCBFetcher) |
| **Escreve no ctx** | `fiscal_metrics: FiscalMetrics` |

Calcula: divida bruta/PIB, divida liquida/PIB, resultado primario/PIB, resultado nominal, juros nominais/PIB, variacao 12m, trajetoria fiscal (improving a severe).

---

## 9. Alerts — Sistema de Alertas

Modulo: `carteira_auto.alerts`

### AlertRule

Regra de alerta (Pydantic model).

| Campo | Tipo | Descricao |
|---|---|---|
| `name` | `str` | Identificador da regra |
| `condition` | `str` | Tipo: `"deviation_above"`, `"price_drop"`, `"indicator_change"` |
| `threshold` | `float` | Limiar de disparo |
| `severity` | `str` | `"info"`, `"warning"`, `"critical"` |
| `message_template` | `str` | Template com placeholders `{classe}`, `{deviation}`, `{ticker}`, etc. |

### Alert

Alerta disparado (Pydantic model).

| Campo | Tipo | Descricao |
|---|---|---|
| `rule` | `AlertRule` | Regra que gerou o alerta |
| `triggered_at` | `datetime` | Momento do disparo |
| `value` | `float` | Valor que disparou |
| `message` | `str` | Mensagem formatada |

### AlertEngine

Engine que avalia regras e gera alertas.

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `register_rule` | `rule: AlertRule` | `None` | Registra uma regra. |
| `register_many` | `rules: list[AlertRule]` | `None` | Registra multiplas regras. |
| `evaluate` | `ctx: dict` | `list[Alert]` | Avalia todas as regras contra o contexto. |

Condicoes suportadas:
- `deviation_above`: verifica `portfolio_metrics.allocations` com desvio acima do threshold.
- `price_drop`: verifica queda de preco vs preco medio.
- `indicator_change`: reservado para comparacao com snapshot anterior.

### AlertChannel (ABC)

Interface base para canais de notificacao.

| Metodo | Parametros | Retorno | Descricao |
|---|---|---|---|
| `send` | `alert: Alert` | `None` | *Abstrato.* Envia um alerta. |
| `send_many` | `alerts: list[Alert]` | `None` | Envia multiplos alertas. |

Implementacoes disponiveis:

| Canal | Descricao |
|---|---|
| `ConsoleChannel` | Imprime alertas no console com icones de severidade. |
| `LogChannel` | Loga alertas via `logging` (critical/warning/info). |

### Regras pre-definidas

Modulo: `carteira_auto.alerts.rules`

| Funcao | Parametros | Descricao |
|---|---|---|
| `rebalance_alert` | `threshold: float = 0.05` | Alerta quando desvio de alocacao excede threshold. |
| `price_drop_alert` | `threshold: float = 0.10` | Alerta quando preco cai mais que threshold vs preco medio. |
| `selic_change_alert` | `threshold: float = 0.25` | Alerta quando Selic muda mais que threshold pontos. |

```python
from carteira_auto.alerts import AlertEngine
from carteira_auto.alerts.rules import rebalance_alert, price_drop_alert

engine = AlertEngine()
engine.register_many([
    rebalance_alert(threshold=0.05),
    price_drop_alert(threshold=0.10),
])
alerts = engine.evaluate(ctx)
```

---

## 10. Utils — Utilitarios

### Decorators

Modulo: `carteira_auto.utils.decorators`

| Decorator | Parametros | Descricao |
|---|---|---|
| `@timer` | — | Mede e loga tempo de execucao. |
| `@retry` | `max_attempts=3, delay=1.0` | Tenta novamente com exponential backoff. |
| `@rate_limit` | `calls_per_minute=60` | Limita taxa de requisicoes (thread-safe). |
| `@timeout` | `seconds=30` | Timeout via `signal.SIGALRM` (POSIX). |
| `@fallback` | `fallback_func: Callable` | Executa funcao alternativa em caso de falha. |
| `@validate_tickers` | — | Valida tickers (detecta `self` automaticamente). |
| `@validate_positive_value` | — | Valida que valores financeiros sao positivos. |
| `@validate_allocation_sum` | — | Valida que soma das alocacoes e ~100%. |
| `@log_execution` | — | Loga inicio e fim/erro de funcao. |
| `@cache_result` | `ttl_seconds=300, max_size=1000` | Cache LRU com TTL e limpeza automatica. |
| `@cache_by_ticker` | `ttl_seconds=300, max_size=1000` | Cache LRU por ticker com TTL. |

```python
from carteira_auto.utils.decorators import retry, rate_limit, cache_result

@retry(max_attempts=3, delay=1.0)
@rate_limit(calls_per_minute=30)
@cache_result(ttl_seconds=3600)
def buscar_dados(url: str) -> dict:
    ...
```

### Logger

Modulo: `carteira_auto.utils.logger`

| Funcao | Parametros | Retorno | Descricao |
|---|---|---|---|
| `get_logger` | `name: str \| None` | `logging.Logger` | Factory function. Recomendado: `get_logger(__name__)`. |
| `setup_logging` | — | `None` | Configura logging global (Rich console + RotatingFile). |
| `initialize_logging` | `force: bool = False` | `None` | Inicializa logging (idem se `force=False` e ja inicializado). |

Classes auxiliares: `ErrorFilter` (>= ERROR), `InfoFilter` (< ERROR).

```python
from carteira_auto.utils import get_logger
logger = get_logger(__name__)
logger.info("Mensagem informativa")
```

### Helpers

Modulo: `carteira_auto.utils.helpers`

| Funcao | Parametros | Retorno | Descricao |
|---|---|---|---|
| `parse_brl_currency` | `value: str` | `Decimal` | Converte "R$ 1.234,56" para `Decimal`. |
| `format_currency` | `value: float, symbol="R$"` | `str` | Formata como "R$ 1.234,56". |
| `format_percentage` | `value: float, decimals=2` | `str` | Formata como "+12,34%" ou "-5,00%". |
| `validate_ticker` | `ticker: str` | `tuple[bool, str]` | Valida ticker e retorna tipo (ex: `(True, "B3_STOCK")`). |
| `is_market_open` | — | `bool` | Verifica se B3 esta aberta (dia util, 10-17h). |
| `days_between_dates` | `start: date, end: date` | `int` | Dias uteis entre datas (aproximado). |

```python
from carteira_auto.utils.helpers import validate_ticker, format_currency
ok, tipo = validate_ticker("PETR4")  # (True, "B3_STOCK")
print(format_currency(1234.56))  # "R$ 1.234,56"
```

---

## 11. CLI — Interface de Linha de Comando

Modulo: `carteira_auto.cli`

Entrypoint: `carteira` (definido em `pyproject.toml`).

### Comandos

| Comando | Argumentos | Descricao |
|---|---|---|
| `carteira run <pipeline>` | `-s SOURCE`, `-o OUTPUT`, `--dry-run` | Executa um pipeline via DAG engine. |
| `carteira list` | — | Lista pipelines disponiveis com descricoes. |
| `carteira dashboard` | — | Abre dashboard Streamlit (`dashboards/app.py`). |
| `carteira ingest` | `--mode {daily,full}` | Ingere dados no DataLake (precos + macro + fundamentos + noticias). |
| `carteira update-prices` | `-s SOURCE`, `-o OUTPUT` | Alias para `run update-excel-portfolio-prices`. |
| `carteira --version` | — | Mostra versao. |

```bash
# Atualizar precos na planilha
carteira run update-excel-portfolio-prices

# Dry run (mostra plano sem executar)
carteira run analyze --dry-run

# Ingestao historica completa
carteira ingest --mode full

# Listar pipelines
carteira list
```

---

## 12. Registry — Pipeline Presets

Modulo: `carteira_auto.core.registry`

### PIPELINE_PRESETS

Mapeamento de nomes CLI para nodes terminais do DAG.

| Pipeline CLI | Node Terminal | Descricao |
|---|---|---|
| `update-excel-portfolio-prices` | `export_portfolio_prices` | Atualiza precos e exporta planilha Excel |
| `analyze` | `analyze_portfolio` | Analisa metricas da carteira (alocacao, retorno) |
| `rebalance` | `rebalance` | Gera recomendacoes de rebalanceamento |
| `risk` | `analyze_risk` | Calcula metricas de risco (VaR, Sharpe, beta) |
| `macro` | `analyze_macro` | Analisa 11 indicadores macro (Selic, CDI, IPCA, IGP-M, INPC, poupanca, TR, PTAX, PIB, desocupacao) |
| `market` | `analyze_market` | Analisa 8 benchmarks (IBOV, IFIX, CDI, S&P500, USD/BRL, Ouro, Selic acum., PTAX) |
| `market-sectors` | `analyze_market_sectors` | Analisa performance por setor de mercado |
| `economic-sectors` | `analyze_economic_sectors` | Analisa setores da economia real (IBGE) |
| `ingest-prices` | `ingest_prices` | Ingere precos historicos no DataLake (Yahoo Finance) |
| `ingest-macro` | `ingest_macro` | Ingere indicadores macro no DataLake (BCB, IBGE) |
| `ingest-fundamentals` | `ingest_fundamentals` | Ingere dados fundamentalistas no DataLake (Yahoo Finance) |
| `ingest-news` | `ingest_news` | Ingere noticias financeiras no DataLake (NewsAPI, RSS) |
| `currency` | `analyze_currency` | Analisa cambio, DXY, carry trade e taxa real efetiva |
| `commodities` | `analyze_commodities` | Analisa precos e ciclo de commodities (petroleo, ouro, agro) |
| `fiscal` | `analyze_fiscal` | Analisa divida/PIB, resultado primario e trajetoria fiscal |

### Funcoes do Registry

| Funcao | Parametros | Retorno | Descricao |
|---|---|---|---|
| `create_engine` | `source_path: Path \| None, output_path: Path \| None` | `DAGEngine` | Cria engine com todos os nodes registrados. |
| `get_terminal_node` | `pipeline_name: str` | `str` | Retorna node terminal. Levanta `KeyError` se nao encontrado. |
| `list_pipelines` | — | `dict[str, str]` | Lista pipelines com descricoes. |

```python
from carteira_auto.core.registry import create_engine, get_terminal_node

engine = create_engine()
terminal = get_terminal_node("analyze")
ctx = engine.run(terminal)
```

---

## Chaves do PipelineContext — Referencia Cruzada

Tabela consolidada de todas as chaves lidas e escritas no contexto.

| Chave | Tipo | Escrito por | Lido por |
|---|---|---|---|
| `portfolio` | `Portfolio` | `LoadPortfolioNode`, `FetchPortfolioPricesNode` | `FetchPortfolioPricesNode`, `ExportPortfolioPricesNode`, `PortfolioAnalyzer`, `RiskAnalyzer`, `Rebalancer`, `IngestPricesNode`, `EvaluateAlertsNode` |
| `source_path` | `Path` | `LoadPortfolioNode` | `ExportPortfolioPricesNode` |
| `prices` | `dict[str, float \| None]` | `FetchPricesNode`, `FetchPortfolioPricesNode` | — |
| `tickers` | `list[str]` | (externo) | `FetchPricesNode` |
| `output_path` | `Path` | `ExportPortfolioPricesNode` | — |
| `portfolio_metrics` | `PortfolioMetrics` | `PortfolioAnalyzer` | `Rebalancer`, `EvaluateAlertsNode`, `SaveSnapshotNode` |
| `risk_metrics` | `RiskMetrics` | `RiskAnalyzer` | `SaveSnapshotNode` |
| `macro_context` | `MacroContext` | `MacroAnalyzer` | `EvaluateAlertsNode`, `SaveSnapshotNode` |
| `market_metrics` | `MarketMetrics` | `MarketAnalyzer` | `SaveSnapshotNode` |
| `market_sectors` | `list[SectorIndicator]` | `MarketSectorAnalyzer` | — |
| `economic_sectors` | `list[EconomicSectorIndicator]` | `EconomicSectorAnalyzer` | — |
| `rebalance_recommendations` | `list[RebalanceRecommendation]` | `Rebalancer` | — |
| `alerts` | `list[Alert]` | `EvaluateAlertsNode` | — |
| `snapshot_path` | `Path` | `SaveSnapshotNode` | — |
| `data_lake` | `DataLake` | `IngestPricesNode`, `IngestMacroNode`, etc. | Todos os IngestNodes |
| `ingest_prices_count` | `int` | `IngestPricesNode` | — |
| `ingest_macro_count` | `int` | `IngestMacroNode` | — |
| `ingest_fundamentals_count` | `int` | `IngestFundamentalsNode` | — |
| `ingest_news_count` | `int` | `IngestNewsNode` | — |
| `currency_metrics` | `CurrencyMetrics` | `CurrencyAnalyzer` | — |
| `commodity_metrics` | `CommodityMetrics` | `CommodityAnalyzer` | — |
| `fiscal_metrics` | `FiscalMetrics` | `FiscalAnalyzer` | — |
| `ingest_cvm_count` | `int` | `IngestCVMNode` | — |
| `ingest_tesouro_direto_count` | `int` | `IngestTesouroDiretoNode` | — |
| `_errors` | `dict[str, str]` | `DAGEngine`, analyzers | `PipelineContext.has_errors` |
