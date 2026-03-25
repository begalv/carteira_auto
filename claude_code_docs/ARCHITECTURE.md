# Arquitetura — carteira_auto v0.1.0

> Referência compacta para Claude Code. Atualizar ao final de cada fase.

## Módulos e responsabilidades

### core/ — Motor do sistema (NÃO alterar)
| Arquivo | Exporta | Papel |
|---------|---------|-------|
| engine.py | DAGEngine, Node, PipelineContext | Motor DAG com topological sort (Kahn) |
| models/portfolio.py | Asset, Portfolio, SoldAsset | Modelos da planilha Excel |
| models/analysis.py | PortfolioMetrics, RiskMetrics, MacroContext, MarketMetrics, RebalanceRecommendation | Outputs dos analyzers |
| models/economic.py | MacroIndicator, MarketIndicator, SectorIndicator, EconomicSectorIndicator | Indicadores econômicos |
| registry.py | create_engine(), PIPELINE_PRESETS | Mapeamento CLI → node terminal |
| nodes/portfolio_nodes.py | LoadPortfolioNode, FetchPricesNode, FetchPortfolioPricesNode, ExportPortfolioPricesNode | Operações de carteira |
| nodes/alert_nodes.py | EvaluateAlertsNode | Avaliação de regras de alerta |
| nodes/storage_nodes.py | SaveSnapshotNode | Persistência de snapshots JSON |
| pipelines/update_excel_prices.py | UpdateExcelPricesPipeline | Pipeline legado (backward compat) |

### data/fetchers/ — Coleta de dados externos
| Arquivo | Classe | API | Rate limit | Cache TTL |
|---------|--------|-----|------------|-----------|
| yahoo_fetcher.py | YahooFinanceFetcher | yfinance | 30 req/min | 5min (preços), 24h (histórico) |
| bcb_fetcher.py | BCBFetcher | SGS API | 30 req/min | 1h |
| ibge_fetcher.py | IBGEFetcher | SIDRA API | 30 req/min | 2h |

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

### alerts/ — Sistema de alertas
| Arquivo | Exporta | Papel |
|---------|---------|-------|
| engine.py | AlertEngine, AlertRule, Alert | Avalia regras contra o contexto |
| channels.py | ConsoleChannel, LogChannel, AlertChannel(ABC) | Canais de notificação |
| rules.py | price_drop_alert(), rebalance_alert() | Factories de regras |

### config/ — Configurações centralizadas
| Arquivo | Exporta | Papel |
|---------|---------|-------|
| settings.py | Settings (dataclass), PathsConfig, YahooFetcherConfig, BCBConfig, IBGEConfig, DDMConfig, PortfolioConfig, LoggingConfig | Toda configuração do sistema |
| constants.py | Constants | Colunas de planilha, field maps, séries BCB, tabelas IBGE, feriados B3 |

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
| macro | analyze_macro | Selic, IPCA, câmbio, PIB |
| market | analyze_market | IBOV, IFIX, CDI |
| market-sectors | analyze_market_sectors | Performance setorial |
| economic-sectors | analyze_economic_sectors | Setores da economia real |

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
| alerts | list[Alert] | EvaluateAlertsNode | — |
| snapshot_path | Path | SaveSnapshotNode | — |
