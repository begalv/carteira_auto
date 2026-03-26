# Padrões de código — carteira_auto

> Exemplos canônicos para o Claude Code. Cada pattern referencia código
> real do repositório e serve como template para novos componentes.

## Pattern 1: Novo fetcher

Referência real: `src/carteira_auto/data/fetchers/bcb_fetcher.py`

```python
"""Fetcher de [FONTE] — [descrição curta].

API: [URL base]
Autenticação: [tipo ou "sem autenticação"]
Rate limit: [X req/min]
Formato resposta: [JSON/CSV/XML]
"""

import pandas as pd
import requests

from carteira_auto.config import settings
from carteira_auto.config.constants import constants
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import (
    cache_result,
    log_execution,
    rate_limit,
    retry,
)

logger = get_logger(__name__)


class NovoFetcher:
    """Busca dados de [FONTE] com cache, retry e rate limit."""

    def __init__(self):
        self._base_url = settings.novo.BASE_URL
        self._timeout = settings.novo.TIMEOUT

    # === Métodos públicos (um por indicador/recurso) ===

    @log_execution
    @cache_result(ttl_seconds=3600)
    def get_indicador_especifico(self, period_days: int = 365) -> pd.DataFrame:
        """[Nome do indicador] — [unidade]."""
        return self._fetch("codigo_ou_endpoint", period_days)

    # === Método genérico ===

    @log_execution
    def get_indicator(self, code: str, start_date=None, end_date=None) -> pd.DataFrame:
        """Busca qualquer série/endpoint por código."""
        return self._fetch_raw(code, start_date, end_date)

    # === Internals ===

    @retry(max_attempts=3)
    @rate_limit(calls_per_minute=30)
    def _fetch_raw(self, code, start_date, end_date) -> pd.DataFrame:
        """Request HTTP com retry e rate limit."""
        url = self._base_url.format(code=code)
        response = requests.get(url, timeout=self._timeout)
        response.raise_for_status()
        # Normalizar para DataFrame com colunas ['data', 'valor']
        return self._parse_response(response.json())

    def _parse_response(self, raw_data) -> pd.DataFrame:
        """Normaliza resposta da API para DataFrame padrão."""
        # ... parsing específico da fonte ...
        pass
```

**Checklist ao criar fetcher:**
- [ ] Config em `settings.py` (BASE_URL, TIMEOUT, RATE_LIMIT, CACHE_TTL)
- [ ] Constantes em `constants.py` (códigos de série, endpoints)
- [ ] Decorators: `@retry`, `@rate_limit`, `@cache_result`, `@log_execution`
- [ ] Logger: `logger = get_logger(__name__)`
- [ ] Output normalizado: DataFrame com colunas padronizadas
- [ ] Registrado em `data/fetchers/__init__.py`
- [ ] Teste em `tests/unit/test_fetchers/`

---

## Pattern 2: Novo analyzer (Node DAG)

Referência real: `src/carteira_auto/analyzers/macro_analyzer.py`

```python
"""Analyzer de [domínio] — [o que calcula].

Node DAG: name="analyze_novo", deps=[lista de dependências]
Produz: ctx["novo_metrics"] -> NovoMetrics
"""

from carteira_auto.core.engine import Node, PipelineContext
from carteira_auto.core.models import NovoMetrics  # Criar em models/
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import log_execution

logger = get_logger(__name__)


class NovoAnalyzer(Node):
    """[O que calcula e para que serve].

    Lê do contexto:
        - "[chave_input]": [Tipo] ([quem produz])

    Produz no contexto:
        - "novo_metrics": NovoMetrics
    """

    name = "analyze_novo"
    dependencies = ["dep1", "dep2"]  # Nodes que devem rodar antes

    @log_execution
    def run(self, ctx: PipelineContext) -> PipelineContext:
        input_data = ctx["chave_input"]
        metrics = self._calculate(input_data)
        ctx["novo_metrics"] = metrics
        logger.info(f"Novo: campo={metrics.campo_principal}")
        return ctx

    def _calculate(self, data) -> NovoMetrics:
        """Lógica de cálculo isolada (testável independente do DAG)."""
        # ... implementação ...
        pass
```

**Checklist ao criar analyzer:**
- [ ] Pydantic model de output em `core/models/`
- [ ] `name` único (será referenciado em dependencies de outros nodes)
- [ ] `dependencies` lista todos os nodes que devem rodar antes
- [ ] Docstring documenta o que lê e o que produz no ctx
- [ ] Registrado em `analyzers/__init__.py`
- [ ] Adicionado ao `create_engine()` em `registry.py`
- [ ] Teste em `tests/unit/test_analyzers/`

---

## Pattern 3: Nova strategy (base)

Referência arquitetural: ADR-002 em `docs/adr/`

```python
"""Estratégia [nome] — [filosofia de investimento].

Required analyzers: [lista]
Timeframe: [short/medium/long]
Produz: StrategyResult com signals + views Black-Litterman
"""

from carteira_auto.core.engine import PipelineContext
from carteira_auto.strategies.base import Signal, Strategy, StrategyResult

class NovaStrategy(Strategy):
    name = "nova_strategy"
    description = "Descrição da filosofia e lógica"
    timeframe = "medium"
    required_analyzers = ["analyze_fundamental", "analyze_risk"]

    def evaluate(self, ctx: PipelineContext) -> StrategyResult:
        """Lê métricas dos analyzers, aplica lógica, retorna sinais + views."""
        funds = ctx["fundamentals"]
        risk = ctx["risk_metrics"]

        signals = []
        views = {}
        confidences = {}

        for asset in ctx["portfolio"].assets:
            score = self._score_asset(asset, funds, risk)
            if score > 0.7:
                signals.append(Signal(
                    ticker=asset.ticker,
                    action="buy",
                    strength=score,
                    reason="Score fundamentalista acima do threshold",
                    source_strategy=self.name,
                ))
                views[asset.ticker] = score * 0.20
                confidences[asset.ticker] = min(score, 0.9)

        return StrategyResult(
            signals=signals,
            views=views,
            confidences=confidences,
        )

    def _score_asset(self, asset, funds, risk) -> float:
        """Lógica de scoring isolada e testável."""
        # ... implementação ...
        return 0.0

    def backtest_params(self) -> dict:
        return {"rebalance_freq": "monthly", "lookback": 504}
```

**Regra fundamental:** Strategy NÃO herda de Node. Usa `evaluate()`, não `run()`.
O `StrategyNode(Node)` faz a ponte para o DAG automaticamente.

---

## Pattern 4: Nova composite strategy

```python
from carteira_auto.strategies.composite import (
    CompositeStrategy, Layer, LayerGate, WeightedBlend,
)

nova_composite = CompositeStrategy(
    name="nome_composta",
    description="Descrição do pipeline de decisão",
    layers=[
        # Layer 1: sempre executa
        Layer(strategy=MacroTactical(), weight=1.0),

        # Layer 2: sempre executa, vê output do layer 1 via ctx
        Layer(strategy=ValueInvesting(), weight=1.0),

        # Layer 3: condicional — executa A ou B dependendo do ctx
        Layer(
            strategy=WeightedBlend([
                (MLScoring(), 0.7),
                (MomentumRotation(), 0.3),
            ]),
            weight=0.8,
            gate=LayerGate(
                condition=lambda ctx: ctx.get("sentiment", {}).get("score", 0) >= -0.3,
                description="Sentimento não-negativo → ML+Momentum",
                fallback=CrisisHedge(),
            ),
        ),
    ],
)
```

---

## Pattern 5: Novo Pydantic model

```python
from datetime import date
from typing import Optional
from pydantic import BaseModel


class NovoMetrics(BaseModel):
    """[Descrição do que representa].

    Campos obrigatórios: apenas identificadores e métricas core.
    Campos opcionais: tudo que pode falhar na coleta ou cálculo.
    """

    # Obrigatórios
    nome: str

    # Opcionais (Optional + default None)
    valor: Optional[float] = None
    data: Optional[date] = None
    fonte: Optional[str] = None
```

---

## Pattern 6: Novo publisher

Referência: `src/carteira_auto/alerts/channels.py` (AlertChannel ABC)

```python
from carteira_auto.publishers.base import Publisher, PublishableContent, PublishResult
from carteira_auto.utils import get_logger

logger = get_logger(__name__)


class NovoPublisher(Publisher):
    """Publica via [canal] — [descrição].

    Configuração: settings.[canal]
    Formato de saída: [HTML/Markdown/texto/binário]
    """

    def format(self, analysis, ctx) -> str:
        """Converte AIAnalysis → formato do canal."""
        # ... formatação ...
        pass

    def publish(self, content: PublishableContent) -> PublishResult:
        """Envia pelo canal."""
        # ... envio ...
        pass
```

---

## Pattern 7: Error Handling com Result Type

Reference: `src/carteira_auto/core/result.py`

```python
from carteira_auto.core import Ok, Err, Result

# Retornar sucesso
def fetch_data(ticker: str) -> Result[pd.DataFrame]:
    try:
        df = fetcher.get_data(ticker)
        return Ok(df)
    except Exception as e:
        return Err(str(e), {"ticker": ticker, "traceback": traceback.format_exc()})

# Consumir resultado
result = fetch_data("PETR4")
if result.is_ok():
    df = result.unwrap()
else:
    logger.error(f"Falha: {result.error}")
    df = result.unwrap_or(pd.DataFrame())  # fallback seguro
```

---

## Pattern 8: Error Tracking Parcial em Analyzers

Reference: `src/carteira_auto/analyzers/macro_analyzer.py`

```python
class NovoAnalyzer(Node):
    name = "analyze_novo"
    dependencies: list[str] = []

    @log_execution
    def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx.setdefault("_errors", {})
        errors: list[str] = []

        # Busca parcial — cada indicador pode falhar independente
        valor_a = None
        try:
            valor_a = self._fetch_a()
        except Exception as e:
            logger.error(f"Falha em A: {e}\n{traceback.format_exc()}")
            errors.append(f"A: {e}")

        valor_b = None
        try:
            valor_b = self._fetch_b()
        except Exception as e:
            logger.error(f"Falha em B: {e}\n{traceback.format_exc()}")
            errors.append(f"B: {e}")

        if errors:
            ctx["_errors"]["analyze_novo.partial"] = "; ".join(errors)

        ctx["novo_metrics"] = NovoMetrics(a=valor_a, b=valor_b)
        return ctx
```

**Checklist error handling:**
- [ ] `ctx.setdefault("_errors", {})` no início do run()
- [ ] try-except por indicador/fonte independente
- [ ] `logger.error()` com traceback.format_exc()
- [ ] Erros coletados em lista, registrados em ctx["_errors"]["node_name.partial"]
- [ ] Métricas com None para campos que falharam (não exceção total)

---

## Pattern 9: Validação Pydantic Estrita

Reference: `src/carteira_auto/core/models/portfolio.py`

```python
from pydantic import BaseModel, field_validator

class NovoModel(BaseModel):
    ticker: str
    preco: float | None = None
    pct: float | None = None

    @field_validator("ticker")
    @classmethod
    def ticker_nao_vazio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("ticker não pode ser vazio")
        return v

    @field_validator("preco")
    @classmethod
    def preco_nao_negativo(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError(f"preco não pode ser negativo: {v}")
        return v

    @field_validator("pct")
    @classmethod
    def pct_no_range(cls, v: float | None) -> float | None:
        if v is not None and (v < 0 or v > 1):
            raise ValueError(f"pct deve estar entre 0 e 1: {v}")
        return v
```

**Checklist validação:**
- [ ] Campos identificadores (ticker, nome): obrigatórios, non-empty
- [ ] Preços e valores: `>= 0` (Optional com validator)
- [ ] Percentuais: `0 <= x <= 1` (Optional com validator)
- [ ] Actions: `Literal["comprar", "vender", "manter"]`
- [ ] Listas: validar não-vazia quando obrigatório (`Portfolio.assets`)
