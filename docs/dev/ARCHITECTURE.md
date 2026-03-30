# Arquitetura — carteira_auto v0.2.1+ (Fase A — Fetcher Maximization Sprint)

> Referência compacta para Claude Code. Atualizar ao final de cada fase.

## Módulos e responsabilidades

### core/ — Motor do sistema
| Arquivo | Exporta | Papel |
|---------|---------|-------|
| engine.py | DAGEngine(fail_fast), Node, PipelineContext, NodeExecutionError | Motor DAG com topological sort (Kahn), error handling per-node, Node.__init_subclass__() isola deps por subclass |
| result.py | Ok[T], Err[T], Result (type alias) | Tipo Result funcional para operações falíveis |
| models/portfolio.py | Asset (+ 17 campos fundamentalistas), Portfolio, SoldAsset | Modelos da planilha Excel — validação Pydantic estrita (field_validator para ticker, preços, percentages). Asset inclui campos fundamentalistas (P/L, P/VP, ROE, DY, beta, etc.) populados via Yahoo Finance. |
| models/analysis.py | PortfolioMetrics, RiskMetrics, MacroContext (12 campos), MarketMetrics (8 campos), CurrencyMetrics (11 campos), CommodityMetrics (18 campos), FiscalMetrics (9 campos), RebalanceRecommendation, AllocationResult | Outputs dos analyzers — AllocationResult.action é Literal["comprar","vender","manter"], RiskMetrics.is_complete(), RebalanceRecommendation.action é Literal["comprar","vender"] |
| models/economic.py | MacroIndicator, MarketIndicator, SectorIndicator, EconomicSectorIndicator | Indicadores econômicos |
| registry.py | create_engine(), PIPELINE_PRESETS | Mapeamento CLI → node terminal |
| nodes/portfolio_nodes.py | LoadPortfolioNode, FetchPricesNode, FetchPortfolioPricesNode, ExportPortfolioPricesNode | Operações de carteira — FetchPortfolioPricesNode usa model_copy() (sem mutação in-place) |
| nodes/ingest_nodes.py | IngestPricesNode, IngestMacroNode, IngestFundamentalsNode | Ingestão de dados no DataLake |
| nodes/fetch_helpers.py | FetchStrategy, FetchResult, fetch_with_fallback() | Helper de fallback hierárquico entre fetchers — usado pelos IngestNodes para orquestrar tentativas entre fontes diferentes com logging de proveniência |
| nodes/alert_nodes.py | EvaluateAlertsNode | Avaliação de regras de alerta |
| nodes/storage_nodes.py | SaveSnapshotNode | Persistência de snapshots JSON |
| pipelines/update_excel_prices.py | UpdateExcelPricesPipeline | Pipeline legado (backward compat) |

### data/fetchers/ — Coleta de dados externos
| Arquivo | Classe | API | Rate limit | Cache TTL |
|---------|--------|-----|------------|-----------|
| yahoo_fetcher.py | YahooFinanceFetcher | yfinance | 30 req/min | 5min (preços), 24h (histórico) |
| bcb_fetcher.py | BCBFetcher | SGS API + python-bcb | 30 req/min | 1h |
| ibge_fetcher.py | IBGEFetcher | SIDRA API + sidrapy | 30 req/min | 2h |
| fred_fetcher.py | FREDFetcher | FRED API | 120 req/min | 24h |
| cvm_fetcher.py | CVMFetcher | CVM Dados Abertos | 30 req/min | 24h |
| tesouro_fetcher.py | TesouroDiretoFetcher | Tesouro API + CKAN | 30 req/min | 1h |
| ddm_fetcher.py | DDMFetcher | DDM stock screening | N/A | 24h |
| tradingcomdados_fetcher.py | TradingComDadosFetcher | tradingcomdados (B3) | 30 req/min | 1h (preços), 24h (índices) |

### data/lake/ — DataLake (SQLite)
| Arquivo | Classe | Papel | Tabelas |
|---------|--------|-------|---------|
| base.py | DataLake | Classe agregadora — acesso unificado aos 5 sub-lakes | — |
| price_lake.py | PriceLake | OHLCV em SQLite | prices |
| macro_lake.py | MacroLake | Séries temporais macroeconômicas genéricas | macro_indicators, macro_metadata |
| fundamentals_lake.py | FundamentalsLake | Dados fundamentalistas por ticker | fundamentals, financial_statements |
| news_lake.py | NewsLake | Notícias e sentimento | news |
| reference_lake.py | ReferenceLake | Dados de referência estruturais (não-temporais) | index_compositions, focus_expectations, analyst_targets, upgrades_downgrades, lending_rates, cnae_classifications, ticker_cnpj_map, major_holders, fund_registry, fund_portfolios, intermediaries, asset_registry |

### data/ — Persistência e I/O
| Arquivo | Classe | Papel |
|---------|--------|-------|
| loaders/excel_loader.py | ExcelLoader, PortfolioLoader | Lê planilha Excel → Portfolio |
| exporters/excel_exporter.py | ExcelExporter, PortfolioPriceExporter | Portfolio → planilha Excel |
| storage/snapshot_store.py | SnapshotStore | JSON snapshots em data/outputs/snapshots/ |

### analyzers/ — Transformam dados em métricas (Nodes DAG)
| Arquivo | Node name | Dependencies | Produz no ctx |
|---------|-----------|-------------|---------------|
| portfolio_analyzer.py | analyze_portfolio | [fetch_portfolio_prices] | ctx["portfolio_metrics"] |
| risk_analyzer.py | analyze_risk | [fetch_portfolio_prices, analyze_portfolio] | ctx["risk_metrics"] |
| macro_analyzer.py | analyze_macro | [] | ctx["macro_context"] |
| market_analyzer.py | analyze_market | [] | ctx["market_metrics"] |
| market_sector_analyzer.py | analyze_market_sectors | [] | ctx["market_sectors"] |
| economic_sector_analyzer.py | analyze_economic_sectors | [] | ctx["economic_sectors"] |
| rebalancer.py | rebalance | [analyze_portfolio] | ctx["rebalance_recommendations"] |
| currency_analyzer.py | analyze_currency | [] | ctx["currency_metrics"] |
| commodity_analyzer.py | analyze_commodities | [] | ctx["commodity_metrics"] |
| fiscal_analyzer.py | analyze_fiscal | [] | ctx["fiscal_metrics"] |

### alerts/ — Sistema de alertas
| Arquivo | Exporta | Papel |
|---------|---------|-------|
| engine.py | AlertEngine, AlertRule, Alert | Avalia regras contra o contexto |
| channels.py | ConsoleChannel, LogChannel, AlertChannel(ABC) | Canais de notificação |
| rules.py | price_drop_alert(), rebalance_alert() | Factories de regras |

### config/ — Configurações centralizadas
| Arquivo | Exporta | Papel |
|---------|---------|-------|
| settings.py | Settings (dataclass), PathsConfig, YahooFetcherConfig, BCBConfig, IBGEConfig, DDMConfig, FREDConfig, TradingComDadosConfig, PortfolioConfig, LoggingConfig | Toda configuração do sistema — PortfolioConfig inclui RISK_FREE_DAILY e MIN_TRADE_VALUE |
| constants.py | Constants (BCB_SERIES_CODES=31, IBGE_TABLE_IDS=16, FRED_SERIES=30, INDEX_CODES=6) | Colunas de planilha, field maps, séries BCB expandidas, tabelas IBGE expandidas, séries FRED com metadados, códigos de índices, feriados B3 |

### utils/ — Utilitários transversais
| Arquivo | Exporta | Usar quando |
|---------|---------|-------------|
| decorators.py | @timer, @retry, @rate_limit, @timeout, @fallback, @validate_tickers, @log_execution, @cache_result, @cache_by_ticker | Todo fetcher e analyzer novo |
| logger.py | get_logger(name), setup_logging() | Todo módulo novo: `logger = get_logger(__name__)` |
| helpers.py | validate_ticker() | Validação de tickers B3 |

## Pipelines registradas (CLI)
| Comando | Node terminal | Descrição |
|---------|--------------|-----------|
| update-excel-portfolio-prices | export_portfolio_prices | Atualiza preços e exporta Excel |
| analyze | analyze_portfolio | Métricas da carteira |
| rebalance | rebalance | Recomendações de rebalanceamento |
| risk | analyze_risk | VaR, Sharpe, beta |
| macro | analyze_macro | 11 indicadores (Selic, CDI, IPCA, IGP-M, INPC, poupança, TR, PTAX, PIB, desocupação) |
| market | analyze_market | 8 benchmarks (IBOV, IFIX, CDI, S&P500, USD/BRL, Ouro, Selic acum., PTAX) |
| market-sectors | analyze_market_sectors | Performance setorial |
| economic-sectors | analyze_economic_sectors | Setores da economia real |
| currency | analyze_currency | Câmbio, DXY, carry trade e taxa real efetiva |
| commodities | analyze_commodities | Preços e ciclo de commodities (petróleo, ouro, agro) |
| fiscal | analyze_fiscal | Dívida/PIB, resultado primário e trajetória fiscal |
| ingest-prices | ingest_prices | Ingestão de preços no DataLake |
| ingest-macro | ingest_macro | Ingestão de indicadores macro no DataLake |
| ingest-fundamentals | ingest_fundamentals | Ingestão de dados fundamentalistas no DataLake |
| ingest-news | ingest_news | Ingestão de notícias no DataLake |

## Paths do sistema
| Variável | Default | Uso |
|----------|---------|-----|
| ROOT_DIR | repo root | Base |
| DATA_DIR | ROOT_DIR/data | Dados |
| RAW_DATA_DIR | DATA_DIR/raw | Planilhas originais |
| PORTFOLIOS_DIR | DATA_DIR/outputs/portfolios | Excel exportados |
| SNAPSHOTS_DIR | DATA_DIR/outputs/snapshots | JSON snapshots |
| LOGS_DIR | DATA_DIR/outputs/logs | Arquivos de log |
| PORTFOLIO_FILE | RAW_DATA_DIR/"Carteira 2026.xlsx" | Planilha master |

## PipelineContext — chaves usadas
| Chave | Tipo | Quem produz | Quem consome |
|-------|------|-------------|-------------|
| portfolio | Portfolio | LoadPortfolioNode | Todos os analyzers |
| source_path | Path | LoadPortfolioNode | ExportNode |
| prices | dict[str, float] | FetchPricesNode | — |
| portfolio_metrics | PortfolioMetrics | PortfolioAnalyzer | Rebalancer, SaveSnapshot |
| risk_metrics | RiskMetrics | RiskAnalyzer | SaveSnapshot |
| macro_context | MacroContext | MacroAnalyzer | SaveSnapshot, Alerts |
| market_metrics | MarketMetrics | MarketAnalyzer | SaveSnapshot |
| market_sectors | list[SectorIndicator] | MarketSectorAnalyzer | — |
| economic_sectors | list[EconomicSectorIndicator] | EconomicSectorAnalyzer | — |
| rebalance_recommendations | list[RebalanceRecommendation] | Rebalancer | — |
| currency_metrics | CurrencyMetrics | CurrencyAnalyzer | — |
| commodity_metrics | CommodityMetrics | CommodityAnalyzer | — |
| fiscal_metrics | FiscalMetrics | FiscalAnalyzer | — |
| alerts | list[Alert] | EvaluateAlertsNode | — |
| snapshot_path | Path | SaveSnapshotNode | — |
| _errors | dict[str, str] | DAGEngine (fail_fast=False) | PipelineContext.errors / has_errors |

## Testes — cobertura atual
| Arquivo | Qtd | Escopo |
|---------|-----|--------|
| test_models.py | 54 | Result type (Ok/Err), validação Asset/Portfolio, todos os model types |
| test_analyzers.py | 19 | DAGEngine error handling, todos os 7 analyzers |
| test_fetchers.py | 17 | Yahoo normalize, prices, historical |
| test_cli.py | 15 | Parser, commands, main |
| test_decorators.py | 20 | Todos os decorators |
| test_integrations.py | 8 | E2E pipeline, dry_run, presets |
| test_lake.py | — | PriceLake, MacroLake, FundamentalsLake, NewsLake |
| test_cvm_fetcher.py | — | CVMFetcher |
| test_fred_fetcher.py | — | FREDFetcher |
| test_currency_analyzer.py | 9 | CurrencyAnalyzer (PTAX, DXY, carry spread, falhas parciais) |
| test_commodity_analyzer.py | 8 | CommodityAnalyzer (preços, ciclo, índice, falhas) |
| test_fiscal_analyzer.py | 16 | FiscalAnalyzer (métricas, trajetória, variação 12m, falhas) |
| test_fetch_helpers.py | 22 | FetchStrategy, FetchResult, fetch_with_fallback (fallback, transform, critical mode) |
| test_reference_lake.py | 39 | ReferenceLake — todas as 12 tabelas (composições, Focus, targets, holders, fundos, ativos) |
