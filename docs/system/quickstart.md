# Guia de Início Rápido

Este guia mostra como instalar, configurar e rodar o `carteira_auto` pela primeira vez.

## Instalação

```bash
git clone https://github.com/begalv/carteira_auto.git
cd carteira_auto
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Requisitos: Python >= 3.10.

## Primeiro Uso

### 1. Prepare a planilha da carteira

Coloque sua planilha Excel com os dados da carteira em `data/raw/`. O nome padrão esperado é `Carteira 2026.xlsx` (configurável em `settings.py`).

A planilha deve conter colunas como Ticker, Classe, Preço Médio, Quantidade, etc. Veja o mapeamento completo em `src/carteira_auto/config/constants.py`.

### 2. Execute pipelines via CLI

O `carteira_auto` funciona por pipelines compostos de nodes em um DAG (grafo acíclico dirigido). Cada pipeline resolve dependências automaticamente.

**Análise de carteira** — calcula alocação, retorno e métricas consolidadas:

```bash
python -m carteira_auto run analyze
```

**Métricas de risco** — VaR, Sharpe, beta e drawdown:

```bash
python -m carteira_auto run risk
```

**Contexto macroeconômico** — Selic, IPCA, câmbio e PIB:

```bash
python -m carteira_auto run macro
```

**Análise de mercado** — benchmarks IBOV, IFIX e CDI:

```bash
python -m carteira_auto run market
```

**Análise setorial** — performance por setor de mercado:

```bash
python -m carteira_auto run market-sectors
```

**Setores da economia real** — dados IBGE:

```bash
python -m carteira_auto run economic-sectors
```

**Análise cambial** — USD/BRL, DXY, carry trade Selic-Fed:

```bash
python -m carteira_auto run currency
```

**Commodities** — petróleo, ouro, soja, ciclo de preços:

```bash
python -m carteira_auto run commodities
```

**Análise fiscal** — dívida/PIB, resultado primário, trajetória fiscal:

```bash
python -m carteira_auto run fiscal
```

**Rebalanceamento** — gera recomendações de ajuste da carteira:

```bash
python -m carteira_auto run rebalance
```

**Atualizar preços na planilha Excel** — busca preços via Yahoo Finance e exporta:

```bash
python -m carteira_auto run update-excel-portfolio-prices
```

**Listar todos os pipelines disponíveis:**

```bash
python -m carteira_auto list
```

**Ver plano de execução sem executar (dry-run):**

```bash
python -m carteira_auto run analyze --dry-run
```

**Ingestão de dados no DataLake:**

```bash
python -m carteira_auto ingest --mode daily    # últimos dias
python -m carteira_auto ingest --mode full     # backfill histórico

# Ou via pipelines individuais:
python -m carteira_auto run ingest-prices      # apenas preços
python -m carteira_auto run ingest-macro       # apenas indicadores macro
```

**Dashboard interativo (Streamlit):**

```bash
python -m carteira_auto dashboard
```

### 3. Opções adicionais do CLI

```bash
# Planilha de origem customizada
python -m carteira_auto run analyze -s data/raw/MinhaCarteira.xlsx

# Planilha de saída customizada
python -m carteira_auto run update-excel-portfolio-prices -o data/outputs/resultado.xlsx

# Ver versão
python -m carteira_auto --version
```

## Configuração

### Variáveis de ambiente (.env)

Crie um arquivo `.env` na raiz do projeto para API keys:

```dotenv
FRED_API_KEY=sua_chave_aqui
```

A chave do FRED é gratuita e pode ser obtida em: https://fred.stlouisfed.org/docs/api/api_key.html

### Ajustes de paths e timeouts

As configurações ficam em `src/carteira_auto/config/settings.py`. O `PathsConfig` define todos os diretórios:

| Diretório | Uso |
|-----------|-----|
| `data/raw/` | Planilha de entrada da carteira |
| `data/lake/` | DataLake SQLite com dados históricos |
| `data/outputs/portfolios/` | Planilhas Excel exportadas |
| `data/outputs/reports/` | Relatórios gerados |
| `data/outputs/snapshots/` | Snapshots JSON da carteira |
| `data/outputs/logs/` | Logs de execução |

Os diretórios são criados automaticamente na primeira execução.

Timeouts, limites de requisição e outras configs de fetchers (Yahoo, BCB, IBGE, FRED, DDM) também ficam em `settings.py`.

## Rodando Testes

```bash
# Todos os testes (excluindo testes lentos de API externa)
pytest tests/ -v --tb=short -k "not test_get_dfp_dre_petrobras"

# Apenas testes unitários
pytest tests/unit/ -v

# Apenas testes de integração (E2E)
pytest tests/integration/ -v

# Com cobertura
pytest tests/ -v --cov=carteira_auto --cov-report=term-missing
```

Os testes unitários usam mocks para não depender de APIs externas. Os testes de integração podem fazer chamadas reais (mais lentos).

## Estrutura do Projeto

```
carteira_auto/
├── src/carteira_auto/
│   ├── cli/              # Interface de linha de comando
│   ├── config/           # Settings, constants, optimization
│   ├── core/             # Engine DAG, models Pydantic, nodes
│   ├── data/             # Fetchers, loaders, exporters, lake
│   ├── analyzers/        # Nodes de análise (portfolio, risk, macro...)
│   ├── alerts/           # Engine de alertas com canais
│   └── utils/            # Logger, decorators, helpers
├── dashboards/           # App Streamlit + páginas
├── data/                 # Dados de entrada e saída
├── tests/                # Unit + integration tests
└── docs/                 # Documentação
```
