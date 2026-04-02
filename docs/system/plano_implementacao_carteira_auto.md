# Plano de Implementação — carteira_auto v0.2.1+

## Contexto Estratégico

**Objetivo:** Sistema de automação de carteira de investimentos para emancipação financeira de investidor PF (29 anos, Brasil), com capacidade de testar múltiplas estratégias, analisar macro/microeconomia e geopolítica, e tomar decisões de alocação embasadas em dados — tudo sob a lente do materialismo histórico-dialético aplicado à análise das contradições do capitalismo financeirizado.

**Estado atual do repositório (v0.2.1+):** Arquitetura DAG funcional com topological sort, 7 fetchers (Yahoo, BCB, IBGE, FRED, CVM, TesouroDireto, DDM), 10 analyzers (incluindo Currency, Commodity, Fiscal), DataLake SQLite com 5 sub-lakes + ReferenceLake (12 tabelas), sistema de alertas, CLI com 14 pipelines, dashboard Streamlit, modelos Pydantic tipados, Result type (Ok/Err), validação estrita, FetchWithFallback helper, 407+ testes passando. Faltam: framework de estratégias, backtesting, otimização (PyPortfolioOpt), ML, NLP/sentimento, AI reasoning, publishers multi-canal.

**Perfil financeiro atual (dados da planilha):**
> Dados sensíveis (renda, custos de vida, detalhamento da carteira) removidos deste arquivo por segurança.
> Ver `docs/system/perfil_pessoal.md` (arquivo local, listado no .gitignore — não rastreado pelo git).

---

## Diagnóstico Arquitetural: Contradições e Lacunas

### O que funciona (tese)
1. **DAGEngine** com Kahn's Algorithm resolve dependências corretamente
2. **Node pattern** (name + dependencies + run(ctx)) é limpo e extensível
3. **Decorators** (retry, rate_limit, cache, timeout) são reutilizáveis
4. **Modelos Pydantic** garantem validação de dados
5. **PipelineContext** (dict tipado) permite comunicação entre nodes

### O que falta (antítese)
1. **Sem framework de estratégias** — analyzers são estáticos, não composáveis
2. **Sem persistência temporal** — snapshots JSON são pontuais, sem séries temporais
3. **Sem backtesting** — impossível validar estratégias contra dados históricos
4. **Fontes insuficientes** — faltam CVM, FRED, commodities, câmbio, notícias, crypto
5. **Sem ML pipeline** — nenhuma infra para treino, validação e inferência
6. **Gastos desconectados** — planilha de orçamento não alimenta projeções
7. **Nodes não são reutilizáveis entre estratégias** — cada pipeline é hardcoded no registry
8. **Sem scheduler** — execução apenas manual via CLI

### Síntese: Arquitetura-Alvo

O sistema deve evoluir de "ferramenta de consulta" para "sistema de decisão":

```
[Fontes de Dados] → [Data Lake] → [Analyzers] → [Estratégias] → [Sinais] → [Execução/Alerta]
                         ↑                              ↓
                    [Backtester] ← ← ← ← ← ← ← [ML Models]
```

---

## Fontes de Dados — Mapeamento Completo

### Dados necessários para gestão completa de carteira

| Categoria | Dados | Fonte Primária | Fonte Alternativa | Frequência |
|-----------|-------|---------------|-------------------|------------|
| **Preços BR** | Cotações B3, OHLCV | Yahoo Finance | Dados de Mercado API | Diária |
| **Preços INT** | S&P500, Nasdaq, ETFs globais | Yahoo Finance | Alpha Vantage | Diária |
| **Fundamentos BR** | DRE, Balanço, DFC, indicadores | CVM (dados abertos) | Yahoo Finance | Trimestral |
| **Fundamentos FIIs** | Relatórios gerenciais, DY, P/VP | CVM/B3 Dados | Funds Explorer scraping | Mensal |
| **Macro BR** | Selic, IPCA, CDI, PIB, câmbio, TR, IGP-M | BCB SGS API | IBGE SIDRA | Diária/Mensal |
| **Macro EUA** | Fed Funds, CPI, GDP, Unemployment, Treasury yields | FRED API | BLS API | Variada |
| **Macro Global** | PMI, trade balance, reservas, CDS soberano | FRED / World Bank | IMF API | Mensal |
| **Commodities** | Petróleo (Brent/WTI), Ouro, Prata, Minério, Soja, Milho | Yahoo Finance | Quandl | Diária |
| **Câmbio** | USD/BRL, EUR/BRL, DXY, BRL real efetivo | BCB PTAX | Yahoo Finance | Diária |
| **Renda Fixa** | Curva DI, NTN-B rates, spread de crédito | ANBIMA | Tesouro Direto API | Diária |
| **Notícias** | Headlines financeiras, geopolítica | NewsAPI / GNews | RSS (Reuters, Bloomberg, Valor) | Contínua |
| **Sentimento** | Fear & Greed, VIX, Put/Call ratio | CNN/CBOE (scraping) | Yahoo Finance (VIX) | Diária |
| **Crypto** | BTC, ETH, dominância | CoinGecko API | Binance API | Contínua |
| **Setores** | Performance setorial B3, rotação | Yahoo Finance (Sector) | B3 dados setoriais | Diária |
| **Dividendos** | Histórico de proventos, JCP, bonificações | Yahoo Finance | StatusInvest scraping | Por evento |
| **Fiscal BR** | Dívida/PIB, resultado primário, gastos juros | Tesouro Nacional API | BCB SGS | Mensal |
| **Geopolítico** | Conflitos, tarifas, sanções, eleições | NewsAPI + NLP | GDELT Project | Contínua |

### Fetchers — status e prioridade

**Fase 1 — Críticos (CONCLUÍDA):**
- `FREDFetcher` — Federal Reserve Economic Data (gratuito, API key) **(CONCLUÍDO)**
- `CVMFetcher` — Dados abertos CVM (fundamentos BR, sem autenticação) **(CONCLUÍDO)**
- `TesouroDiretoFetcher` — Taxas de títulos públicos **(CONCLUÍDO)**
- `DDMFetcher` — Dividend Discount Model / stock screening **(CONCLUÍDO)**
- `ANBIMAFetcher` — Curva DI e taxas de referência **(DEPRIORITIZADO — dados de curva via BCB SGS)**

**Fetcher Maximization Sprint (entre Fases 1 e 2):**

Sprint dedicado a expandir os fetchers existentes para cobrir todas as séries definidas em constants.py e integrar mecanismos de fallback hierárquico.

| Sub-fase | Escopo | Status |
|----------|--------|--------|
| Sprint A | Deps (python-bcb, sidrapy, tradingcomdados), constants expandidos (BCB 57 séries, IBGE 17 tabelas, FRED 38 séries, 6 índices), FetchWithFallback helper, ReferenceLake (12 tabelas), TradingComDadosConfig | **CONCLUÍDA** |
| Sprint B | BCBFetcher (módulo bcb/ com 6 mixins incl. MercadoImobiliário, 105 métodos), IBGEFetcher (+analfabetismo, fix D3N/D4N, @cache_result), FREDFetcher (+23 convenience methods, FRED_SERIES unificada PT), auditoria (bcb_fetcher.py legado deletado, 697 testes) | **CONCLUÍDA** |
| Sprint C | Expansão Yahoo, DDM, Tesouro, CVM + TradingComDadosFetcher (novo) | Pendente |
| Sprint D | IngestNodes com fallback chains, testes de integração, docs finais | Pendente |

**Mecanismos de fallback (decididos no Sprint A):**
- `fetch_with_fallback()` (core/nodes/fetch_helpers.py) — orquestra ENTRE fetchers diferentes nos IngestNodes, com logging de proveniência
- `@fallback` decorator (utils/decorators.py) — opera DENTRO de um mesmo fetcher (ex: python-bcb → HTTP raw SGS)

**Fase 2 — Importantes (Pendente — NLP/Sentimento):**
- `NewsApiFetcher` — Headlines financeiras para NLP
- `RSSFetcher` — Reuters, Bloomberg, Valor Econômico
- `CoinGeckoFetcher` — Crypto (BTC/ETH como hedge)
- `GDELTFetcher` — Eventos geopolíticos quantificados

**Fase 3 — Complementares (Pendente):**
- `WorldBankFetcher` — Dados macro globais
- `TradingComDadosFetcher` — Dados B3 via tradingcomdados **(Sprint C — config pronta, fetcher pendente)**
- `AlphaVantageFetcher` — Fallback para Yahoo Finance

---

## Arquitetura do Sistema — Camadas

### Camada 1: Data Lake (Persistência Temporal)

> **STATUS: IMPLEMENTADO (Fase 0 + Fetcher Sprint A).** DataLake SQLite com 5 sub-lakes (PriceLake, MacroLake, FundamentalsLake, NewsLake) + ReferenceLake (12 tabelas de dados estruturais não-temporais: index_compositions, focus_expectations, analyst_targets, upgrades_downgrades, lending_rates, cnae_classifications, ticker_cnpj_map, major_holders, fund_registry, fund_portfolios, intermediaries, asset_registry). FetchWithFallback helper para orquestração de fallback entre fontes.

**Problema:** Atualmente os dados são efêmeros (buscados, usados e descartados). Estratégias de múltiplos prazos exigem séries temporais persistidas.

**Solução:** SQLite + Parquet para séries temporais, com API unificada de acesso.

```
data/
├── lake/
│   ├── prices.db          # SQLite: preços OHLCV diários (todos os ativos)
│   ├── fundamentals.db    # SQLite: dados fundamentalistas trimestrais
│   ├── macro.db           # SQLite: indicadores macro (BCB, FRED, IBGE)
│   ├── news.db            # SQLite: headlines + scores de sentimento
│   └── parquet/           # Parquet: séries longas para ML (leitura rápida)
│       ├── prices_10y.parquet
│       ├── macro_10y.parquet
│       └── features_*.parquet
├── outputs/
│   ├── snapshots/         # (existente) JSON diário
│   ├── portfolios/        # (existente) Excel atualizado
│   ├── reports/           # Relatórios gerados
│   └── backtests/         # Resultados de backtesting
└── raw/
    └── Carteira 2026.xlsx # (existente) Planilha master
```

**Implementação: `DataLake` class**

```python
# src/carteira_auto/data/lake/base.py
class DataLake:
    """Interface unificada para persistência de séries temporais."""

    def store_prices(self, df: pd.DataFrame, source: str) -> None: ...
    def get_prices(self, tickers: list[str], start: date, end: date) -> pd.DataFrame: ...
    def store_macro(self, indicator: str, df: pd.DataFrame) -> None: ...
    def get_macro(self, indicator: str, start: date, end: date) -> pd.DataFrame: ...
    def store_fundamentals(self, ticker: str, data: dict) -> None: ...
    def get_fundamentals(self, ticker: str, periods: int = 8) -> pd.DataFrame: ...
    def export_to_parquet(self, table: str, path: Path) -> None: ...
```

**Nodes de ingestão (existentes):**
- `IngestPricesNode` — Busca e persiste preços históricos de todos os ativos **(existente)**
- `IngestMacroNode` — Busca e persiste todos indicadores macro **(existente)**
- `IngestFundamentalsNode` — Busca e persiste dados fundamentalistas CVM **(existente)**
- `IngestNewsNode` — Busca e persiste headlines com timestamp **(existente)**
- `fetch_helpers.py` — FetchStrategy, FetchResult, fetch_with_fallback() para fallback hierárquico entre fontes **(existente — Fetcher Sprint A)**

### Camada 2: Analyzers (Refatoração + Novos)

**Refatoração dos existentes:**
Os analyzers atuais (PortfolioAnalyzer, RiskAnalyzer, MacroAnalyzer, MarketAnalyzer, Rebalancer, MarketSectorAnalyzer, EconomicSectorAnalyzer) devem passar a ler do DataLake quando dados históricos são necessários, em vez de buscar via fetcher a cada execução.

**Analyzers — status (3/11 concluídos, 8 pendentes):**

| Analyzer | Input | Output | Propósito | Status |
|----------|-------|--------|-----------|--------|
| `CurrencyAnalyzer` | DataLake (câmbio) | `CurrencyMetrics` | Análise de moedas e carry trade | **CONCLUÍDO** |
| `CommodityAnalyzer` | DataLake (commodities) | `CommodityMetrics` | Ciclo de commodities, termos de troca | **CONCLUÍDO** |
| `FiscalAnalyzer` | BCB/Tesouro | `FiscalMetrics` | Trajetória fiscal, dívida/PIB | **CONCLUÍDO** |
| `YieldCurveAnalyzer` | ANBIMA/Tesouro | `YieldCurveMetrics` | Curva DI, spreads, inversão | Pendente |
| `FundamentalAnalyzer` | DataLake (CVM) | `FundamentalMetrics` | Múltiplos, qualidade, scoring | Pendente |
| `GlobalMacroAnalyzer` | FRED + WorldBank | `GlobalMacroMetrics` | Ciclo global, diferencial de juros | Pendente |
| `CorrelationAnalyzer` | DataLake (prices) | `CorrelationMatrix` | Correlação entre ativos e classes | Pendente |
| `DividendAnalyzer` | Yahoo/CVM | `DividendMetrics` | DY, payout, crescimento de proventos | Pendente |
| `SentimentAnalyzer` | DataLake (news) | `SentimentMetrics` | NLP em headlines, Fear & Greed | Pendente (Fase 5) |
| `GeopoliticalAnalyzer` | GDELT + News | `GeopoliticalMetrics` | Risco geopolítico quantificado | Pendente (Fase 5) |
| `PersonalFinanceAnalyzer` | Planilha gastos | `PersonalFinanceMetrics` | Capacidade de aporte, projeção FI | Pendente |

### Camada 3: Framework de Estratégias

**Conceito:** Uma estratégia é uma composição de analyzers + lógica decisória + regras de risco que produz sinais e views para o optimizer. `Strategy` NÃO é um `Node` — é envolvida por um `StrategyNode(Node)` que adapta a interface para o DAG.

```python
# src/carteira_auto/strategies/base.py
from abc import ABC, abstractmethod
from pydantic import BaseModel

class Signal(BaseModel):
    """Sinal produzido por uma estratégia."""
    ticker: str
    action: str        # "buy", "sell", "hold", "reduce", "increase", "hedge"
    strength: float    # 0.0 a 1.0 (confiança)
    reason: str
    source_strategy: str  # Nome da estratégia que gerou
    metadata: dict = {}   # Dados que justificam o sinal

class StrategyResult(BaseModel):
    """Resultado unificado de uma estratégia (base ou composta).

    Este é o output de evaluate() — TUDO que a estratégia produz
    retorna neste modelo. O StrategyNode grava cada campo no ctx.
    """
    signals: list[Signal] = []
    views: dict[str, float] | None = None          # {ticker: retorno_esperado_anual}
    confidences: dict[str, float] | None = None     # {ticker: confiança 0-1}
    class_allocations: dict[str, float] | None = None  # {classe: peso%} (de layers macro)
    metadata: dict = {}

class Strategy(ABC):
    """Base para todas as estratégias.

    Relação com Node:
        - Strategy NÃO é um Node. Não tem run(), name, nem dependencies.
        - StrategyNode(Node) envolve uma Strategy e adapta para o DAG.
        - O DAGEngine só vê StrategyNode. Strategy é invisível para ele.

    Fluxo:
        DAGEngine.run("strategy_X")
        → resolve: [LoadPortfolio, FetchPrices, Analyzers..., StrategyNode]
        → StrategyNode.run(ctx) chama self.strategy.evaluate(ctx)
        → evaluate() lê métricas do ctx, aplica lógica, retorna StrategyResult
    """
    name: str
    description: str
    timeframe: str                     # "short", "medium", "long"
    required_analyzers: list[str]      # Nomes dos analyzer nodes necessários

    @abstractmethod
    def evaluate(self, ctx: "PipelineContext") -> StrategyResult:
        """Método central. Recebe contexto com analyzers executados,
        retorna sinais + views + confidences unificados.

        O ctx contém TUDO que os analyzers produziram porque o DAG
        garante execução na ordem correta via dependencies.
        """

    @abstractmethod
    def backtest_params(self) -> dict:
        """Parâmetros para backtesting."""


# src/carteira_auto/core/nodes/strategy_nodes.py
class StrategyNode(Node):
    """Ponte entre Strategy e DAGEngine.

    Envolve qualquer Strategy (base ou composta) e expõe como Node.
    O StrategyEngine cria StrategyNodes automaticamente.
    """
    def __init__(self, strategy: Strategy):
        self._strategy = strategy
        self.name = f"strategy_{strategy.name}"
        self.dependencies = list(set(strategy.required_analyzers))

    def run(self, ctx: PipelineContext) -> PipelineContext:
        result = self._strategy.evaluate(ctx)
        ctx["strategy_result"] = result
        ctx["signals"] = result.signals
        ctx["views"] = result.views
        ctx["view_confidences"] = result.confidences
        if result.class_allocations:
            ctx["class_allocations"] = result.class_allocations
        logger.info(
            f"Estratégia '{self._strategy.name}': "
            f"{len(result.signals)} sinais, "
            f"{len(result.views or {})} views BL"
        )
        return ctx
```

**CompositeStrategy — composição Layered como padrão:**

O modo padrão é Layered com N camadas de profundidade variável. Cada layer pode ser uma estratégia base ou um `WeightedBlend` de múltiplas estratégias. Qualquer layer pode ter um `gate` condicional (Layered + Conditional integrado).

```python
# src/carteira_auto/strategies/composite.py
from dataclasses import dataclass, field
from typing import Callable

@dataclass
class LayerGate:
    """Condição para ativar/desativar um layer.

    Se condition(ctx) retorna True → executa o layer normalmente.
    Se False → executa fallback (se houver) ou pula o layer.

    Permite combinar Layered + Conditional naturalmente:
    cada layer decide individualmente se executa.
    """
    condition: Callable[["PipelineContext"], bool]
    description: str                        # Human-readable (para logs e debug)
    fallback: "Strategy | None" = None      # Estratégia alternativa se gate False

@dataclass
class WeightedBlend:
    """Blend ponderado de múltiplas estratégias (usado DENTRO de um layer).

    Ao invés de uma estratégia base, um layer pode conter um blend:
    Layer(strategy=WeightedBlend([
        (MLScoring(), 0.6),
        (CrisisHedge(), 0.4),
    ]))
    """
    strategies: list[tuple[Strategy, float]]  # [(strategy, weight)]

    @property
    def required_analyzers(self) -> list[str]:
        analyzers = set()
        for strategy, _ in self.strategies:
            analyzers.update(strategy.required_analyzers)
        return list(analyzers)

    def evaluate(self, ctx: "PipelineContext") -> StrategyResult:
        """Executa todas e combina via média ponderada."""
        all_signals: dict[str, list[tuple[Signal, float]]] = {}
        combined_views: dict[str, float] = {}
        combined_confs: dict[str, float] = {}
        total_weight: dict[str, float] = {}

        for strategy, weight in self.strategies:
            result = strategy.evaluate(ctx)

            for signal in result.signals:
                all_signals.setdefault(signal.ticker, []).append((signal, weight))

            if result.views:
                for t, v in result.views.items():
                    combined_views[t] = combined_views.get(t, 0) + weight * v
                    total_weight[t] = total_weight.get(t, 0) + weight

            if result.confidences:
                for t, c in result.confidences.items():
                    combined_confs[t] = combined_confs.get(t, 0) + weight * c

        # Média ponderada dos sinais por ticker
        final_signals = self._weighted_combine(all_signals)

        # Média ponderada das views
        final_views = {t: combined_views[t] / total_weight[t]
                       for t in combined_views} if combined_views else None

        final_confs = {t: combined_confs[t] / total_weight.get(t, 1)
                       for t in combined_confs} if combined_confs else None

        return StrategyResult(
            signals=final_signals,
            views=final_views,
            confidences=final_confs,
        )

    def _weighted_combine(self, all_signals) -> list[Signal]:
        """Média ponderada de sinais conflitantes por ticker."""
        # ... implementação da média ponderada de strengths ...
        pass

@dataclass
class Layer:
    """Uma camada no pipeline Layered.

    Cada layer contém:
        - strategy: Strategy base OU WeightedBlend de múltiplas
        - gate: condição opcional (Layered + Conditional)
        - weight: influência deste layer no resultado final
    """
    strategy: "Strategy | WeightedBlend"
    weight: float = 1.0
    gate: LayerGate | None = None


class CompositeStrategy(Strategy):
    """Estratégia composta por N layers sequenciais.

    Modo padrão: LAYERED com gates condicionais opcionais.

    Fluxo de execução (dentro de evaluate):
        1. Para cada layer, na ordem:
           a. Verifica gate (se houver). Se False → fallback ou skip.
           b. Executa layer.strategy.evaluate(ctx)
           c. Grava resultado parcial no ctx (layer anterior visível pelo próximo)
        2. Após todos os layers:
           a. Combina sinais de todos os layers (últimos layers refinam primeiros)
           b. Agrega views BL (média ponderada por layer.weight)
           c. Retorna StrategyResult unificado

    Cada layer VÊ os resultados dos layers anteriores via ctx.
    Isso é o que torna Layered poderoso: o layer 2 (ValueInvesting)
    sabe que o layer 1 (MacroTactical) definiu "Ações: 35%", e seleciona
    ativos DENTRO dessa alocação.
    """

    def __init__(
        self,
        name: str,
        description: str,
        layers: list[Layer],
        timeframe: str = "medium",
    ):
        self.name = name
        self.description = description
        self.timeframe = timeframe
        self._layers = layers

    @property
    def required_analyzers(self) -> list[str]:
        """União de todos os analyzers de todos os layers (incluindo fallbacks)."""
        analyzers: set[str] = set()
        for layer in self._layers:
            if isinstance(layer.strategy, WeightedBlend):
                analyzers.update(layer.strategy.required_analyzers)
            else:
                analyzers.update(layer.strategy.required_analyzers)
            if layer.gate and layer.gate.fallback:
                analyzers.update(layer.gate.fallback.required_analyzers)
        return list(analyzers)

    def evaluate(self, ctx: "PipelineContext") -> StrategyResult:
        """Executa layers sequencialmente, cada um enriquecendo o ctx."""
        layer_results: list[tuple[StrategyResult, float]] = []

        for i, layer in enumerate(self._layers):
            # 1. Verifica gate condicional
            strategy_to_run = self._resolve_gate(layer, ctx)
            if strategy_to_run is None:
                logger.info(f"  Layer {i} ({layer.strategy.name}): SKIPPED (gate False, sem fallback)")
                continue

            # 2. Executa a estratégia do layer
            result = strategy_to_run.evaluate(ctx)

            # 3. Grava resultado parcial no ctx para próximo layer ver
            ctx[f"layer_{i}_result"] = result
            if result.class_allocations:
                ctx["class_allocations"] = result.class_allocations

            layer_results.append((result, layer.weight))
            logger.info(
                f"  Layer {i}: {len(result.signals)} sinais, "
                f"{len(result.views or {})} views"
            )

        # 4. Combine final: mescla resultados de todos os layers
        return self._combine_layers(layer_results)

    def _resolve_gate(self, layer: Layer, ctx) -> "Strategy | WeightedBlend | None":
        """Resolve o gate condicional de um layer."""
        if layer.gate is None:
            return layer.strategy  # Sem gate → sempre executa

        if layer.gate.condition(ctx):
            return layer.strategy  # Gate True → executa normalmente
        elif layer.gate.fallback:
            return layer.gate.fallback  # Gate False + fallback → executa fallback
        else:
            return None  # Gate False + sem fallback → skip

    def _combine_layers(
        self, layer_results: list[tuple[StrategyResult, float]]
    ) -> StrategyResult:
        """Combina resultados de todos os layers.

        Sinais: último layer que opina sobre um ticker prevalece (top-down refinement).
        Views: média ponderada por layer.weight.
        Class allocations: último layer que define prevalece.
        """
        final_signals: dict[str, Signal] = {}
        combined_views: dict[str, float] = {}
        combined_confs: dict[str, float] = {}
        total_weight: dict[str, float] = {}
        final_allocations: dict[str, float] | None = None

        for result, weight in layer_results:
            # Sinais: sobrescrevem por ticker (layers posteriores refinam)
            for signal in result.signals:
                final_signals[signal.ticker] = signal

            # Views: acumulam ponderadamente
            if result.views:
                for t, v in result.views.items():
                    combined_views[t] = combined_views.get(t, 0) + weight * v
                    total_weight[t] = total_weight.get(t, 0) + weight

            if result.confidences:
                for t, c in result.confidences.items():
                    combined_confs[t] = combined_confs.get(t, 0) + weight * c

            if result.class_allocations:
                final_allocations = result.class_allocations

        return StrategyResult(
            signals=list(final_signals.values()),
            views={t: combined_views[t] / total_weight[t]
                   for t in combined_views} if combined_views else None,
            confidences={t: combined_confs[t] / total_weight.get(t, 1)
                         for t in combined_confs} if combined_confs else None,
            class_allocations=final_allocations,
        )

    def backtest_params(self) -> dict:
        """Usa params do último layer como base."""
        if self._layers:
            last = self._layers[-1].strategy
            if isinstance(last, WeightedBlend):
                return last.strategies[0][0].backtest_params()
            return last.backtest_params()
        return {}


# =========================================================================
# PRESETS — estratégias compostas pré-configuradas
# =========================================================================
# src/carteira_auto/strategies/presets.py

# Exemplo: TacticalValue (3 layers com gate condicional)
tactical_value = CompositeStrategy(
    name="tactical_value",
    description="Macro define classe → Value seleciona ativo → ML+Crisis ajusta",
    layers=[
        # Layer 1: Alocação por classe (sempre executa)
        Layer(strategy=MacroTactical(), weight=1.0),

        # Layer 2: Seleção de ativos dentro da classe (sempre executa)
        Layer(strategy=ValueInvesting(), weight=1.0),

        # Layer 3: Ajuste fino — modo varia por regime de mercado
        Layer(
            strategy=WeightedBlend([
                (MLScoring(), 0.7),
                (MomentumRotation(), 0.3),
            ]),
            weight=0.8,
            gate=LayerGate(
                condition=lambda ctx: ctx.get("sentiment", {}).get("score", 0) >= -0.3,
                description="Sentimento neutro ou positivo → ML + Momentum",
                fallback=CrisisHedge(),  # Sentimento negativo → ativa hedge
            ),
        ),
    ],
)
```

**Estratégias planejadas (base + compostas):**

| Estratégia | Tipo | Analyzers | Horizonte | Descrição |
|------------|------|-----------|-----------|-----------|
| `ValueInvesting` | Base — Fundamentalista | Fundamental, Dividend, Risk | Longo | Graham/Buffett: P/L, P/VP, DY, ROE, dívida |
| `MacroTactical` | Base — Top-down | Macro, GlobalMacro, Currency, Fiscal | Médio | Alocação por classe baseada em ciclo econômico |
| `MomentumRotation` | Base — Quantitativa | Market, MarketSector, Correlation | Curto/Médio | Rotação setorial por momentum relativo |
| `RiskParity` | Base — Quantitativa | Risk, Correlation, YieldCurve | Médio | Alocação por contribuição equitativa de risco |
| `IncomeOptimizer` | Base — Renda passiva | Dividend, Fundamental, YieldCurve | Longo | Maximiza fluxo de caixa (proventos + RF) |
| `CrisisHedge` | Base — Defensiva | Geopolitical, Sentiment, Commodity, Currency | Tático | Proteção em cenários de cauda (ouro, USD, puts) |
| `MLScoring` | Base — ML | Fundamental, Macro, Sentiment | Variado | Scoring via model treinado |
| `EmancipationPath` | Base — Planejamento | PersonalFinance, todas | Longo prazo | Projeção de independência financeira |
| `TacticalValue` | **Composta — 3 layers** | Macro → Value → [ML+Crisis] | Médio/Longo | Padrão: layered + gate condicional no layer 3 |
| `DefensiveIncome` | **Composta — 2 layers** | Income → Crisis (gated) | Longo | Income normal; hedge quando sentimento < threshold |
| `FullSpectrum` | **Composta — 4 layers** | Macro → Value → ML blend → Risk Parity | Multi | Pipeline completo com todos os inputs |

**Como estratégias viram pipelines (StrategyEngine):**

```python
# src/carteira_auto/strategies/registry.py
class StrategyEngine:
    """Converte estratégias em pipelines DAG executáveis.

    Recebe uma Strategy (base ou composta), resolve recursivamente
    todos os analyzers necessários, cria os Nodes correspondentes,
    e registra tudo no DAGEngine.
    """

    def build_pipeline(self, strategy: Strategy, dag: DAGEngine) -> str:
        """Registra nodes necessários e retorna o nome do node terminal.

        Retorna: nome do StrategyNode (ou OptimizerNode se optimize=True)
        """
        # 1. Coleta analyzers necessários (recursivo para compostas/blends)
        analyzer_names = strategy.required_analyzers

        # 2. Registra analyzer nodes (se não já registrados)
        for name in analyzer_names:
            if name not in dag.list_nodes():
                node = self._create_analyzer_node(name)
                dag.register(node)

        # 3. Cria e registra StrategyNode
        strategy_node = StrategyNode(strategy)
        dag.register(strategy_node)

        # 4. Cria e registra OptimizerNode (depende do StrategyNode)
        optimizer_node = OptimizePortfolioNode()
        optimizer_node.dependencies = [strategy_node.name, "fetch_portfolio_prices"]
        dag.register(optimizer_node)

        # 5. Retorna o node terminal
        return optimizer_node.name
```

### Camada 3.5: Portfolio Optimizer (PyPortfolioOpt)

A otimização de portfólio é uma **camada independente** que consome sinais e views das estratégias e produz pesos ótimos. Não é um analyzer nem uma estratégia — é o mecanismo que traduz intenções (sinais, views) em alocações concretas (pesos por ativo) respeitando constraints reais do mercado brasileiro.

**Biblioteca central: `pypfopt` (PyPortfolioOpt)**

```python
# =========================================================================
# src/carteira_auto/config/optimization.py
# Enums e config ficam no módulo de config, junto a settings.py e constants.py.
# =========================================================================
from enum import Enum
from pydantic import BaseModel

class OptimizationObjective(str, Enum):
    """Objetivos de otimização disponíveis."""
    MAX_SHARPE = "max_sharpe"              # Máximo Sharpe ratio
    MIN_VOLATILITY = "min_volatility"      # Mínima volatilidade
    MAX_QUADRATIC_UTILITY = "max_utility"  # Máxima utilidade quadrática
    EFFICIENT_RISK = "efficient_risk"      # Retorno máximo dado um risco target
    EFFICIENT_RETURN = "efficient_return"  # Risco mínimo dado um retorno target
    MIN_CVAR = "min_cvar"                  # Mínimo CVaR (Conditional VaR)
    RISK_PARITY = "risk_parity"            # Contribuição equitativa de risco
    HRP = "hrp"                            # Hierarchical Risk Parity

class RiskModelType(str, Enum):
    """Modelos de risco (covariância) disponíveis."""
    SAMPLE = "sample"                      # Covariância amostral (naive)
    SEMICOVARIANCE = "semicovariance"      # Semicovariância (só downside)
    EXP_COVARIANCE = "exp_cov"             # Covariância ponderada exponencialmente
    LEDOIT_WOLF = "ledoit_wolf"            # Shrinkage Ledoit-Wolf (default)
    ORACLE_APPROX = "oracle_approximating" # Oracle Approximating Shrinkage
    SHRUNK_COVARIANCE = "shrunk_covariance" # Covariância com shrinkage genérico
    DENOISED = "denoised"                  # Random Matrix Theory denoising
    HYBRID_ML = "hybrid_ml"               # CUSTOM: híbrida com ML (ver abaixo)

class ReturnModelType(str, Enum):
    """Modelos de retorno esperado."""
    MEAN_HISTORICAL = "mean_historical"    # Média histórica simples
    EMA_HISTORICAL = "ema_historical"      # Média exponencialmente ponderada
    CAPM = "capm"                          # Capital Asset Pricing Model
    BLACK_LITTERMAN = "black_litterman"    # Black-Litterman com views
    ML_PREDICTED = "ml_predicted"          # CUSTOM: retornos via ML scorer

class OptimizationConfig(BaseModel):
    """Configuração completa de uma otimização.

    LOCALIZAÇÃO: src/carteira_auto/config/optimization.py
    (junto aos demais configs: settings.py, constants.py)

    Os enums (OptimizationObjective, RiskModelType, ReturnModelType)
    também ficam neste arquivo.
    """

    # Objetivo
    objective: OptimizationObjective = OptimizationObjective.MAX_SHARPE

    # Modelos
    risk_model: RiskModelType = RiskModelType.LEDOIT_WOLF
    return_model: ReturnModelType = ReturnModelType.BLACK_LITTERMAN

    # Parâmetros do risk model
    risk_lookback_days: int = 504          # 2 anos de dados diários
    exp_cov_span: int = 180                # Span para covariância exponencial
    shrinkage_target: str = "constant_correlation"  # Target para shrinkage

    # Black-Litterman
    bl_tau: float = 0.05                   # Incerteza no equilíbrio (0.01-0.1)
    bl_risk_aversion: float = 1.0          # Aversão ao risco do mercado

    # Risk parity
    risk_free_rate: float = 0.1475         # Selic atual como rf (14.75%)

    # Constraints brasileiras
    min_weight: float = 0.0                # Peso mínimo por ativo (0 = pode zerar)
    max_weight: float = 0.15               # Peso máximo por ativo (15%)
    max_sector_weight: float = 0.30        # Máximo por setor (30%)
    min_asset_count: int = 10              # Mínimo de ativos na carteira
    max_asset_count: int = 40              # Máximo de ativos

    # Alocação discreta (lotes B3)
    total_portfolio_value: float = 0.0     # Valor total para alocação discreta
    min_trade_value: float = 100.0         # Operação mínima em R$
    lot_size: int = 1                      # Lote mínimo (1 para fracionário)

    # Turnover constraint
    max_turnover: float = 0.30             # Máximo 30% de turnover por rebalanceamento
    current_weights: dict[str, float] | None = None  # Pesos atuais (para L2 penalty)

    # Regularização
    l2_gamma: float = 0.1                  # Penalidade L2 para turnover
    sector_constraints: dict[str, tuple[float, float]] | None = None  # {setor: (min, max)}


class OptimizationResult(BaseModel):
    """Resultado da otimização."""

    weights: dict[str, float]              # Pesos ótimos contínuos
    discrete_allocation: dict[str, int] | None = None  # Quantidade inteira por ativo
    leftover: float = 0.0                  # Dinheiro remanescente após alocação discreta
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    expected_sharpe: float = 0.0
    objective_value: float = 0.0
    risk_model_used: str = ""
    return_model_used: str = ""
    covariance_matrix: dict | None = None  # Para debug/visualização
    frontier_points: list[dict] | None = None  # Pontos da fronteira eficiente


# =========================================================================
# src/carteira_auto/optimization/optimizer.py
# O optimizer IMPORTA config de carteira_auto.config.optimization
# =========================================================================
from carteira_auto.config.optimization import (
    OptimizationConfig, OptimizationObjective, RiskModelType, ReturnModelType,
    OptimizationResult,
)
from pypfopt import (
    EfficientFrontier, BlackLittermanModel, HRPOpt, CLA,
    risk_models, expected_returns, black_litterman,
    objective_functions, DiscreteAllocation,
)
from pypfopt.risk_models import CovarianceShrinkage
import numpy as np
import pandas as pd

class PortfolioOptimizer:
    """Otimizador de portfólio avançado usando PyPortfolioOpt.

    Pipeline de otimização:
        1. Buscar retornos históricos do DataLake
        2. Estimar retornos esperados (mean, CAPM, Black-Litterman, ou ML)
        3. Estimar matriz de covariância (com shrinkage/denoising)
        4. Aplicar objetivo de otimização com constraints
        5. Converter pesos contínuos em alocação discreta (lotes B3)
        6. Calcular métricas da carteira otimizada

    Exemplo de uso:
        optimizer = PortfolioOptimizer(data_lake)
        config = OptimizationConfig(
            objective=OptimizationObjective.MAX_SHARPE,
            risk_model=RiskModelType.LEDOIT_WOLF,
            return_model=ReturnModelType.BLACK_LITTERMAN,
        )
        result = optimizer.optimize(
            tickers=["PETR4", "VALE3", "ITSA4", ...],
            config=config,
            views=strategy.get_views(ctx),       # Views de Black-Litterman
            confidences=strategy.get_view_confidences(ctx),
        )
    """

    def __init__(self, data_lake: "DataLake"):
        self.lake = data_lake

    def optimize(
        self,
        tickers: list[str],
        config: OptimizationConfig,
        views: dict[str, float] | None = None,
        confidences: dict[str, float] | None = None,
        market_caps: dict[str, float] | None = None,
    ) -> OptimizationResult:
        """Pipeline completo de otimização."""
        # 1. Buscar retornos
        prices = self.lake.get_prices(tickers, lookback=config.risk_lookback_days)
        returns = prices.pct_change().dropna()

        # 2. Estimar retornos esperados
        mu = self._estimate_returns(returns, prices, config, views,
                                     confidences, market_caps)

        # 3. Estimar matriz de covariância
        S = self._estimate_covariance(returns, config)

        # 4. Otimizar
        weights = self._run_optimization(mu, S, config)

        # 5. Alocação discreta (se valor total fornecido)
        discrete, leftover = self._discrete_allocation(
            weights, prices, config
        )

        # 6. Métricas
        return self._build_result(weights, mu, S, discrete, leftover, config)

    # ================================================================
    # MODELOS DE RETORNO ESPERADO
    # ================================================================

    def _estimate_returns(self, returns, prices, config, views,
                          confidences, market_caps) -> pd.Series:
        """Estima retornos esperados segundo o modelo configurado."""

        if config.return_model == ReturnModelType.MEAN_HISTORICAL:
            return expected_returns.mean_historical_return(prices)

        elif config.return_model == ReturnModelType.EMA_HISTORICAL:
            return expected_returns.ema_historical_return(
                prices, span=config.exp_cov_span
            )

        elif config.return_model == ReturnModelType.CAPM:
            return expected_returns.capm_return(prices)

        elif config.return_model == ReturnModelType.BLACK_LITTERMAN:
            return self._black_litterman_returns(
                prices, returns, views, confidences, market_caps, config
            )

        elif config.return_model == ReturnModelType.ML_PREDICTED:
            return self._ml_predicted_returns(returns, config)

    def _black_litterman_returns(
        self, prices, returns, views, confidences, market_caps, config
    ) -> pd.Series:
        """Calcula retornos de equilíbrio Black-Litterman com views.

        O Black-Litterman combina:
        1. Retornos implícitos do mercado (equilíbrio CAPM reverso)
        2. Views do investidor (das estratégias) com incertezas
        3. Produz retornos ajustados que respeitam a estrutura de mercado

        Views podem vir de:
        - Estratégias base (ValueInvesting, MacroTactical)
        - ML scorer (retornos preditos)
        - CompositeStrategy (views agregadas)
        """
        S = self._estimate_covariance(returns, config)

        # Market-implied risk aversion (delta)
        delta = black_litterman.market_implied_risk_aversion(
            prices.iloc[-1].mean(),  # market return proxy
            risk_free_rate=config.risk_free_rate / 252,  # Diário
        )

        # Retornos implícitos de equilíbrio (pi)
        if market_caps:
            pi = black_litterman.market_implied_prior_returns(
                market_caps, delta, S,
                risk_free_rate=config.risk_free_rate / 252,
            )
        else:
            # Fallback: usa pesos iguais se market caps indisponíveis
            pi = expected_returns.capm_return(prices)

        # Se não há views, retorna equilíbrio puro
        if not views:
            return pi

        # Constrói modelo BL com views
        bl = BlackLittermanModel(
            S,
            pi=pi,
            absolute_views=views,
            omega="idzorek",  # Método de Idzorek para calibrar omega
            view_confidences=list(confidences.values()) if confidences else None,
            tau=config.bl_tau,
        )

        return bl.bl_returns()

    def _ml_predicted_returns(self, returns, config) -> pd.Series:
        """Retornos preditos pelo ML scorer como mu para otimização."""
        # Busca previsões do FundamentalScorer no contexto ou no DataLake
        # Mapeia scores de classificação → retornos esperados
        pass  # Implementação na Fase 4

    # ================================================================
    # MODELOS DE RISCO (COVARIÂNCIA)
    # ================================================================

    def _estimate_covariance(
        self, returns: pd.DataFrame, config: OptimizationConfig
    ) -> pd.DataFrame:
        """Estima matriz de covariância segundo o modelo configurado.

        O shrinkage é ESSENCIAL para carteiras reais:
        - Covariância amostral é ruidosa com N ativos e T observações
        - Ledoit-Wolf encolhe rumo a uma matriz estruturada (menor erro)
        - Oracle Approximating é mais agressivo, bom para N >> T
        - Denoised usa Random Matrix Theory para limpar eigenvalues espúrios
        """

        if config.risk_model == RiskModelType.SAMPLE:
            return risk_models.sample_cov(returns)

        elif config.risk_model == RiskModelType.SEMICOVARIANCE:
            return risk_models.semicovariance(returns)

        elif config.risk_model == RiskModelType.EXP_COVARIANCE:
            return risk_models.exp_cov(returns, span=config.exp_cov_span)

        elif config.risk_model == RiskModelType.LEDOIT_WOLF:
            cs = CovarianceShrinkage(returns)
            return cs.ledoit_wolf(
                shrinkage_target=config.shrinkage_target
            )

        elif config.risk_model == RiskModelType.ORACLE_APPROX:
            cs = CovarianceShrinkage(returns)
            return cs.oracle_approximating()

        elif config.risk_model == RiskModelType.SHRUNK_COVARIANCE:
            cs = CovarianceShrinkage(returns)
            return cs.shrunk_covariance()

        elif config.risk_model == RiskModelType.DENOISED:
            # Random Matrix Theory denoising (Marchenko-Pastur)
            return self._denoised_covariance(returns)

        elif config.risk_model == RiskModelType.HYBRID_ML:
            return self._hybrid_ml_covariance(returns, config)

    def _denoised_covariance(self, returns: pd.DataFrame) -> pd.DataFrame:
        """Covariância denoised via Random Matrix Theory.

        Baseado em Lopez de Prado (Advances in Financial ML):
        1. Calcula eigenvalues da covariância amostral
        2. Compara com distribuição Marchenko-Pastur (random matrix)
        3. Eigenvalues abaixo do threshold teórico = ruído → substituídos
        4. Reconstrói a matriz com eigenvalues limpos
        """
        from sklearn.covariance import LedoitWolf

        # Base: Ledoit-Wolf como ponto de partida
        lw = LedoitWolf().fit(returns)
        S_lw = pd.DataFrame(lw.covariance_, index=returns.columns,
                             columns=returns.columns)

        # Denoising via eigenvalue clipping (Marchenko-Pastur)
        T, N = returns.shape
        q = T / N  # Ratio observações/variáveis

        eigenvalues, eigenvectors = np.linalg.eigh(S_lw.values)
        lambda_plus = (1 + 1/np.sqrt(q))**2  # Marchenko-Pastur upper bound

        # Clip eigenvalues abaixo do threshold
        eigenvalues_clean = np.where(
            eigenvalues > lambda_plus * np.median(eigenvalues),
            eigenvalues,
            np.median(eigenvalues[eigenvalues <= lambda_plus * np.median(eigenvalues)])
        )

        # Reconstrói a matriz
        S_denoised = eigenvectors @ np.diag(eigenvalues_clean) @ eigenvectors.T
        return pd.DataFrame(S_denoised, index=returns.columns,
                             columns=returns.columns)

    def _hybrid_ml_covariance(
        self, returns: pd.DataFrame, config: OptimizationConfig
    ) -> pd.DataFrame:
        """Covariância híbrida: combina shrinkage + regime detection.

        1. Ledoit-Wolf para estimativa base (estável)
        2. Covariância exponencialmente ponderada para capturar regime recente
        3. Blend ponderado pelo regime detectado:
           - Regime de crise (vol alta): mais peso no exp_cov (reativo)
           - Regime normal: mais peso no LW (estável)
        4. Denoising final via RMT
        """
        # Componente 1: Ledoit-Wolf (estável)
        cs = CovarianceShrinkage(returns)
        S_lw = cs.ledoit_wolf()

        # Componente 2: Exponencialmente ponderada (recente)
        S_exp = risk_models.exp_cov(returns, span=config.exp_cov_span)

        # Detecção de regime via volatilidade realizada
        recent_vol = returns.iloc[-21:].std().mean()  # Vol últimos 21 dias
        long_vol = returns.std().mean()                # Vol total
        vol_ratio = recent_vol / long_vol if long_vol > 0 else 1.0

        # Peso adaptativo: mais exp_cov em regime de stress
        crisis_weight = min(max((vol_ratio - 1.0) / 0.5, 0.0), 0.8)
        stable_weight = 1.0 - crisis_weight

        # Blend
        S_hybrid = stable_weight * S_lw + crisis_weight * S_exp

        # Fix: garante positive semi-definite
        return risk_models.fix_nonpositive_semidefinite(S_hybrid)

    # ================================================================
    # OTIMIZAÇÃO
    # ================================================================

    def _run_optimization(
        self, mu: pd.Series, S: pd.DataFrame, config: OptimizationConfig
    ) -> dict[str, float]:
        """Executa a otimização com constraints."""

        if config.objective == OptimizationObjective.HRP:
            # HRP não usa mu, apenas covariância
            hrp = HRPOpt(returns=None, cov_matrix=S)
            return hrp.optimize()

        elif config.objective == OptimizationObjective.RISK_PARITY:
            ef = EfficientFrontier(mu, S, weight_bounds=(config.min_weight, config.max_weight))
            ef.nonconvex_objective(
                objective_functions.portfolio_variance,
                objective_args=(ef.cov_matrix,),
            )
            return ef.clean_weights()

        else:
            ef = EfficientFrontier(
                mu, S,
                weight_bounds=(config.min_weight, config.max_weight),
            )

            # Constraints adicionais
            if config.sector_constraints:
                for sector, (lo, hi) in config.sector_constraints.items():
                    sector_tickers = self._get_sector_tickers(sector)
                    ef.add_sector_constraints(
                        {t: sector for t in sector_tickers
                         if t in mu.index},
                        sector_lower={sector: lo},
                        sector_upper={sector: hi},
                    )

            # Turnover constraint (L2 regularization)
            if config.current_weights and config.l2_gamma > 0:
                ef.add_objective(
                    objective_functions.L2_reg,
                    gamma=config.l2_gamma,
                )

            # Objetivo
            if config.objective == OptimizationObjective.MAX_SHARPE:
                ef.max_sharpe(risk_free_rate=config.risk_free_rate)
            elif config.objective == OptimizationObjective.MIN_VOLATILITY:
                ef.min_volatility()
            elif config.objective == OptimizationObjective.MAX_QUADRATIC_UTILITY:
                ef.max_quadratic_utility(risk_aversion=config.bl_risk_aversion)
            elif config.objective == OptimizationObjective.EFFICIENT_RISK:
                ef.efficient_risk(target_volatility=0.15)  # Configurável
            elif config.objective == OptimizationObjective.EFFICIENT_RETURN:
                ef.efficient_return(target_return=0.20)     # Configurável

            return ef.clean_weights()

    def _discrete_allocation(
        self, weights, prices, config
    ) -> tuple[dict[str, int] | None, float]:
        """Converte pesos contínuos em quantidades inteiras (lotes B3)."""
        if config.total_portfolio_value <= 0:
            return None, 0.0

        latest_prices = prices.iloc[-1]
        da = DiscreteAllocation(
            weights, latest_prices,
            total_portfolio_value=config.total_portfolio_value,
            short_ratio=0.0,  # Sem short (PF brasileiro)
        )
        allocation, leftover = da.greedy_portfolio()
        return allocation, leftover

    # ================================================================
    # EFFICIENT FRONTIER (para visualização)
    # ================================================================

    def compute_frontier(
        self, tickers: list[str], config: OptimizationConfig, n_points: int = 50
    ) -> list[dict]:
        """Calcula pontos da fronteira eficiente para plotagem."""
        prices = self.lake.get_prices(tickers, lookback=config.risk_lookback_days)
        returns = prices.pct_change().dropna()
        mu = self._estimate_returns(returns, prices, config, None, None, None)
        S = self._estimate_covariance(returns, config)

        cla = CLA(mu, S, weight_bounds=(config.min_weight, config.max_weight))
        cla.max_sharpe()

        # Pontos da fronteira
        frontier = []
        min_ret = mu.min()
        max_ret = mu.max()
        for target_ret in np.linspace(min_ret, max_ret, n_points):
            try:
                ef = EfficientFrontier(mu, S,
                    weight_bounds=(config.min_weight, config.max_weight))
                ef.efficient_return(target_ret)
                perf = ef.portfolio_performance(risk_free_rate=config.risk_free_rate)
                frontier.append({
                    "return": perf[0], "volatility": perf[1], "sharpe": perf[2]
                })
            except Exception:
                continue

        return frontier
```

**OptimizerNode no DAG:**

```python
# src/carteira_auto/core/nodes/optimizer_nodes.py
class OptimizePortfolioNode(Node):
    """Executa otimização de portfólio após geração de sinais.

    Lê do contexto:
        - "portfolio": Portfolio (pesos atuais)
        - "signals": list[Signal] (de estratégias)
        - "views": dict[str, float] (de Black-Litterman, opcional)
        - "view_confidences": dict[str, float] (opcional)
        - "optimization_config": OptimizationConfig (opcional, usa default)

    Produz no contexto:
        - "optimization_result": OptimizationResult
        - "rebalance_orders": list[RebalanceOrder]  # Ordens concretas
    """
    name = "optimize_portfolio"
    dependencies = ["fetch_portfolio_prices", "analyze_risk"]
```

### Camada 4: Backtesting Engine

```python
# src/carteira_auto/backtesting/engine.py
@dataclass
class BacktestConfig:
    """Configuração de um backtest."""
    strategy: Strategy
    start_date: date
    end_date: date
    initial_capital: float
    rebalance_frequency: str  # "daily", "weekly", "monthly"
    transaction_cost: float   # % por operação
    tax_config: dict          # regras tributárias BR

@dataclass
class BacktestResult:
    """Resultado de um backtest."""
    returns: pd.Series
    trades: pd.DataFrame
    metrics: dict              # Sharpe, Sortino, max_dd, alpha, beta, etc.
    benchmark_comparison: dict # vs CDI, IBOV, IFIX
    monthly_returns: pd.DataFrame
    drawdown_series: pd.Series

class BacktestEngine:
    """Motor de backtesting."""

    def __init__(self, data_lake: DataLake):
        self.lake = data_lake

    def run(self, config: BacktestConfig) -> BacktestResult:
        """Executa backtest histórico de uma estratégia."""

    def walk_forward(self, config: BacktestConfig, folds: int = 5) -> list[BacktestResult]:
        """Walk-forward analysis para validação robusta."""

    def monte_carlo(self, config: BacktestConfig, simulations: int = 1000) -> dict:
        """Simulação Monte Carlo dos retornos."""

    def compare(self, results: list[BacktestResult]) -> pd.DataFrame:
        """Compara múltiplas estratégias lado a lado."""
```

### Camada 5: ML Pipeline

**Prioridade 1 — Scoring Fundamentalista:**
```python
# src/carteira_auto/ml/scoring/fundamental_scorer.py
class FundamentalScorer:
    """Classifica ativos por qualidade fundamentalista via ML.

    Features:
        - Múltiplos: P/L, P/VP, EV/EBITDA, P/FCF
        - Qualidade: ROE, ROIC, margem líquida, margem EBITDA
        - Endividamento: Dívida Líquida/EBITDA, Dívida Líquida/PL
        - Crescimento: CAGR receita 3a, CAGR lucro 3a
        - Proventos: DY, payout, crescimento de dividendos
        - Momentum: retorno 6m, 12m, volatilidade

    Target: retorno forward (6m, 12m) ajustado por risco

    Modelos:
        - XGBoost (classificação: quintis de retorno)
        - Random Forest (feature importance para interpretabilidade)
        - Ensemble: média ponderada dos modelos
    """
```

**Prioridade 2 — Otimização de Portfólio:**
A otimização avançada com PyPortfolioOpt já está especificada na Camada 3.5. Na Fase 4, o foco é integrar ML com o optimizer:
- ML scorer produz retornos esperados (`ReturnModelType.ML_PREDICTED`)
- Regime detection via volatilidade alimenta a covariância híbrida (`RiskModelType.HYBRID_ML`)
- Views de Black-Litterman são geradas pelas estratégias (base e compostas)
- Feature importance do XGBoost calibra as confidências das views

**Prioridade 3 — Análise de Sentimento:**
```python
# src/carteira_auto/ml/nlp/sentiment_analyzer.py
class NewsSentimentAnalyzer:
    """Análise de sentimento em notícias financeiras.

    Pipeline:
        1. Coleta: NewsAPI + RSS feeds
        2. Pré-processamento: limpeza, tokenização
        3. Classificação: modelo pré-treinado (FinBERT ou similar)
        4. Agregação: score por ticker, setor, mercado
        5. Sinal: desvio do sentimento médio como indicador contrarian

    Modelo: FinBERT fine-tuned em notícias BR (ou transformer multilingual)
    """
```

**Prioridade 4 — Séries Temporais:**
```python
# src/carteira_auto/ml/timeseries/forecaster.py
class TimeSeriesForecaster:
    """Previsão de séries temporais financeiras.

    Modelos:
        - ARIMA/GARCH para volatilidade
        - Prophet para sazonalidade macro
        - LSTM para padrões não-lineares
        - Ensemble: combinação de modelos

    Nota: Previsão de preços tem utilidade limitada (EMH).
    Foco real: previsão de indicadores macro (Selic, IPCA, câmbio)
    para alimentar cenários nas estratégias de alocação.
    """
```

### Camada 6: Personal Finance Integration

```python
# src/carteira_auto/personal/finance_tracker.py
class FinanceTracker:
    """Integra dados pessoais para projeção de independência financeira.

    Inputs:
        - Planilha de gastos (gastos.xlsx)
        - Carteira atual (Carteira 2026.xlsx)
        - Projeções de renda (crescimento salarial estimado)

    Outputs:
        - Taxa de poupança efetiva
        - Capacidade de aporte mensal
        - Projeção de patrimônio (Monte Carlo)
        - Data estimada de independência financeira
        - Número de anos para FI com diferentes cenários de retorno
        - "Crossover point" — quando renda passiva > gastos
    """
```

### Camada 7: AI Reasoning Layer (Claude / Deepseek)

A camada de raciocínio artificial transforma dados quantitativos em análises narrativas, recomendações textuais e conteúdo inteligente. Ela recebe o PipelineContext completo (métricas, sinais, notícias, alertas) e produz conteúdo estruturado para os canais de output.

**Conceito central:** O sistema não apenas calcula — ele *pensa*. A IA interpreta os números sob a lente do materialismo histórico-dialético, identifica contradições nos dados, sintetiza múltiplas fontes e comunica insights de forma acionável.

```python
# src/carteira_auto/ai/providers/base.py
from abc import ABC, abstractmethod
from pydantic import BaseModel

class AIProvider(ABC):
    """Interface para provedores de IA (Claude, Deepseek, etc.)."""

    @abstractmethod
    async def complete(self, prompt: str, system: str, **kwargs) -> str: ...

    @abstractmethod
    async def complete_structured(self, prompt: str, system: str,
                                   response_model: type[BaseModel]) -> BaseModel: ...

# src/carteira_auto/ai/providers/claude_provider.py
class ClaudeProvider(AIProvider):
    """Anthropic Claude API — análise profunda, raciocínio complexo."""
    # Modelo: claude-sonnet-4-20250514 (custo-benefício para análises recorrentes)
    # Modelo: claude-opus-4-20250514 (relatórios profundos, análises de cenário)

# src/carteira_auto/ai/providers/deepseek_provider.py
class DeepseekProvider(AIProvider):
    """Deepseek API — fallback de custo baixo, bom para tarefas repetitivas."""
```

**PromptEngine — templates e routing:**

```python
# src/carteira_auto/ai/prompts/engine.py
class PromptEngine:
    """Gerencia templates de prompt e roteia para o provider adequado.

    Cada tipo de análise tem:
        - system_prompt: instrução fixa com papel e contexto
        - user_template: template com placeholders preenchidos pelo contexto
        - response_model: Pydantic model do output esperado (structured output)
        - provider_preference: qual IA usar (Claude para complexo, Deepseek para simples)
        - max_tokens / temperature: configs por tipo

    Tipos de análise:
        - portfolio_review: Análise da carteira (alocação, desvios, recomendações)
        - macro_context: Interpretação do cenário macro (Selic, IPCA, câmbio, geopolítica)
        - strategy_signals: Interpretação dos sinais gerados por estratégias
        - news_digest: Síntese e classificação de notícias relevantes
        - risk_alert: Narrativa sobre alertas de risco disparados
        - weekly_newsletter: Composição de newsletter semanal completa
        - fi_projection: Análise da projeção de independência financeira
        - chat_response: Resposta conversacional a perguntas do usuário (Telegram)
        - sector_analysis: Análise setorial aprofundada
    """

# src/carteira_auto/ai/prompts/templates/
# Cada arquivo .py contém system_prompt + user_template para um tipo de análise
# Exemplo: portfolio_review.py, macro_context.py, news_digest.py, etc.
```

**Modelos de output da IA:**

```python
# src/carteira_auto/ai/models.py
class AIAnalysis(BaseModel):
    """Output estruturado de uma análise da IA."""

    analysis_type: str         # "portfolio_review", "macro_context", etc.
    title: str                 # Título da análise
    summary: str               # Resumo executivo (2-3 frases)
    narrative: str             # Análise completa em Markdown
    recommendations: list[AIRecommendation]  # Recomendações acionáveis
    risk_warnings: list[str]   # Alertas de risco identificados
    confidence: float          # 0-1, auto-avaliação da IA
    data_sources: list[str]    # Quais dados alimentaram a análise
    timestamp: datetime
    provider: str              # "claude" ou "deepseek"
    model: str                 # Modelo específico usado
    tokens_used: int           # Para controle de custos

class AIRecommendation(BaseModel):
    """Recomendação acionável gerada pela IA."""

    action: str                # "comprar", "vender", "manter", "monitorar"
    target: str                # Ticker, classe, ou ação genérica
    rationale: str             # Justificativa
    urgency: str               # "imediata", "curto_prazo", "estratégica"
    conditions: list[str]      # Condições para a recomendação valer
```

**Node DAG para IA:**

```python
# src/carteira_auto/core/nodes/ai_nodes.py
class AIAnalysisNode(Node):
    """Executa análise via IA a partir do contexto do pipeline.

    Lê do contexto: qualquer combinação de métricas/sinais/alertas/notícias
    Produz no contexto: "ai_analyses" -> list[AIAnalysis]

    Configurável por análise — pode rodar múltiplas análises em paralelo.
    """

    name = "ai_analysis"
    dependencies = []  # Dinâmico — depende do que estiver disponível no ctx

class TelegramBotNode(Node):
    """Processa mensagens recebidas do Telegram e gera respostas via IA.

    Bidirecional: recebe pergunta → monta contexto → chama IA → responde.
    """

    name = "telegram_bot"
    dependencies = ["ai_analysis"]
```

**Controle de custos:**

```python
# src/carteira_auto/ai/cost_tracker.py
class AICostTracker:
    """Monitora e limita gastos com APIs de IA.

    - Budget mensal configurável (e.g. R$ 50/mês)
    - Routing inteligente: Claude para análises complexas, Deepseek para rotina
    - Cache de análises recentes (evita re-análise de dados inalterados)
    - Relatório de uso por tipo de análise
    """
```

### Camada 8: Multi-Channel Publisher

Sistema de publicação que formata e distribui o conteúdo (tanto quantitativo quanto narrativo da IA) para múltiplos canais de output.

```python
# src/carteira_auto/publishers/base.py
from abc import ABC, abstractmethod

class Publisher(ABC):
    """Interface base para canais de publicação."""

    @abstractmethod
    def publish(self, content: PublishableContent) -> PublishResult: ...

    @abstractmethod
    def format(self, analysis: AIAnalysis, ctx: PipelineContext) -> str: ...

class PublishableContent(BaseModel):
    """Conteúdo formatado para publicação."""

    title: str
    body: str                  # Markdown ou HTML
    attachments: list[Path]    # Gráficos, planilhas
    metadata: dict
    target_channel: str
    priority: str              # "urgent", "normal", "digest"
```

**Canais implementados:**

```python
# 1. Streamlit Dashboard (existente, expandir)
# src/carteira_auto/publishers/streamlit_publisher.py
class StreamlitPublisher(Publisher):
    """Alimenta o dashboard Streamlit com análises da IA.

    - Página de AI Insights: narrativas e recomendações em tempo real
    - Cards de análise por tipo (macro, carteira, setores)
    - Histórico de recomendações com tracking de acerto
    - Chat widget: pergunta ao sistema via interface web
    """

# 2. PDF Reports
# src/carteira_auto/publishers/pdf_publisher.py
class PDFPublisher(Publisher):
    """Gera relatórios profissionais em PDF.

    Tipos:
        - Relatório semanal: resumo de mercado, carteira, recomendações
        - Relatório mensal: análise profunda com gráficos
        - Relatório de estratégia: backtest results + sinais ativos
        - Relatório de projeção FI: cenários de independência financeira

    Usa: reportlab ou weasyprint (HTML → PDF com CSS)
    Inclui: gráficos matplotlib/plotly exportados como imagem
    """

# 3. Email + Newsletter
# src/carteira_auto/publishers/email_publisher.py
class EmailPublisher(Publisher):
    """Envia emails e newsletters.

    Tipos:
        - Alerta urgente: desvio de alocação, queda abrupta, evento geopolítico
        - Newsletter semanal: digest da semana com análise da IA
        - Relatório mensal: PDF em anexo + resumo no corpo

    Infraestrutura: SMTP (Gmail/Outlook) ou SendGrid API
    Templates: HTML responsivo (Jinja2)
    """

# 4. Telegram Bot (bidirecional)
# src/carteira_auto/publishers/telegram_publisher.py
class TelegramPublisher(Publisher):
    """Bot Telegram para alertas e conversa com IA.

    Modos:
        - Push (sistema → usuário): alertas, resumos diários, sinais
        - Pull (usuário → sistema → IA → usuário): perguntas livres

    Comandos:
        /carteira - Resumo da carteira
        /macro - Cenário macro atual
        /sinais - Sinais ativos das estratégias
        /projecao - Projeção de independência financeira
        /pergunta <texto> - Pergunta livre à IA sobre seus investimentos
        /relatorio - Gera e envia relatório PDF

    Infraestrutura: python-telegram-bot + webhook ou polling
    """

# 5. Excel Export (existente, expandir)
# src/carteira_auto/publishers/excel_publisher.py
class ExcelPublisher(Publisher):
    """Exporta dados e análises para planilhas Excel.

    - Planilha da carteira atualizada (existente)
    - Aba de recomendações da IA (NOVA)
    - Aba de histórico de sinais (NOVA)
    - Aba de métricas de risco (NOVA)
    - Aba de projeção FI (NOVA)
    """

# 6. Web Estático (futuro)
# src/carteira_auto/publishers/web_publisher.py
class WebPublisher(Publisher):
    """Gera site estático para visualização da carteira.

    - HTML/CSS/JS estático (GitHub Pages ou similar)
    - Dashboard público (sem dados sensíveis) ou privado (autenticado)
    - Atualização automática via GitHub Actions
    - Visualizações interativas com Plotly.js ou D3.js

    Geração: Jinja2 templates → HTML estático
    Deploy: git push para repo de páginas
    """
```

**ContentRouter — orquestração:**

```python
# src/carteira_auto/publishers/router.py
class ContentRouter:
    """Roteia conteúdo para os canais apropriados baseado em regras.

    Regras:
        - Alertas urgentes → Telegram (imediato) + Email
        - Resumo diário → Telegram (18h, após fechamento B3)
        - Newsletter semanal → Email (domingo) + PDF
        - Relatório mensal → PDF + Email + Excel + Web
        - Resposta a perguntas → Telegram (bidirecional)
        - Atualização de carteira → Excel + Streamlit

    Cada regra define:
        - Trigger: evento, horário, ou manual
        - Canais: lista de publishers
        - Prioridade: urgente, normal, digest
        - Formatação: qual template usar por canal
    """
```

---

## Fases de Implementação

### Progresso Atual (atualizado 2026-03-30)

| Fase | Status | PR | Notas |
|------|--------|----|-------|
| 0 | CONCLUÍDA | #18 | DataLake SQLite (4 sub-lakes), IngestNodes, settings expandido |
| 1 | CONCLUÍDA | #19 | FRED, CVM, Tesouro, DDM fetchers + testes |
| Hardening | CONCLUÍDA | #20 | Result type, validação estrita, error handling, 350 testes |
| 2 Sprint 0 | CONCLUÍDA | — | Validação infraestrutura, correção códigos BCB SGS |
| 2 Sprint 1 | CONCLUÍDA | — | CurrencyAnalyzer, CommodityAnalyzer, FiscalAnalyzer + 33 testes |
| Fetcher Max A | CONCLUÍDA | #34 | Deps (python-bcb, sidrapy, tradingcomdados), constants expandidos, FetchWithFallback, ReferenceLake (12 tab), TradingComDadosConfig |
| Fetcher Max B | CONCLUÍDA | — | BCBFetcher (6 mixins + MercadoImobiliário), IBGEFetcher (+analfabetismo), FREDFetcher (+23 convenience methods), auditoria e 697 testes |
| Fetcher Max C | Pendente | — | Expansão Yahoo, DDM, Tesouro, CVM + TradingComDadosFetcher |
| Fetcher Max D | Pendente | — | IngestNodes com fallback, testes integração, docs |
| 2 Sprint 2+ | Pendente | — | 6 analyzers restantes (fundamental, yield curve, global macro...) |
| 3-7 | Pendente | — | Estratégias, optimizer, backtesting, ML, NLP, AI, publishers |

**Decisões estratégicas tomadas no hardening (PR #20):**
- Result type `Ok[T] | Err[T]` para error handling explícito
- Validação Pydantic estrita: ticker obrigatório, preços >= 0, Literal types
- Per-node error handling no DAGEngine com `fail_fast` flag
- Erros parciais em analyzers via `ctx["_errors"]` (sem silenciar exceções)
- Imutabilidade: `model_copy()` em vez de mutação in-place
- `RISK_FREE_DAILY` e `MIN_TRADE_VALUE` extraídos para settings
- Node.__init_subclass__() para isolar dependencies entre subclasses

**Decisões tomadas no Fetcher Maximization Sprint A (PR #34):**
- python-bcb>=0.3.0, sidrapy>=0.1.0, tradingcomdados>=0.4.0 como dependências
- Constants expandidos: BCB_SERIES_CODES (57 séries), IBGE_TABLE_IDS (17 tabelas), FRED_SERIES (38 séries com metadados), INDEX_CODES (6 índices)
- FetchWithFallback vs @fallback: mecanismos distintos (entre fetchers vs dentro de um fetcher)
- ReferenceLake com 12 tabelas para dados estruturais não-temporais
- TradingComDadosConfig em settings.py (fetcher será implementado no Sprint C)

**Cobertura de testes (407+ passando):**
- test_models.py (54) — Result type, validação Asset/Portfolio, todos os models
- test_analyzers.py (19) — DAGEngine error handling, 7 analyzers com mocks
- test_fetchers.py (17) — Yahoo normalize, preços, histórico
- test_cli.py (15) — parser, comandos, main
- test_decorators.py (20) — todos os decorators
- test_integrations.py (8) — E2E pipeline, dry_run, presets
- test_currency_analyzer.py (9) — CurrencyAnalyzer (PTAX, DXY, carry spread, falhas parciais)
- test_commodity_analyzer.py (8) — CommodityAnalyzer (preços, ciclo, índice, falhas)
- test_fiscal_analyzer.py (16) — FiscalAnalyzer (métricas, trajetória, variação 12m, falhas)
- test_fetch_helpers.py (22) — FetchWithFallback, FetchStrategy, FetchResult
- test_reference_lake.py (39) — ReferenceLake (12 tabelas, CRUD, auditoria)
- test_lake.py, test_cvm_fetcher.py, test_fred_fetcher.py, test_ddm_fetcher.py, test_tesouro_fetcher.py, test_ingest_nodes.py, test_rate_helpers.py (pré-existentes)
- **2 falhas pré-existentes:** CVM 404 (endpoint removido), Excel fixture

---

### Fase 0: Infraestrutura Base (Pré-requisito) — CONCLUÍDA

**Objetivo:** Preparar o terreno para tudo que vem depois.

1. **Data Lake SQLite**
   - Criar `src/carteira_auto/data/lake/` com classes `PriceLake`, `MacroLake`, `FundamentalsLake`, `NewsLake`
   - Schema SQLite para cada tipo de dado
   - API unificada `DataLake` que agrega todas
   - Método `export_to_parquet()` para ML

2. **Refatorar Settings**
   - Adicionar configs para novos fetchers (FRED API key, NewsAPI key, etc.)
   - Mover para `.env` com fallbacks sensatos
   - Adicionar `DataLakeConfig` com paths e TTLs

3. **Nodes de Ingestão**
   - `IngestPricesNode` — Todos os ativos da carteira + benchmarks + commodities
   - `IngestMacroNode` — Todos os indicadores BCB + FRED
   - Pipeline CLI: `carteira run ingest` (execução diária)

4. **Testes unitários base**
   - Fixtures para DataLake (SQLite in-memory)
   - Mocks para fetchers (evitar chamadas reais em testes)

### Fase 1: Fontes de Dados Críticas — CONCLUÍDA

**Objetivo:** Alimentar o data lake com dados suficientes para as primeiras estratégias.

1. **FREDFetcher** (Federal Reserve Economic Data)
   - API key via `.env`
   - Séries: Fed Funds Rate, CPI, GDP, Unemployment, Treasury yields (2y, 5y, 10y, 30y), DXY, VIX
   - Rate limit: 120 req/min (generoso)

2. **CVMFetcher** (Dados Abertos CVM)
   - Sem autenticação
   - Endpoints: demonstrações financeiras trimestrais, dados de FIIs
   - Parser de CSVs da CVM (formato próprio)
   - Foco: DRE, Balanço, DFC das empresas da carteira

3. **TesouroDiretoFetcher**
   - API pública de taxas de títulos
   - Histórico de taxas NTN-B, LFT, NTN-F, LTN
   - Curva de juros implícita

4. **DDMFetcher** (DDM Stock Screening)
   - Dividend Discount Model para valuations
   - Screening de ações por métricas fundamentalistas

5. **Enrichment dos preços**
   - Commodities via Yahoo: `CL=F` (petróleo), `GC=F` (ouro), `SI=F` (prata), `ZS=F` (soja)
   - Índices globais: `^GSPC`, `^IXIC`, `^FTSE`, `^N225`, `^HSI`
   - Cripto: `BTC-USD`, `ETH-USD`

5. **Pipeline de ingestão completa**
   - `carteira run ingest --full` (backfill histórico)
   - `carteira run ingest --daily` (atualização incremental)
   - Cron/scheduler básico (systemd timer ou crontab)

### Fase 2: Analyzers Avançados — EM ANDAMENTO (3 de 9 concluídos)

**Objetivo:** Transformar dados brutos em métricas acionáveis.

1. **FundamentalAnalyzer** — Múltiplos, qualidade, scoring
2. **CurrencyAnalyzer** — Carry trade, PTAX, DXY, real efetivo **(CONCLUÍDO — Sprint 1)**
3. **CommodityAnalyzer** — Ciclo de commodities, termos de troca Brasil **(CONCLUÍDO — Sprint 1)**
4. **YieldCurveAnalyzer** — Curva DI, spreads, sinalização de ciclo
5. **FiscalAnalyzer** — Trajetória de dívida/PIB, resultado primário **(CONCLUÍDO — Sprint 1)**
6. **GlobalMacroAnalyzer** — Diferencial de juros, ciclo global, PMI
7. **CorrelationAnalyzer** — Matriz de correlação rolling, regime shifts
8. **DividendAnalyzer** — DY, payout, sustentabilidade, crescimento
9. **PersonalFinanceAnalyzer** — Integração com gastos.xlsx

### Fase 3: Framework de Estratégias + Otimização + Backtesting — ~4 semanas

**Objetivo:** Criar a infraestrutura para testar, combinar e otimizar estratégias.

1. **Strategy base class**, `Signal` model, `CompositeStrategy`
2. **StrategyEngine** — converte estratégia (base ou composta) em pipeline DAG
3. **PortfolioOptimizer com PyPortfolioOpt:**
   - `OptimizationConfig` com todos os enums (objectives, risk models, return models)
   - Covariância: Ledoit-Wolf, Oracle Approx, Exp-weighted, Denoised (RMT), Hybrid-ML
   - Retornos: Mean, EMA, CAPM, Black-Litterman com views das estratégias
   - Constraints brasileiras: lotes B3, setores, turnover L2, impostos
   - Alocação discreta via `DiscreteAllocation`
   - Fronteira eficiente para visualização
4. **BacktestEngine** — motor de backtesting com walk-forward
5. **Três estratégias base prioritárias:**
   - `ValueInvesting` — scoring fundamentalista (produz views de BL)
   - `MacroTactical` — alocação tática por ciclo (produz views de BL)
   - `EmancipationPath` — projeção de independência financeira
6. **Uma estratégia composta:**
   - `TacticalValue` — Layered: MacroTactical → classe, ValueInvesting → ativo
7. **Pipeline completo:** estratégia → sinais + views → optimizer → alocação ótima → backtest
8. **CLI:** `carteira optimize --strategy tactical_value --objective max_sharpe`
9. **CLI:** `carteira backtest <strategy> --start 2020-01-01 --end 2025-12-31`

### Fase 4: ML Pipeline + Integração com Optimizer — ~3 semanas

**Objetivo:** Adicionar inteligência preditiva e conectar ML ao optimizer.

1. **Feature Engineering**
   - Pipeline de features a partir do DataLake
   - Exportação para Parquet otimizado
   - Feature store com versionamento

2. **FundamentalScorer (XGBoost + RF)**
   - Treino em dados CVM históricos
   - Walk-forward validation
   - SHAP para interpretabilidade
   - Produz views quantificadas para Black-Litterman (`get_views()`)
   - Feature importance calibra confidências (`get_view_confidences()`)

3. **Integração ML → Optimizer**
   - `ReturnModelType.ML_PREDICTED`: scorer produz mu (retornos esperados)
   - `RiskModelType.HYBRID_ML`: regime detection via vol → blend de covariâncias
   - Covariância denoised (Random Matrix Theory) como default para ML
   - Walk-forward validation do pipeline completo (ML → optimizer → backtest)

4. **Dependências ML:** `scikit-learn`, `xgboost`, `shap`, `arch` (GARCH), `pyportfolioopt`

### Fase 5: NLP + Sentimento — ~2 semanas

**Objetivo:** Quantificar o sentiment de mercado e geopolítica.

1. **NewsApiFetcher + RSSFetcher**
2. **NewsSentimentAnalyzer** — FinBERT ou multilingual transformer
3. **GeopoliticalAnalyzer** — Score de risco geopolítico
4. **SentimentAnalyzer node** — Integração no DAG
5. **Estratégia CrisisHedge** — Usa sentimento como gatilho
6. **Dependências:** `transformers`, `torch` (ou `onnxruntime` para inferência leve)

### Fase 6: AI Reasoning Layer — ~2 semanas

**Objetivo:** Adicionar camada de raciocínio artificial que interpreta e narra.

1. **AI Provider abstraction**
   - `AIProvider` ABC com `complete()` e `complete_structured()`
   - `ClaudeProvider` (Anthropic API — análise profunda)
   - `DeepseekProvider` (fallback de custo baixo)
   - Config no `.env`: API keys, model selection, budget mensal

2. **PromptEngine + templates**
   - Template por tipo de análise (portfolio_review, macro_context, news_digest, etc.)
   - System prompts com a lente materialista-dialética
   - Structured outputs via Pydantic (AIAnalysis, AIRecommendation)
   - Routing inteligente: Claude para complexo, Deepseek para rotina

3. **AIAnalysisNode no DAG**
   - Lê contexto completo (métricas + sinais + alertas + notícias)
   - Produz `ctx["ai_analyses"]` → list[AIAnalysis]
   - Pipeline: `carteira run ai-review`

4. **AICostTracker**
   - Budget mensal configurável
   - Cache de análises recentes
   - Relatório de uso por tipo

### Fase 7: Multi-Channel Publisher + Telegram Bot — ~3 semanas

**Objetivo:** Distribuir conteúdo inteligente para todos os canais.

1. **Publisher base + ContentRouter**
   - Interface `Publisher` com `publish()` + `format()`
   - `ContentRouter` com regras de roteamento por tipo/prioridade

2. **TelegramPublisher (bidirecional) — PRIORIDADE**
   - Bot com comandos (/carteira, /macro, /sinais, /pergunta)
   - Push: alertas urgentes, resumo diário
   - Pull: perguntas livres → AI → resposta
   - Infraestrutura: `python-telegram-bot`

3. **PDFPublisher**
   - Relatório semanal e mensal com gráficos
   - Templates via `weasyprint` (HTML → PDF)
   - Gráficos matplotlib/plotly exportados como imagem

4. **EmailPublisher**
   - Newsletter semanal (HTML responsivo, Jinja2)
   - Alertas urgentes
   - SMTP ou SendGrid

5. **Dashboard Streamlit expandido**
   - Página de AI Insights (narrativas + recomendações)
   - Página de estratégias (sinais ativos, backtest results)
   - Página de projeção FI (Monte Carlo, crossover point)
   - Chat widget: pergunta ao sistema

6. **ExcelPublisher expandido**
   - Abas de recomendações IA, sinais, métricas, projeção FI

7. **WebPublisher (futuro)**
   - Site estático com Jinja2 → GitHub Pages
   - Visualizações Plotly.js

8. **Scheduler completo**
   - `carteira schedule start` — APScheduler
   - Ingestão diária (18h), AI review diária, newsletter domingo, relatório mensal

---

## Estrutura de Diretórios — Estado Final

```
carteira_auto/
├── src/carteira_auto/
│   ├── __init__.py
│   ├── analyzers/                  # (expandido)
│   │   ├── __init__.py
│   │   ├── portfolio_analyzer.py   # (existente)
│   │   ├── risk_analyzer.py        # (existente)
│   │   ├── macro_analyzer.py       # (existente, refatorar)
│   │   ├── market_analyzer.py      # (existente)
│   │   ├── market_sector_analyzer.py   # (existente)
│   │   ├── economic_sector_analyzer.py # (existente)
│   │   ├── rebalancer.py           # (existente)
│   │   ├── currency_analyzer.py    # (existente — Sprint 1)
│   │   ├── commodity_analyzer.py   # (existente — Sprint 1)
│   │   ├── fiscal_analyzer.py      # (existente — Sprint 1)
│   │   ├── fundamental_analyzer.py # NOVO
│   │   ├── yield_curve_analyzer.py # NOVO
│   │   ├── global_macro_analyzer.py # NOVO
│   │   ├── correlation_analyzer.py # NOVO
│   │   ├── dividend_analyzer.py    # NOVO
│   │   ├── sentiment_analyzer.py   # NOVO (Fase 5)
│   │   ├── geopolitical_analyzer.py # NOVO (Fase 5)
│   │   └── personal_finance_analyzer.py # NOVO
│   ├── alerts/                     # (existente, manter)
│   ├── cli/                        # (expandir comandos)
│   ├── config/                     # (expandir settings)
│   │   ├── __init__.py
│   │   ├── settings.py             # (existente, expandir)
│   │   ├── constants.py            # (existente)
│   │   └── optimization.py         # NOVO — OptimizationConfig + enums
│   ├── core/
│   │   ├── engine.py               # (existente, manter)
│   │   ├── models/                 # (expandir com novos modelos)
│   │   ├── nodes/                  # (expandir com ingest, strategy, optimizer nodes)
│   │   │   ├── __init__.py
│   │   │   ├── portfolio_nodes.py  # (existente)
│   │   │   ├── alert_nodes.py      # (existente)
│   │   │   ├── storage_nodes.py    # (existente)
│   │   │   ├── ingest_nodes.py     # (existente) — IngestPricesNode, IngestMacroNode, IngestFundamentalsNode
│   │   │   ├── fetch_helpers.py    # (existente) — FetchWithFallback, FetchStrategy, FetchResult
│   │   │   ├── strategy_nodes.py   # NOVO — StrategyNode (ponte Strategy↔DAG)
│   │   │   ├── optimizer_nodes.py  # NOVO — OptimizePortfolioNode
│   │   │   ├── ai_nodes.py         # NOVO — AIAnalysisNode
│   │   │   └── publish_nodes.py    # NOVO — PublishNode
│   │   ├── pipelines/              # (existente, backward compat)
│   │   └── registry.py             # (expandir com novas pipelines)
│   ├── data/
│   │   ├── fetchers/               # (expandido)
│   │   │   ├── __init__.py
│   │   │   ├── yahoo_fetcher.py    # (existente)
│   │   │   ├── bcb/                # (módulo com 6 mixins: SGS, Focus, PTAX, TaxaJuros, MercadoImobiliário, Base)
│   │   │   ├── ibge_fetcher.py     # (existente)
│   │   │   ├── fred_fetcher.py     # (existente — Fase 1)
│   │   │   ├── cvm_fetcher.py      # (existente — Fase 1)
│   │   │   ├── tesouro_fetcher.py  # (existente — Fase 1)
│   │   │   ├── ddm_fetcher.py      # (existente — Fase 1)
│   │   │   ├── tradingcomdados_fetcher.py # NOVO (Sprint C)
│   │   │   ├── news_fetcher.py     # NOVO (Fase 5)
│   │   │   ├── rss_fetcher.py      # NOVO (Fase 5)
│   │   │   └── coingecko_fetcher.py # NOVO
│   │   ├── lake/                   # (existente — Fase 0 + Fetcher Sprint A)
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # (existente) DataLake facade
│   │   │   ├── price_lake.py       # (existente) Preços OHLCV
│   │   │   ├── macro_lake.py       # (existente) Indicadores macro
│   │   │   ├── fundamentals_lake.py # (existente) Dados fundamentalistas
│   │   │   ├── news_lake.py        # (existente) Headlines + sentimento
│   │   │   └── reference_lake.py   # (existente) ReferenceLake — 12 tabelas de referência
│   │   ├── loaders/                # (existente)
│   │   ├── exporters/              # (existente)
│   │   └── storage/                # (existente — snapshots)
│   ├── strategies/                 # NOVO — Framework de Estratégias
│   │   ├── __init__.py
│   │   ├── base.py                 # Strategy ABC, Signal model
│   │   ├── composite.py            # CompositeStrategy, Layer, LayerGate, WeightedBlend
│   │   ├── registry.py             # StrategyEngine
│   │   ├── value_investing.py      # Estratégia value (base)
│   │   ├── macro_tactical.py       # Alocação top-down (base)
│   │   ├── momentum_rotation.py    # Rotação setorial (base)
│   │   ├── risk_parity.py          # Paridade de risco (base)
│   │   ├── income_optimizer.py     # Maximização de renda (base)
│   │   ├── crisis_hedge.py         # Hedge geopolítico (base)
│   │   ├── ml_scoring.py           # Scoring via ML (base)
│   │   ├── emancipation_path.py    # Projeção FI (base)
│   │   └── presets.py              # Compostas pré-configuradas (TacticalValue, etc.)
│   ├── optimization/               # NOVO — Portfolio Optimizer (PyPortfolioOpt)
│   │   ├── __init__.py
│   │   ├── optimizer.py            # PortfolioOptimizer principal
│   │   ├── risk_models.py          # Hybrid ML cov, denoised cov, regime detection
│   │   ├── return_models.py        # BL returns, ML predicted returns
│   │   ├── constraints.py          # Constraints brasileiras (setores, lotes, impostos)
│   │   └── frontier.py             # Efficient frontier computation + visualização
│   ├── backtesting/                # NOVO — Motor de Backtesting
│   │   ├── __init__.py
│   │   ├── engine.py               # BacktestEngine
│   │   ├── metrics.py              # Métricas de performance
│   │   ├── simulator.py            # Simulador de portfólio
│   │   └── tax_calculator.py       # Impostos BR (ações, FIIs, RF)
│   ├── ml/                         # NOVO — Machine Learning
│   │   ├── __init__.py
│   │   ├── features/
│   │   │   ├── __init__.py
│   │   │   ├── feature_store.py    # Feature store com versionamento
│   │   │   ├── fundamental_features.py
│   │   │   ├── technical_features.py
│   │   │   └── macro_features.py
│   │   ├── scoring/
│   │   │   ├── __init__.py
│   │   │   └── fundamental_scorer.py  # XGBoost + RF
│   │   ├── nlp/
│   │   │   ├── __init__.py
│   │   │   └── sentiment_analyzer.py  # FinBERT
│   │   └── timeseries/
│   │       ├── __init__.py
│   │       └── forecaster.py          # ARIMA/GARCH/Prophet
│   ├── personal/                   # NOVO — Finanças Pessoais
│   │   ├── __init__.py
│   │   ├── finance_tracker.py      # Integração gastos.xlsx
│   │   ├── fi_projector.py         # Projeção de independência financeira
│   │   └── tax_optimizer.py        # Otimização tributária BR
│   ├── ai/                         # NOVO — AI Reasoning Layer
│   │   ├── __init__.py
│   │   ├── providers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # AIProvider ABC
│   │   │   ├── claude_provider.py  # Anthropic Claude API
│   │   │   └── deepseek_provider.py # Deepseek API (fallback)
│   │   ├── prompts/
│   │   │   ├── __init__.py
│   │   │   ├── engine.py           # PromptEngine (templates + routing)
│   │   │   └── templates/          # Um .py por tipo de análise
│   │   │       ├── portfolio_review.py
│   │   │       ├── macro_context.py
│   │   │       ├── strategy_signals.py
│   │   │       ├── news_digest.py
│   │   │       ├── risk_alert.py
│   │   │       ├── weekly_newsletter.py
│   │   │       ├── fi_projection.py
│   │   │       └── chat_response.py
│   │   ├── models.py              # AIAnalysis, AIRecommendation
│   │   └── cost_tracker.py        # Controle de budget mensal
│   ├── publishers/                 # NOVO — Multi-Channel Output
│   │   ├── __init__.py
│   │   ├── base.py                # Publisher ABC, PublishableContent
│   │   ├── router.py              # ContentRouter (orquestração)
│   │   ├── streamlit_publisher.py # Dashboard expandido
│   │   ├── pdf_publisher.py       # Relatórios PDF
│   │   ├── email_publisher.py     # Newsletters + alertas
│   │   ├── telegram_publisher.py  # Bot bidirecional
│   │   ├── excel_publisher.py     # Planilhas expandidas
│   │   ├── web_publisher.py       # Site estático (futuro)
│   │   └── templates/             # Jinja2 templates por canal
│   │       ├── email/
│   │       ├── pdf/
│   │       └── web/
│   └── utils/                      # (existente, expandir)
│       ├── __init__.py
│       ├── logger.py               # (existente)
│       ├── decorators.py           # (existente)
│       └── helpers.py              # (existente)
├── dashboards/                     # (expandir páginas)
├── tests/                          # NOVO — Testes estruturados
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── data/
│   ├── lake/                       # NOVO
│   ├── raw/
│   ├── processed/
│   └── outputs/
└── pyproject.toml                  # (atualizar deps)
```

---

## Novas Dependências (pyproject.toml)

```toml
[project]
dependencies = [
    # === Existentes ===
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    "requests>=2.31.0",
    "yfinance>=0.2.28",
    "openpyxl>=3.1.0",
    "python-dotenv>=1.0.0",
    "rich>=13.0.0",
    "pydantic>=2.0.0",
    "streamlit>=1.28.0",
    "plotly>=5.17.0",
    "scipy>=1.11.0",
    "psutil>=5.9.0",
    "python-dateutil>=2.8.0",
    # === Novas — Core ===
    "fredapi>=0.5.0",          # FRED API client
    "feedparser>=6.0.0",       # RSS parsing
    "beautifulsoup4>=4.12.0",  # Web scraping (CVM, ANBIMA)
    "lxml>=4.9.0",             # XML parsing rápido
    "apscheduler>=3.10.0",     # Scheduler para automação
    "pyarrow>=14.0.0",         # Parquet I/O
    # === Novas — ML ===
    "scikit-learn>=1.3.0",     # ML base
    "xgboost>=2.0.0",          # Gradient boosting
    "shap>=0.43.0",            # Interpretabilidade
    "cvxpy>=1.4.0",            # Otimização convexa (fallback)
    "arch>=6.2.0",             # GARCH models
    "pyportfolioopt>=1.5.5",   # Portfolio optimization (Markowitz, BL, HRP, CLA)
    # === Novas — AI Reasoning ===
    "anthropic>=0.40.0",       # Claude API client
    "openai>=1.50.0",          # Deepseek API (compatível OpenAI)
    "tiktoken>=0.7.0",         # Contagem de tokens (controle de custo)
    "httpx>=0.27.0",           # HTTP async para providers
    # === Novas — Publishers ===
    "python-telegram-bot>=21.0",  # Telegram bot
    "weasyprint>=62.0",        # HTML → PDF
    "jinja2>=3.1.0",           # Templates (email, PDF, web)
    "matplotlib>=3.8.0",       # Gráficos para relatórios
    "aiosmtplib>=3.0.0",       # Email async
]

[project.optional-dependencies]
nlp = [
    "transformers>=4.35.0",    # FinBERT
    "torch>=2.1.0",            # Backend para transformers
    "sentencepiece>=0.1.99",   # Tokenizer
]
web = [
    "fastapi>=0.110.0",        # API para web publisher (futuro)
    "uvicorn>=0.27.0",         # ASGI server
]
```

---

## Regras de Design para Claude Code

### Princípios Invioláveis

1. **Cada node faz UMA coisa** — Single Responsibility. Se um node busca dados E calcula métricas, deve ser dividido.
2. **Nodes comunicam via PipelineContext** — Nunca por estado global ou imports circulares.
3. **Fetchers nunca calculam** — Apenas buscam e normalizam dados brutos.
4. **Analyzers não persistem** — Apenas leem do contexto e produzem métricas.
5. **Estratégias são stateless** — Toda informação vem do contexto.
6. **DataLake é a single source of truth** — Fetchers gravam no lake; analyzers leem do lake.
7. **Backward compatibility** — Pipelines existentes (`update-excel-portfolio-prices`, `analyze`, etc.) devem continuar funcionando.
8. **Type hints em tudo** — Pydantic para modelos, typing para funções.
9. **Testes para cada componente** — Mínimo: unit test para cada analyzer e strategy.
10. **Logs estruturados** — Usar o sistema de logging existente em todo código novo.
11. **AI providers são intercambiáveis** — Toda chamada passa pelo `PromptEngine`, nunca diretamente ao provider. Trocar Claude por Deepseek (ou outro) deve ser uma mudança de config, não de código.
12. **Prompts são versionados** — Cada template de prompt é um arquivo Python com constantes. Mudanças em prompts são rastreáveis via git.
13. **AI nunca executa** — A IA analisa, narra e recomenda. Nunca dispara compra/venda/transferência. Toda ação é humana.
14. **Publishers são independentes** — Falha num canal (e.g. Telegram offline) não impede publicação nos demais. `ContentRouter` trata erros por canal.
15. **Custos de IA são rastreados** — Todo call à API registra tokens usados. Budget mensal é hard limit, não sugestão.
16. **Conteúdo da IA é sempre atribuído** — Todo output indica qual modelo gerou, com qual prompt, e quais dados alimentaram. Transparência total.

### Padrões de Código

```python
# Padrão para novos analyzers:
class NovoAnalyzer(Node):
    """Docstring: o que faz, o que lê, o que produz."""

    name = "nome_unico"
    dependencies = ["nodes_que_precisa"]

    @log_execution
    def run(self, ctx: PipelineContext) -> PipelineContext:
        # 1. Ler inputs do contexto
        # 2. Buscar dados do DataLake se necessário
        # 3. Calcular métricas
        # 4. Gravar resultado no contexto
        # 5. Logar resumo
        return ctx

# Padrão para novos fetchers:
class NovoFetcher:
    """Docstring: fonte, autenticação, rate limits."""

    def __init__(self):
        self._config = settings.novo  # Config do settings.py

    @retry(max_attempts=3)
    @rate_limit(calls_per_minute=60)
    @cache_result(ttl_seconds=3600)
    @log_execution
    def get_dados(self, params) -> pd.DataFrame:
        # Buscar, normalizar, retornar DataFrame padronizado
        pass

# Padrão para estratégias:
class NovaStrategy(Strategy):
    name = "nome_estrategia"
    description = "O que faz e por quê"
    timeframe = "medium"
    required_analyzers = ["analyzer1", "analyzer2"]

    def evaluate(self, ctx: PipelineContext) -> StrategyResult:
        # 1. Ler métricas dos analyzers via ctx
        data = ctx["analyzer1_output"]
        # 2. Aplicar lógica decisória
        # 3. Retornar sinais + views unificados
        return StrategyResult(
            signals=[Signal(ticker="X", action="buy", strength=0.8, ...)],
            views={"X": 0.15},        # Retorno esperado para BL
            confidences={"X": 0.7},   # Confiança na view
        )

    def backtest_params(self) -> dict:
        return {"rebalance_freq": "monthly", "lookback": 252}

# Padrão para prompts de IA:
# src/carteira_auto/ai/prompts/templates/portfolio_review.py
SYSTEM_PROMPT = """Você é um analista de investimentos que opera sob a lente do
materialismo histórico-dialético. Analise os dados quantitativos fornecidos
identificando contradições, tendências estruturais e oportunidades que o
capital financeirizado cria para o investidor pessoa física.
Seja direto, factual e acionável. Nunca invente dados."""

USER_TEMPLATE = """Analise o estado atual da carteira:
- Patrimônio: R$ {total_value:,.2f}
- Retorno total: {total_return_pct:.2%}
- Alocação: {allocations_summary}
- Sinais ativos: {signals_summary}
- Contexto macro: Selic {selic}%, IPCA {ipca}%, Câmbio R$ {cambio}
- Alertas: {alerts_summary}

Produza: resumo executivo, 3 recomendações acionáveis, riscos identificados."""

RESPONSE_MODEL = AIAnalysis  # Structured output via Pydantic
PROVIDER = "claude"  # Análise complexa → Claude
MAX_TOKENS = 2000

# Padrão para publishers:
class NovoPublisher(Publisher):
    """Docstring: canal, formato, frequência."""

    def format(self, analysis: AIAnalysis, ctx: PipelineContext) -> str:
        # Converter AIAnalysis para o formato do canal (HTML, Markdown, texto)
        pass

    def publish(self, content: PublishableContent) -> PublishResult:
        # Enviar pelo canal (SMTP, Telegram API, filesystem, etc.)
        pass

# Padrão para AI provider:
class NovoProvider(AIProvider):
    """Docstring: API, modelo, limites, custo."""

    async def complete(self, prompt: str, system: str, **kwargs) -> str:
        # Chamar API, retornar texto
        pass

    async def complete_structured(self, prompt: str, system: str,
                                   response_model: type[BaseModel]) -> BaseModel:
        # Chamar API com structured output, retornar modelo Pydantic
        pass
```

---

## Cronograma Resumido

| Fase | Escopo | Duração | Entregáveis |
|------|--------|---------|-------------|
| **0** | Infra (DataLake, refactor settings, ingest nodes) | 1 sem | DataLake funcional, `carteira run ingest` |
| **1** | Fontes (FRED, CVM, Tesouro, commodities, crypto) | 2 sem | 7+ fetchers, lake populado |
| **2** | Analyzers (11 novos) | 2 sem | Métricas abrangentes no contexto |
| **3** | Estratégias + Optimizer (PyPortfolioOpt) + Backtesting | 4 sem | Compostas, BL, HRP, backtest engine |
| **4** | ML (scoring → views → optimizer integration) | 3 sem | Scorer treinado, ML↔optimizer conectados |
| **5** | NLP + Sentimento | 2 sem | Sentiment scoring, crisis hedge |
| **6** | AI Reasoning Layer | 2 sem | Claude/Deepseek integration, prompts, AIAnalysis |
| **7** | Multi-Channel Publisher + Telegram | 3 sem | 6 canais, bot Telegram, scheduler |

**Total estimado: ~19 semanas de desenvolvimento iterativo.**

---

## Decisões Consolidadas

1. **Banco de dados: SQLite agora, migrar se necessário.** O volume esperado (~50 ativos × 10 anos × 252 dias = ~126k linhas de preços) cabe confortavelmente. Se escalar para screening amplo do mercado BR (~400+ ativos), avaliamos migração para PostgreSQL. Design com abstração `DataLake` garante que a camada de storage é substituível.

2. **Execução de ordens: Apenas sinais e recomendações.** O sistema não integrará com APIs de corretora. Toda decisão de execução permanece humana. Isso elimina risco de execução automática sem supervisão e mantém o investidor no controle. Futuramente, se desejado, a interface `Signal` já suporta extensão para execução semi-automática.

3. **Estratégias prioritárias na Fase 3: ValueInvesting + MacroTactical + EmancipationPath.** ValueInvesting é a estratégia-âncora (scoring fundamentalista alimentado pelo ML scorer). MacroTactical é essencial para alocação tática entre classes (o cenário macro atual de juros altos + guerra no Irã + eleições 2026 exige gestão ativa de classes). EmancipationPath projeta a independência financeira — é o norte de todo o sistema. IncomeOptimizer e as demais entram na Fase 4+.

4. **Horizonte de dados: Máximo disponível por fonte, segmentado por estratégia.** Estratégias de longo prazo (ValueInvesting, EmancipationPath) consomem 10+ anos. Macro/tático usa 3-5 anos. Momentum usa 1-2 anos. O DataLake armazena tudo; cada estratégia define seu lookback.

5. **Fontes de dados: Todas as principais identificadas.** FRED (gratuita, API key), CVM (gratuita, sem auth), NewsAPI (gratuita até 100 req/dia), CoinGecko (gratuita). Nenhuma API paga necessária neste estágio.

6. **ML para sentimento: FinBERT (inglês) + multilingual com fallback.** Headlines internacionais (Reuters, Bloomberg) vão ao FinBERT; notícias brasileiras (Valor, Folha) ao modelo multilingual. Decisão de implementação adiada para Fase 5.

## Perguntas Residuais (para decidir durante implementação)

1. **Modelo de ML para sentimento:** FinBERT (inglês, melhor para finanças) vs. modelo multilingual (aceita português)? Ou ambos com fallback? (Decisão na Fase 5)

2. **Granularidade do scheduler:** Ingestão diária é suficiente ou queremos intraday para alguns dados (preços, notícias)?

3. **Dashboard vs CLI:** O dashboard Streamlit deve ser a interface principal ou o CLI continua como padrão com dashboard como complemento visual?

4. **Budget mensal de IA:** Qual limite aceitável para APIs de IA? (Estimativa: Claude Sonnet ~$3/1M tokens input, ~$15/1M output. Uma análise diária completa consome ~5K tokens input + ~2K output ≈ $0.045/dia ≈ $1.35/mês. Newsletter semanal + chat ad-hoc: ~$3-5/mês total.)

5. **Telegram bot token:** Criar via @BotFather antes da Fase 7.

---

## Template .env (todas as API keys necessárias)

```bash
# === Ambiente ===
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

# === APIs de Dados (gratuitas) ===
FRED_API_KEY=your_fred_key_here          # https://fred.stlouisfed.org/docs/api/api_key.html
NEWSAPI_KEY=your_newsapi_key_here        # https://newsapi.org/register
COINGECKO_API_KEY=                       # Opcional (tier gratuito sem key)
DADOS_MERCADO_API_KEY=                   # https://dadosdemercado.com.br

# === APIs de IA ===
ANTHROPIC_API_KEY=your_claude_key_here   # https://console.anthropic.com/
DEEPSEEK_API_KEY=your_deepseek_key_here  # https://platform.deepseek.com/
AI_MONTHLY_BUDGET_USD=10.00              # Hard limit mensal em USD
AI_DEFAULT_PROVIDER=claude               # "claude" ou "deepseek"
AI_CLAUDE_MODEL=claude-sonnet-4-20250514
AI_DEEPSEEK_MODEL=deepseek-chat

# === Publishers ===
TELEGRAM_BOT_TOKEN=your_telegram_token   # Via @BotFather
TELEGRAM_CHAT_ID=your_chat_id           # Seu chat ID pessoal
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password          # App password, não senha normal
EMAIL_RECIPIENT=your_email@gmail.com

# === Paths (opcionais — defaults em settings.py) ===
# PORTFOLIO_FILE=data/raw/Carteira 2026.xlsx
# LAKE_DIR=data/lake
```

---

## Prompt para Claude Code — Planejamento e Implementação por Sprints

O texto abaixo é o prompt completo a ser alimentado ao Claude Code. Ele deve ser salvo como `CLAUDE.md` na raiz do repositório (o Claude Code lê este arquivo automaticamente como instrução persistente). O plano de implementação (`plano_implementacao_carteira_auto.md`) deve estar acessível no repositório (recomenda-se `docs/plano_implementacao_carteira_auto.md`).

````markdown
# CLAUDE.md — Governança de Desenvolvimento do carteira_auto

## Seu papel

Você é o co-desenvolvedor do sistema `carteira_auto` — um sistema de automação
de carteira de investimentos para emancipação financeira de pessoa física no Brasil.
Seu parceiro humano é um programador Python com foco em finanças, economia e
geopolítica. Vocês trabalharão juntos em sprints iterativos.

## Documentos de referência

- **Plano de implementação**: `docs/plano_implementacao_carteira_auto.md`
  Este é o source of truth arquitetural. Contém 8 camadas, 8 fases, modelos de
  código, regras de design e decisões consolidadas. LEIA-O INTEGRALMENTE antes de
  qualquer sprint. Sempre consulte-o ao tomar decisões de design.

- **Código existente**: `src/carteira_auto/`
  O repositório já tem código funcional (v0.1.0). Respeite e reaproveite tudo
  que já existe — nunca reescreva o que funciona.

## Protocolo de sprints

O desenvolvimento segue 8 fases (0 a 7). Cada fase será dividida em sprints
de escopo gerenciável. Para CADA sprint, siga este protocolo rigorosamente:

### 1. Planejamento do sprint (ANTES de escrever código)

Ao iniciar cada nova fase ou sprint, faça o seguinte:

a) **Leia o plano** — releia a seção da fase atual no plano de implementação.

b) **Audite o estado atual** — examine o código existente relevante para a fase.
   Use `find`, `grep`, `cat` para entender o que já existe, quais patterns são
   usados, quais imports estão disponíveis, e como os módulos se conectam.

c) **Proponha o sprint** — apresente ao humano:
   - Título e objetivo do sprint (1 frase)
   - Lista de entregáveis concretos (arquivos a criar/modificar)
   - Dependências de sprints anteriores
   - Riscos ou dúvidas que precisam de decisão humana

d) **Faça perguntas** — ANTES de implementar, levante:
   - Ambiguidades no plano que precisam de clarificação
   - Trade-offs de design que o humano deve decidir
   - Prioridades quando há mais trabalho do que cabe no sprint
   - Dúvidas sobre o domínio (finanças, APIs, regulação BR)
   - Impactos em fases futuras que podem ser antecipados agora

   NÃO prossiga sem respostas para perguntas críticas. É melhor perguntar do
   que assumir errado e reescrever depois.

e) **Aguarde aprovação** — só comece a implementar após o humano aprovar o
   escopo do sprint.

### 2. Implementação (durante o sprint)

a) **Incremental** — implemente arquivo por arquivo, não tudo de uma vez.
   Após cada arquivo significativo, mostre o que foi feito e pergunte se
   o humano quer revisar antes de prosseguir.

b) **Testes junto com código** — para cada módulo novo, escreva o teste
   correspondente no mesmo sprint. Não acumule testes para "depois".

c) **Rode os testes** — execute `pytest` após cada módulo para garantir
   que nada quebrou. Se um teste falhar, corrija antes de seguir.

d) **Commit semântico** — sugira mensagens de commit claras ao final
   de cada unidade lógica de trabalho (ex: "feat(lake): add PriceLake
   with SQLite backend").

### 3. Revisão do sprint (APÓS implementar)

Ao concluir cada sprint, conduza uma revisão estruturada:

a) **Resumo do que foi feito** — liste os arquivos criados/modificados,
   com 1 frase sobre o que cada um faz.

b) **Status dos testes** — quantos passaram, quantos falharam, cobertura.

c) **Checklist de qualidade**:
   - [ ] Type hints em todas as funções e métodos
   - [ ] Docstrings no padrão do projeto (o que faz, lê, produz)
   - [ ] Decorators aplicados onde apropriado (@log_execution, @retry, etc.)
   - [ ] Logger via get_logger(__name__) em todos os módulos
   - [ ] Backward compatibility verificada (pipelines existentes rodam)
   - [ ] Nenhum import circular introduzido
   - [ ] Configs adicionadas em settings.py / constants.py / optimization.py

d) **Perguntas de revisão** — faça perguntas ao humano sobre:
   - Satisfação com a implementação
   - Ajustes necessários antes de avançar
   - Mudanças de prioridade para o próximo sprint
   - Lições aprendidas que afetam fases futuras
   - Se o plano de implementação precisa ser atualizado

e) **Transição** — após aprovação, apresente o planejamento do próximo sprint.

## Infraestrutura existente — USE E REAPROVEITE

O repositório já contém componentes maduros. NÃO reimplemente nada
disto — estenda, integre, importe:

### Config (src/carteira_auto/config/)
- `settings.py`: Settings dataclass com PathsConfig, YahooFetcherConfig,
  BCBConfig, IBGEConfig, DDMConfig, PortfolioConfig, LoggingConfig.
  → ADICIONE novas configs aqui (DataLakeConfig, FREDConfig, AIConfig, etc.)
  → OptimizationConfig vai em config/optimization.py (novo arquivo)
- `constants.py`: Constants class com colunas de planilha, field maps, séries BCB,
  tabelas IBGE, padrões de ticker, horários de mercado, feriados B3.
  → ADICIONE novas constantes aqui (séries FRED, endpoints CVM, etc.)

### Utils (src/carteira_auto/utils/)
- `decorators.py`: @timer, @retry, @rate_limit, @timeout, @fallback,
  @validate_tickers, @validate_positive_value, @validate_allocation_sum,
  @log_execution, @cache_result, @cache_by_ticker.
  → USE estes decorators em todo código novo de fetchers e analyzers.
- `logger.py`: setup_logging(), get_logger(name), RichHandler, RotatingFileHandler.
  → USE get_logger(__name__) em todo módulo novo.
- `helpers.py`: validate_ticker() e outras utilidades.
  → ADICIONE novas helpers aqui se forem genéricas.

### Core (src/carteira_auto/core/)
- `engine.py`: DAGEngine, Node ABC, PipelineContext.
  → NÃO altere. Todos os novos componentes se plugam via Node.
  → Strategy NÃO é um Node. StrategyNode(Node) é a ponte.
- `models/`: Asset, Portfolio, SoldAsset, PortfolioMetrics, RiskMetrics,
  MacroContext, MarketMetrics, RebalanceRecommendation, modelos econômicos.
  → ADICIONE novos Pydantic models aqui (Signal, StrategyResult, AIAnalysis, etc.)
- `registry.py`: PIPELINE_PRESETS, create_engine(), StrategyEngine futuro.
  → EXPANDA com novos pipelines. NÃO remova os existentes.
- `nodes/`: LoadPortfolioNode, FetchPricesNode, ExportPortfolioPricesNode, etc.
  → ADICIONE novos nodes aqui (ingest, strategy, optimizer, ai, publish).

### Data (src/carteira_auto/data/)
- `fetchers/`: YahooFinanceFetcher (completo com batch, paralelo, cache),
  BCBFetcher (SGS API), IBGEFetcher (SIDRA).
  → NÃO altere. ADICIONE novos fetchers no mesmo padrão.
- `loaders/`: ExcelLoader, PortfolioLoader.
- `exporters/`: ExcelExporter, PortfolioPriceExporter.
- `storage/`: SnapshotStore (JSON).

### Alerts (src/carteira_auto/alerts/)
- AlertEngine, AlertRule, Alert, ConsoleChannel, LogChannel.
  → ADICIONE novos channels (TelegramChannel, EmailChannel) seguindo AlertChannel ABC.

### Analyzers (src/carteira_auto/analyzers/)
- PortfolioAnalyzer, RiskAnalyzer, MacroAnalyzer, MarketAnalyzer,
  Rebalancer, MarketSectorAnalyzer, EconomicSectorAnalyzer.
  → ADICIONE novos analyzers no mesmo padrão (Node subclass com run(ctx)).

### Dashboard (dashboards/)
- app.py + pages/ (visão geral, portfolio, risk, macro).
  → EXPANDA com novas páginas.

## Regras de design invioláveis

(Referência completa no plano, seção "Regras de Design para Claude Code")

1. Single Responsibility: cada Node faz UMA coisa.
2. Comunicação via PipelineContext — sem estado global.
3. Fetchers só buscam. Analyzers só calculam. Strategies só decidem.
4. DataLake é o single source of truth para dados históricos.
5. Backward compatibility: pipelines existentes NUNCA quebram.
6. Type hints em tudo. Pydantic para modelos. Typing para funções.
7. Testes para cada componente novo.
8. Logs via get_logger(__name__) em todo módulo.
9. AI providers são intercambiáveis via PromptEngine.
10. AI nunca executa — só analisa, narra, recomenda.
11. Publishers são independentes — falha num canal não impede os demais.
12. Strategy.evaluate(ctx) -> StrategyResult é o método central.
13. StrategyNode(Node) é a ponte entre Strategy e DAGEngine.
14. CompositeStrategy usa Layered como padrão, com gates condicionais.
15. OptimizationConfig fica em config/optimization.py.
16. Custos de IA são rastreados — budget mensal é hard limit.

## Fases de implementação — referência rápida

| Fase | Escopo | Status |
|------|--------|--------|
| 0 | Infra: DataLake SQLite, IngestNodes, settings | CONCLUÍDA |
| 1 | Fontes: FRED, CVM, Tesouro, DDM | CONCLUÍDA |
| H | Hardening: Result type, validação, error handling, testes | CONCLUÍDA |
| 2 Sprint 0-1 | Analyzers: currency, commodity, fiscal (3/9) | CONCLUÍDA |
| Fetcher Max A | Fundação: deps, constants, FetchWithFallback, ReferenceLake | CONCLUÍDA |
| Fetcher Max B | BCB (6 mixins), IBGE (+analfabetismo), FRED (+11 methods), auditoria | CONCLUÍDA |
| Fetcher Max C-D | Expansão Yahoo/DDM/Tesouro/CVM + TradingComDadosFetcher + IngestNodes | Pendente |
| 2 Sprint 2+ | Analyzers restantes (fundamental, yield curve, global macro...) | Pendente |
| 3 | Estratégias + Optimizer (PyPortfolioOpt) + Backtesting | Pendente |
| 4 | ML: scoring fundamentalista, integração ML↔optimizer | Pendente |
| 5 | NLP: sentimento, geopolítica, crisis hedge | Pendente |
| 6 | AI Reasoning: Claude/Deepseek, prompts, AIAnalysis | Pendente |
| 7 | Publishers: Telegram bot, PDF, email, Excel, web, scheduler | Pendente |

Detalhes de cada fase estão no plano. Leia a seção correspondente
antes de iniciar cada fase.

## Como iniciar

Quando o humano disser "vamos começar" ou indicar que quer iniciar uma fase:

1. Leia o plano de implementação inteiro (se ainda não leu).
2. Audite o código existente para a fase em questão.
3. Proponha a decomposição da fase em sprints de 1-3 dias cada.
4. Apresente o Sprint 1 com escopo, entregáveis e perguntas.
5. Aguarde aprovação antes de escrever código.

Quando o humano disser "continuar", "próximo sprint", ou similar:
1. Faça a revisão do sprint anterior (se aplicável).
2. Apresente o próximo sprint.
3. Aguarde aprovação.

Quando o humano fizer uma pergunta técnica ou de design:
1. Consulte o plano de implementação primeiro.
2. Se a resposta está lá, cite a seção relevante.
3. Se não está, proponha uma solução fundamentada e pergunte se deve atualizar o plano.

## Idioma

Comunique-se em português brasileiro. Código e docstrings em português
(conforme o padrão existente no repositório). Nomes de classes, métodos
e variáveis em inglês (conforme o padrão existente).
````
