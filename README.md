# carteira_auto

Sistema de automacao e analise de carteiras de investimentos para emancipacao financeira de pessoa fisica no Brasil.

## Visao Geral

O `carteira_auto` e um sistema modular que automatiza a coleta, analise e gestao de uma carteira de investimentos diversificada. Projetado para investidores PF brasileiros, integra multiplas fontes de dados macroeconomicos, fundamentalistas e de mercado em um pipeline orquestrado por DAG.

### Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│  CLI (carteira) / Dashboard Streamlit                       │
├─────────────────────────────────────────────────────────────┤
│  DAGEngine  ->  Nodes (Load -> Fetch -> Analyze -> Export)  │
├──────────┬──────────┬───────────────┬───────────────────────┤
│ Analyzers│ Alerts   │  DataLake     │  Strategies (futuro)  │
│10 modulos│ Engine   │  SQLite       │  Optimizer            │
├──────────┴──────────┴───────────────┴───────────────────────┤
│  Fetchers: Yahoo | BCB | IBGE | FRED | CVM | DDM | Tesouro │
├─────────────────────────────────────────────────────────────┤
│  Config (Settings + Constants) | Utils (Decorators + Logger)│
└─────────────────────────────────────────────────────────────┘
```

### Fontes de Dados

| Fonte | Fetcher | Dados | Autenticacao |
|-------|---------|-------|-------------|
| **Yahoo Finance** | `YahooFinanceFetcher` | OHLCV, fundamentalistas, dividendos, splits | Livre |
| **BCB (SGS)** | `BCBFetcher` | Selic, CDI, IPCA, IGP-M, PTAX, TR | Livre |
| **IBGE (SIDRA)** | `IBGEFetcher` | PIB, desemprego, IPCA detalhado | Livre |
| **FRED** | `FREDFetcher` | Fed Funds, Treasuries, VIX, CPI, cambio | API key (gratuita) |
| **CVM** | `CVMFetcher` | Cadastro empresas, DFP, DRE, fluxo de caixa | Livre |
| **Dados de Mercado** | `DDMFetcher` | Cotacoes, DRE, indicadores, focus | API key |
| **Tesouro Direto** | `TesouroDiretoFetcher` | Taxas, titulos, historico, NTN-B | Livre |

### Analyzers

| Analyzer | Analise |
|----------|---------|
| `PortfolioAnalyzer` | Valor total, retorno, dividend yield, alocacao vs metas |
| `RiskAnalyzer` | Volatilidade, VaR 95/99, Sharpe, max drawdown, beta |
| `MacroAnalyzer` | Contexto macro BR (Selic, IPCA, PTAX, PIB) |
| `MarketAnalyzer` | Benchmarks (IBOV, IFIX, CDI) |
| `Rebalancer` | Desvios de alocacao, recomendacoes de compra/venda |
| `MarketSectorAnalyzer` | Performance setorial via Yahoo |
| `EconomicSectorAnalyzer` | Crescimento setorial via IBGE |
| `CurrencyAnalyzer` | Cambio USD/BRL, DXY, carry trade Selic-Fed, cambio real efetivo |
| `CommodityAnalyzer` | Petroleo (WTI/Brent), ouro, prata, soja, milho, trigo, ciclo 5y |
| `FiscalAnalyzer` | Divida/PIB, resultado primario, juros nominais, trajetoria fiscal |

## Instalacao

### Pre-requisitos

- Python 3.10+
- pip ou uv

### Setup

```bash
# Clone o repositorio
git clone https://github.com/begalv/carteira_auto.git
cd carteira_auto

# Crie o ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Instale dependencias
pip install -e ".[dev]"

# Configure as variaveis de ambiente
cp .env.example .env
# Edite .env com suas API keys
```

### API Keys

| Servico | Variavel | Como obter |
|---------|----------|-----------|
| FRED | `FRED_API_KEY` | [fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html) |
| Dados de Mercado | `DADOS_MERCADO_API_KEY` | [dadosdemercado.com.br/api](https://www.dadosdemercado.com.br/api) |

## Uso

### CLI

```bash
# Listar pipelines disponiveis
python -m carteira_auto list

# Analise macro (Selic, IPCA, cambio, PIB)
python -m carteira_auto run macro

# Analise fiscal (divida/PIB, resultado primario)
python -m carteira_auto run fiscal

# Atualizar precos na planilha Excel
python -m carteira_auto run update-excel-portfolio-prices

# Dry-run (ver plano de execucao sem executar)
python -m carteira_auto run analyze --dry-run
```

### Python

```python
from carteira_auto.data.fetchers.yahoo_fetcher import YahooFinanceFetcher
from carteira_auto.data.fetchers.bcb import BCBFetcher

# Precos de acoes brasileiras
yahoo = YahooFinanceFetcher()
precos = yahoo.get_historical_price_data(['PETR4.SA', 'VALE3.SA'], period='1y')

# Indicadores macro
bcb = BCBFetcher()
selic = bcb.get_selic()
ipca = bcb.get_ipca()
```

### Pipeline DAG

```python
from carteira_auto.core.registry import create_engine, get_terminal_node

# Cria engine com todos os nodes registrados
engine = create_engine()

# Executa pipeline "macro" (resolve dependencias automaticamente)
terminal = get_terminal_node("macro")
ctx = engine.run(terminal)

# Resultados
print(ctx.get("macro_context"))
```

### Notebook Interativo

O notebook `notebooks/demo_fase1.ipynb` demonstra todas as funcionalidades com visualizacoes e analises financeiras. Ideal como documentacao interativa do sistema.

## Estrutura do Projeto

```
carteira_auto/
├── src/carteira_auto/
│   ├── config/           # Settings, constants
│   ├── core/             # DAGEngine, models Pydantic, registry, nodes, Result type
│   ├── data/
│   │   ├── fetchers/     # Yahoo, BCB, IBGE, FRED, CVM, DDM, Tesouro (7 fetchers)
│   │   ├── lake/         # DataLake SQLite (prices, macro, fundamentals, news)
│   │   ├── loaders/      # Excel, portfolio
│   │   ├── exporters/    # Excel, portfolio prices
│   │   └── storage/      # SnapshotStore (JSON)
│   ├── analyzers/        # 10 analyzers (portfolio, risk, macro, market, currency, commodity, fiscal...)
│   ├── alerts/           # AlertEngine, rules, channels
│   ├── utils/            # Decorators, logger, helpers
│   └── cli/              # Comandos CLI
├── dashboards/           # Streamlit app + paginas
├── notebooks/            # Notebooks de analise interativa
├── tests/                # Unit + integration tests (697 testes)
├── data/                 # Dados locais (gitignored)
│   ├── lake/             # SQLite DataLake
│   ├── raw/              # Planilha da carteira
│   └── outputs/          # Portfolios, snapshots, logs, reports
└── docs/
    ├── system/           # Docs do sistema (plano, arquitetura, API, guias)
    └── dev/              # Docs Claude Code (ARCHITECTURE, PATTERNS, grafo deps)
```

## Desenvolvimento

### Testes

```bash
# Unit tests
pytest tests/unit/ -v

# Com cobertura
pytest tests/unit/ --cov=carteira_auto --cov-report=html

# Testes em paralelo
pytest tests/unit/ -n auto
```

### Code Quality

```bash
# Formatacao
black src/ tests/

# Linting
ruff check src/ tests/

# Type checking
mypy src/carteira_auto/
```

### Pre-commit Hooks

O projeto usa pre-commit para garantir qualidade automaticamente:

```bash
pre-commit install
pre-commit run --all-files
```

## Roadmap

O desenvolvimento segue 8 fases:

| Fase | Escopo | Status |
|------|--------|--------|
| 0 | Infraestrutura: DataLake SQLite, IngestNodes | Concluida |
| 1 | Fontes: FRED, CVM, Tesouro, DDM | Concluida |
| H | Hardening: Result type, validacao estrita, error handling | Concluida |
| 2 | Analyzers avancados (currency, commodity, fiscal + 6 restantes) | Em andamento |
| 3 | Estrategias + Optimizer (PyPortfolioOpt) + Backtesting | Planejada |
| 4 | ML: scoring fundamentalista, integracao ML-optimizer | Planejada |
| 5 | NLP: sentimento, geopolitica, crisis hedge | Planejada |
| 6 | AI Reasoning: Claude/Deepseek, prompts, AIAnalysis | Planejada |
| 7 | Publishers: Telegram, PDF, email, Excel, web, scheduler | Planejada |

## Licenca

MIT License - veja [LICENSE](LICENSE) para detalhes.
