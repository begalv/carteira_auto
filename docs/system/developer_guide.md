# Guia do Desenvolvedor

Referência para contribuir com o `carteira_auto`: como criar fetchers, analyzers, pipelines e seguir as convenções do projeto.

## Como Criar um Novo Fetcher

Fetchers buscam dados de APIs externas. Cada fetcher fica em `src/carteira_auto/data/fetchers/` e segue o mesmo padrão.

### Passo 1: Criar a classe do fetcher

Crie um arquivo em `src/carteira_auto/data/fetchers/novo_fetcher.py`:

```python
"""Fetcher do NovaFonte — descrição da fonte de dados.

Portal: https://...
API: https://...
Docs: https://...

Séries disponíveis:
    SERIE_1 — Descrição
    SERIE_2 — Descrição

Fluxo típico:
    1. Configurar API key no .env (se necessário)
    2. fetcher.get_data() -> DataFrame
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import requests

from carteira_auto.config import settings
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import (
    cache_result,
    log_execution,
    rate_limit,
    retry,
)

logger = get_logger(__name__)


class NovoFetcher:
    """Busca dados da NovaFonte.

    Uso:
        fetcher = NovoFetcher()
        df = fetcher.get_data("SERIE_1")
    """

    BASE_URL = "https://api.novafonte.com"

    def __init__(self) -> None:
        self.session = requests.Session()
        self.api_key = settings.novo_fonte.API_KEY  # configurado em settings.py

    @retry(max_attempts=3, delay=2.0)
    @rate_limit(calls_per_second=2)
    @cache_result(ttl_seconds=3600)
    @log_execution
    def get_data(
        self,
        serie_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Busca série temporal da NovaFonte.

        Args:
            serie_id: Identificador da série.
            start_date: Data inicial (default: 1 ano atrás).
            end_date: Data final (default: hoje).

        Returns:
            DataFrame com colunas [date, value].

        Raises:
            requests.HTTPError: Erro na API.
        """
        params = {"series_id": serie_id, "api_key": self.api_key}
        if start_date:
            params["start"] = start_date.isoformat()
        if end_date:
            params["end"] = end_date.isoformat()

        response = self.session.get(f"{self.BASE_URL}/data", params=params)
        response.raise_for_status()

        data = response.json()
        df = pd.DataFrame(data["observations"])
        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")

        logger.info(f"NovaFonte: {serie_id} -> {len(df)} registros")
        return df
```

### Passo 2: Adicionar config em settings.py

Em `src/carteira_auto/config/settings.py`, crie um dataclass de configuracao e adicione-o ao `Settings`:

```python
@dataclass
class NovoFonteConfig:
    """Configuracoes do fetcher NovaFonte."""

    API_KEY: str = os.getenv("NOVO_FONTE_API_KEY", "")
    TIMEOUT: int = 30
    MAX_RETRIES: int = 3
```

### Passo 3: Registrar em `__init__.py`

Em `src/carteira_auto/data/fetchers/__init__.py`:

```python
from .novo_fetcher import NovoFetcher

__all__ = [
    # ... fetchers existentes ...
    "NovoFetcher",
]
```

### Passo 4: Escrever testes com mocks

Crie `tests/unit/test_novo_fetcher.py`:

```python
"""Testes do NovoFetcher."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from carteira_auto.data.fetchers import NovoFetcher


@pytest.fixture
def fetcher():
    """Fetcher com API key fake."""
    with patch.object(NovoFetcher, "__init__", lambda self: None):
        f = NovoFetcher()
        f.session = MagicMock()
        f.api_key = "fake_key"
        return f


def test_get_data_retorna_dataframe(fetcher):
    """get_data deve retornar DataFrame com colunas date e value."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "observations": [
            {"date": "2024-01-01", "value": "10.5"},
            {"date": "2024-01-02", "value": "11.0"},
        ]
    }
    mock_response.raise_for_status = MagicMock()
    fetcher.session.get.return_value = mock_response

    df = fetcher.get_data("SERIE_1")

    assert isinstance(df, pd.DataFrame)
    assert "date" in df.columns
    assert "value" in df.columns
    assert len(df) == 2


def test_get_data_http_error(fetcher):
    """get_data deve propagar HTTPError da API."""
    import requests

    fetcher.session.get.side_effect = requests.HTTPError("404")

    with pytest.raises(requests.HTTPError):
        fetcher.get_data("SERIE_INVALIDA")
```

### Checklist de fetcher

- [ ] Decorators: `@retry`, `@rate_limit`, `@cache_result`, `@log_execution`
- [ ] Logger: `logger = get_logger(__name__)` no topo do modulo
- [ ] Type hints em todos os metodos
- [ ] Docstring com descricao da fonte, series e fluxo tipico
- [ ] Config em `settings.py` (API keys via `os.getenv`)
- [ ] Registrado em `__init__.py`
- [ ] Testes unitarios com mocks (sem chamadas reais a APIs)

---

## Como Criar um Novo Analyzer

Analyzers calculam metricas e produzem resultados no contexto do pipeline. Cada analyzer e um `Node` do DAG.

### Passo 1: Criar model de output em `core/models/`

Se o analyzer produz um tipo de dado novo, defina um Pydantic model:

```python
# src/carteira_auto/core/models/novo_model.py
from pydantic import BaseModel, field_validator


class NovaAnalise(BaseModel):
    """Resultado da analise X."""

    score: float
    classificacao: str
    detalhes: dict[str, float] = {}

    @field_validator("score")
    @classmethod
    def score_entre_zero_e_um(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Score deve estar entre 0 e 1, recebeu {v}")
        return v
```

Registre no `__init__.py` dos models.

### Passo 2: Criar Node em `analyzers/`

```python
# src/carteira_auto/analyzers/novo_analyzer.py
"""Analyzer X — descricao do que analisa.

Node DAG: name="analyze_novo", deps=["fetch_prices"]
Produz: ctx["nova_analise"] -> NovaAnalise
"""

from carteira_auto.core.engine import Node, PipelineContext
from carteira_auto.core.models import NovaAnalise
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import log_execution

logger = get_logger(__name__)


class NovoAnalyzer(Node):
    """Calcula analise X.

    Le do contexto:
        - "portfolio": Portfolio

    Produz no contexto:
        - "nova_analise": NovaAnalise
    """

    name = "analyze_novo"
    dependencies = ["fetch_prices"]

    @log_execution
    def run(self, ctx: PipelineContext) -> PipelineContext:
        portfolio = ctx["portfolio"]

        try:
            resultado = self._calcular(portfolio)
            ctx["nova_analise"] = resultado
            logger.info(f"NovoAnalyzer: score={resultado.score:.2f}")
        except Exception as e:
            logger.error(f"Erro no NovoAnalyzer: {e}")
            errors = ctx.get("_errors", {})
            errors["analyze_novo"] = str(e)
            ctx["_errors"] = errors

        return ctx

    def _calcular(self, portfolio) -> NovaAnalise:
        """Logica de calculo."""
        # ... implementacao ...
        return NovaAnalise(score=0.75, classificacao="bom")
```

Pontos importantes:

- `name` e o identificador unico do node no DAG.
- `dependencies` lista os nodes que devem executar antes.
- `run(ctx)` sempre retorna o contexto (mesmo em caso de erro).
- Erros parciais vao em `ctx["_errors"]` para nao interromper o pipeline inteiro.

### Passo 3: Registrar em `registry.py` e `create_engine()`

Em `src/carteira_auto/core/registry.py`:

```python
# No PIPELINE_PRESETS, adicione:
PIPELINE_PRESETS: dict[str, str] = {
    # ... existentes ...
    "novo": "analyze_novo",
}

# No PIPELINE_DESCRIPTIONS, adicione:
PIPELINE_DESCRIPTIONS: dict[str, str] = {
    # ... existentes ...
    "novo": "Executa analise X sobre a carteira",
}

# Na funcao create_engine(), registre o node:
def create_engine(...) -> DAGEngine:
    from carteira_auto.analyzers import NovoAnalyzer

    # ... nodes existentes ...
    dag_engine.register(NovoAnalyzer())
```

### Passo 4: Adicionar ao `analyzers/__init__.py`

```python
from .novo_analyzer import NovoAnalyzer

__all__ = [
    # ... existentes ...
    "NovoAnalyzer",
]
```

### Passo 5: Escrever testes

```python
# tests/unit/test_novo_analyzer.py
"""Testes do NovoAnalyzer."""

from unittest.mock import MagicMock

import pytest

from carteira_auto.analyzers import NovoAnalyzer
from carteira_auto.core.engine import PipelineContext


@pytest.fixture
def ctx_com_portfolio():
    """Contexto com portfolio mockado."""
    ctx = PipelineContext()
    portfolio = MagicMock()
    portfolio.assets = [
        MagicMock(ticker="PETR4.SA", posicao_atual=1000.0),
        MagicMock(ticker="VALE3.SA", posicao_atual=2000.0),
    ]
    ctx["portfolio"] = portfolio
    return ctx


def test_run_produz_nova_analise(ctx_com_portfolio):
    """run() deve produzir nova_analise no contexto."""
    analyzer = NovoAnalyzer()
    result_ctx = analyzer.run(ctx_com_portfolio)

    assert "nova_analise" in result_ctx
    assert result_ctx["nova_analise"].score >= 0.0


def test_run_com_erro_registra_em_errors():
    """Erros devem ir para ctx['_errors'] sem interromper."""
    ctx = PipelineContext()
    # Sem portfolio no contexto -> erro
    analyzer = NovoAnalyzer()
    result_ctx = analyzer.run(ctx)

    assert "_errors" in result_ctx
    assert "analyze_novo" in result_ctx["_errors"]
```

---

## Como Adicionar uma Pipeline

Pipelines sao composicoes de nodes resolvidas automaticamente pelo DAG engine. Para criar um pipeline novo:

### 1. Crie os nodes necessarios

Cada node precisa de `name`, `dependencies` e `run(ctx)`. Veja as secoes acima para fetchers e analyzers.

### 2. Adicione ao `PIPELINE_PRESETS` e `PIPELINE_DESCRIPTIONS`

Em `src/carteira_auto/core/registry.py`:

```python
PIPELINE_PRESETS["meu-pipeline"] = "node_terminal"
PIPELINE_DESCRIPTIONS["meu-pipeline"] = "Descricao do que o pipeline faz"
```

O DAG engine resolve todas as dependencias automaticamente a partir do node terminal.

### 3. Registre os nodes em `create_engine()`

Todos os nodes devem ser registrados via `dag_engine.register()` ou `dag_engine.register_many()`.

### 4. Teste com dry-run

```bash
python -m carteira_auto run meu-pipeline --dry-run
```

O dry-run mostra a ordem de execucao sem executar nada.

---

## Convencoes de Codigo

### Type hints obrigatorios

Todas as funcoes e metodos devem ter type hints nos parametros e retorno:

```python
def calcular_retorno(valor_atual: float, valor_investido: float) -> float:
    """Calcula retorno percentual."""
    return (valor_atual - valor_investido) / valor_investido
```

### Logger padrao

Todo modulo deve ter logger no topo:

```python
from carteira_auto.utils import get_logger

logger = get_logger(__name__)
```

### Decorators padrao para fetchers

Fetchers devem usar os decorators nesta ordem:

```python
@retry(max_attempts=3, delay=2.0)
@rate_limit(calls_per_second=2)
@cache_result(ttl_seconds=3600)
@log_execution
def get_data(self, ...) -> pd.DataFrame:
```

Decorators disponiveis em `src/carteira_auto/utils/decorators.py`:

| Decorator | Uso |
|-----------|-----|
| `@timer` | Mede tempo de execucao |
| `@retry` | Retenta em caso de erro |
| `@rate_limit` | Limita requisicoes por segundo |
| `@timeout` | Aborta apos N segundos |
| `@fallback` | Valor padrao em caso de erro |
| `@cache_result` | Cache com TTL |
| `@cache_by_ticker` | Cache por ticker |
| `@log_execution` | Loga inicio/fim da funcao |
| `@validate_tickers` | Valida formato de tickers |
| `@validate_positive_value` | Valida valores positivos |
| `@validate_allocation_sum` | Valida soma de alocacoes |

### Error handling com ctx["_errors"]

Nodes nao devem lancar excecoes que interrompam o pipeline inteiro. Erros parciais devem ser registrados no contexto:

```python
try:
    resultado = self._calcular(dados)
    ctx["resultado"] = resultado
except Exception as e:
    logger.error(f"Erro: {e}")
    errors = ctx.get("_errors", {})
    errors[self.name] = str(e)
    ctx["_errors"] = errors
```

### Validacao Pydantic

Models usam `field_validator` para campos obrigatorios:

```python
from pydantic import BaseModel, field_validator

class MeuModel(BaseModel):
    valor: float
    acao: Literal["comprar", "vender", "manter"]

    @field_validator("valor")
    @classmethod
    def valor_positivo(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Valor deve ser positivo")
        return v
```

Use `Literal` types para campos com valores restritos (actions, status, etc.).

### Formatacao e linting

O projeto usa `black` para formatacao e `ruff` para linting, aplicados via pre-commit hooks:

```bash
# Instalar hooks
pre-commit install

# Rodar manualmente
pre-commit run --all-files

# Ou individualmente
black src/ tests/
ruff check src/ tests/ --fix
```

O ruff esta configurado com regra `UP007` que prefere `X | Y` ao inves de `Optional[X]`.

---

## Estrutura de Testes

### Organizacao

```
tests/
├── conftest.py           # Fixtures compartilhadas
├── fixtures/             # Dados de teste (JSON, CSV)
├── unit/                 # Testes unitarios com mocks
│   ├── test_bcb_fetcher.py
│   ├── test_novo_fetcher.py
│   └── ...
└── integration/          # Testes E2E com dados mockados
    ├── test_pipeline_analyze.py
    └── ...
```

### Mocks de fetchers

Quando um fetcher e importado dentro do `run()` de um node, o mock deve apontar para o local de importacao:

```python
from unittest.mock import patch, MagicMock

# Se o node faz: from carteira_auto.data.fetchers import BCBFetcher
# O mock deve ser:
@patch("carteira_auto.data.fetchers.BCBFetcher")
def test_meu_node(mock_bcb):
    mock_bcb.return_value.get_series.return_value = pd.DataFrame(...)
```

### Fixtures compartilhadas

As fixtures em `tests/conftest.py` incluem:

- `tmp_lake_dir` — diretorio temporario para DataLake
- `tmp_parquet_dir` — diretorio temporario para Parquet

Para criar fixtures de portfolio e contexto em seus testes:

```python
@pytest.fixture
def portfolio_simples():
    """Portfolio com 2 ativos para testes."""
    from carteira_auto.core.models import Asset, Portfolio

    assets = [
        Asset(ticker="PETR4.SA", classe="Acoes", quantidade=100, preco_medio=25.0),
        Asset(ticker="VALE3.SA", classe="Acoes", quantidade=50, preco_medio=60.0),
    ]
    return Portfolio(assets=assets)


@pytest.fixture
def ctx_com_portfolio(portfolio_simples):
    """PipelineContext com portfolio carregado."""
    from carteira_auto.core.engine import PipelineContext

    ctx = PipelineContext()
    ctx["portfolio"] = portfolio_simples
    return ctx
```

### Executando testes

```bash
# Todos os testes
pytest tests/ -v --tb=short -k "not test_get_dfp_dre_petrobras"

# Apenas unit
pytest tests/unit/ -v

# Apenas integration
pytest tests/integration/ -v

# Teste especifico
pytest tests/unit/test_novo_fetcher.py::test_get_data_retorna_dataframe -v

# Com cobertura
pytest tests/ --cov=carteira_auto --cov-report=term-missing
```

---

## Pre-commit Hooks

O projeto usa pre-commit com os seguintes hooks:

| Hook | Funcao |
|------|--------|
| `black` | Formatacao automatica de codigo |
| `ruff` | Linting com autofix (`--fix`) |
| `trailing-whitespace` | Remove espacos em branco no final das linhas |
| `end-of-file-fixer` | Garante newline no final dos arquivos |
| `check-yaml` | Valida sintaxe YAML |
| `check-toml` | Valida sintaxe TOML |
| `check-merge-conflict` | Detecta marcadores de merge conflict |
| `check-added-large-files` | Impede commit de arquivos grandes |
| `detect-private-key` | Impede commit de chaves privadas |

Para instalar e usar:

```bash
# Instalar hooks (uma vez)
pre-commit install

# Rodar em todos os arquivos
pre-commit run --all-files

# Os hooks rodam automaticamente em cada git commit
```

Se o `ruff` ou `black` fizer alteracoes automaticas, os arquivos serao modificados mas o commit sera rejeitado. Basta fazer `git add` novamente e commitar.

---

## FetchWithFallback — Fallback Hierárquico entre Fetchers

O helper `FetchWithFallback` em `src/carteira_auto/core/nodes/fetch_helpers.py` orquestra tentativas entre fontes diferentes quando um dado pode vir de múltiplas APIs.

### Quando usar

Nos IngestNodes, quando um indicador pode ser obtido de mais de uma fonte:

```python
from carteira_auto.core.nodes.fetch_helpers import (
    FetchStrategy, fetch_with_fallback,
)

# Selic: BCB (primário, gratuito) → DDM (fallback, pago)
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

### FetchWithFallback vs @fallback

| Mecanismo | Escopo | Onde usar |
|-----------|--------|----------|
| `fetch_with_fallback()` | Entre fetchers diferentes | IngestNodes |
| `@fallback` decorator | Dentro de um mesmo fetcher | Fetcher internals |

O `@fallback` (de `utils/decorators.py`) opera dentro de um único fetcher para fallback interno (ex: python-bcb falha → HTTP raw). O `fetch_with_fallback` opera nos IngestNodes para orquestrar entre fetchers independentes.

### Proveniência

Todo dado persistido no DataLake deve incluir `source=result.source` para rastreabilidade. O campo `source` indica qual fetcher real forneceu o dado (ex: `"bcb"`, `"ddm"`, `"yahoo"`, `"tradingcomdados"`).

---

## ReferenceLake — Dados de Referência Não-Temporais

O `ReferenceLake` (`src/carteira_auto/data/lake/reference_lake.py`) armazena dados estruturais que não são séries temporais:

| Tabela | Dados | Fonte primária |
|--------|-------|----------------|
| `index_compositions` | Composição de IBOV, IFIX, IDIV, SMLL | TradingComDados, DDM |
| `focus_expectations` | Projeções Focus (Selic, IPCA, PIB) | BCB (python-bcb) |
| `analyst_targets` | Preço-alvo de analistas | Yahoo |
| `upgrades_downgrades` | Revisões de rating | Yahoo |
| `lending_rates` | Taxas de crédito por banco | BCB (TaxaJuros) |
| `cnae_classifications` | Classificação setorial CNAE | IBGE |
| `ticker_cnpj_map` | Mapeamento ticker → CNPJ | DDM, CVM |
| `major_holders` | Participação acionária (% insiders/institutional) | Yahoo |
| `fund_registry` | Cadastro de fundos e FIIs | CVM |
| `fund_portfolios` | Composição de carteiras CDA | CVM |
| `intermediaries` | Corretoras e distribuidoras | CVM |
| `asset_registry` | Listas de ações, FIIs, BDRs, ETFs | TradingComDados |

Acesso via fachada `DataLake`:

```python
lake = DataLake(Path("data/lake"))
lake.store_index_composition("IBOV", df, source="tradingcomdados")
lake.store_asset_registry(df, asset_type="fii", source="tradingcomdados")
lake.store_fund_registry(funds, source="cvm")
```
