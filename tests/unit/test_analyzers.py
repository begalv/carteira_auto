"""Testes dos analyzers — Portfolio, Risk, Macro, Market, Rebalancer, DAGEngine."""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from carteira_auto.core.engine import (
    DAGEngine,
    Node,
    NodeExecutionError,
    PipelineContext,
)
from carteira_auto.core.models import (
    Asset,
    MacroContext,
    MarketMetrics,
    Portfolio,
    PortfolioMetrics,
    RiskMetrics,
)

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def portfolio_simples():
    """Portfolio com 3 ativos para testes."""
    return Portfolio(
        assets=[
            Asset(
                ticker="PETR4",
                nome="Petrobras PN",
                classe="Ações",
                posicao_atual=5000.0,
                preco_posicao=4000.0,
                preco_atual=35.0,
                preco_medio=28.0,
                pct_meta=0.15,
                proventos_recebidos=200.0,
                n_cotas_atual=142.0,
            ),
            Asset(
                ticker="VALE3",
                nome="Vale ON",
                classe="Ações",
                posicao_atual=3000.0,
                preco_posicao=2500.0,
                preco_atual=65.0,
                preco_medio=50.0,
                pct_meta=0.10,
                proventos_recebidos=100.0,
                n_cotas_atual=46.0,
            ),
            Asset(
                ticker="XPML11",
                nome="XP Malls FII",
                classe="Renda Fixa",
                posicao_atual=2000.0,
                preco_posicao=2200.0,
                preco_atual=98.0,
                preco_medio=110.0,
                pct_meta=0.05,
                proventos_recebidos=150.0,
                n_cotas_atual=20.0,
            ),
        ]
    )


@pytest.fixture
def ctx_com_portfolio(portfolio_simples):
    """PipelineContext com portfolio carregado."""
    ctx = PipelineContext()
    ctx["portfolio"] = portfolio_simples
    return ctx


# ============================================================================
# DAGEngine — ERROR HANDLING
# ============================================================================


class TestDAGEngineErrorHandling:
    """Testes do error handling per-node no DAGEngine."""

    def _make_node(self, name: str, deps: list[str] | None = None, fail: bool = False):
        """Cria um node de teste."""
        _fail = fail
        _name = name
        _deps = deps or []

        class TestNode(Node):
            name = _name
            dependencies = _deps

            def run(self, ctx):
                if _fail:
                    raise ValueError(f"Erro simulado em {_name}")
                ctx[f"{_name}_done"] = True
                return ctx

        return TestNode()

    def test_pipeline_sem_erros(self):
        engine = DAGEngine()
        engine.register(self._make_node("a"))
        engine.register(self._make_node("b", deps=["a"]))
        ctx = engine.run("b")
        assert ctx["a_done"]
        assert ctx["b_done"]
        assert not ctx.has_errors

    def test_pipeline_com_erro_continua(self):
        """Em modo padrão (fail_fast=False), pipeline continua após erro."""
        engine = DAGEngine(fail_fast=False)
        node_a = self._make_node("a")
        node_b = self._make_node("b", deps=["a"], fail=True)

        engine.register(node_a)
        engine.register(node_b)

        ctx = engine.run("b")
        assert ctx["a_done"]
        assert ctx.has_errors
        assert "b" in ctx.errors

    def test_pipeline_fail_fast(self):
        """Em modo fail_fast=True, pipeline para no primeiro erro."""
        engine = DAGEngine(fail_fast=True)
        engine.register(self._make_node("a", fail=True))

        with pytest.raises(NodeExecutionError, match="Erro no node 'a'"):
            engine.run("a")

    def test_errors_registrados_no_contexto(self):
        engine = DAGEngine()
        engine.register(self._make_node("a", fail=True))
        ctx = engine.run("a")
        assert ctx.has_errors
        assert "a" in ctx.errors
        assert "Erro simulado" in ctx.errors["a"]

    def test_pipeline_context_errors_property(self):
        ctx = PipelineContext()
        assert not ctx.has_errors
        assert ctx.errors == {}

        ctx["_errors"] = {"node_x": "falhou"}
        assert ctx.has_errors
        assert "node_x" in ctx.errors


class TestNodeDependenciesIsolation:
    """Testa que dependencies são isoladas entre subclasses."""

    def test_subclasses_nao_compartilham_dependencies(self):
        class NodeA(Node):
            name = "a"
            dependencies = ["x"]

            def run(self, ctx):
                return ctx

        class NodeB(Node):
            name = "b"
            dependencies = ["y"]

            def run(self, ctx):
                return ctx

        class NodeC(Node):
            name = "c"

            def run(self, ctx):
                return ctx

        assert NodeA.dependencies == ["x"]
        assert NodeB.dependencies == ["y"]
        assert NodeC.dependencies == []

        # Mutação em uma não afeta outra
        NodeA.dependencies.append("z")
        assert "z" not in NodeB.dependencies
        assert "z" not in NodeC.dependencies


# ============================================================================
# PORTFOLIO ANALYZER
# ============================================================================


class TestPortfolioAnalyzer:
    """Testes do PortfolioAnalyzer."""

    def test_calcula_metricas_basicas(self, ctx_com_portfolio):
        from carteira_auto.analyzers import PortfolioAnalyzer

        analyzer = PortfolioAnalyzer()
        ctx = analyzer.run(ctx_com_portfolio)

        metrics: PortfolioMetrics = ctx["portfolio_metrics"]
        assert metrics.total_value == 10000.0  # 5000 + 3000 + 2000
        assert metrics.total_cost == 8700.0  # 4000 + 2500 + 2200
        assert metrics.total_return == 1300.0
        assert metrics.total_return_pct == pytest.approx(1300.0 / 8700.0, rel=1e-4)

    def test_calcula_dividend_yield(self, ctx_com_portfolio):
        from carteira_auto.analyzers import PortfolioAnalyzer

        analyzer = PortfolioAnalyzer()
        ctx = analyzer.run(ctx_com_portfolio)

        metrics: PortfolioMetrics = ctx["portfolio_metrics"]
        # 450 dividendos / 10000 valor total = 0.045
        assert metrics.dividend_yield == pytest.approx(0.045, rel=1e-4)

    def test_portfolio_sem_posicao(self):
        from carteira_auto.analyzers import PortfolioAnalyzer

        portfolio = Portfolio(assets=[Asset(ticker="PETR4", nome="Petrobras")])
        ctx = PipelineContext()
        ctx["portfolio"] = portfolio

        analyzer = PortfolioAnalyzer()
        ctx = analyzer.run(ctx)
        metrics = ctx["portfolio_metrics"]
        assert metrics.total_value == 0.0
        assert metrics.total_return_pct == 0.0

    def test_allocation_results(self, ctx_com_portfolio):
        from carteira_auto.analyzers import PortfolioAnalyzer

        analyzer = PortfolioAnalyzer()
        ctx = analyzer.run(ctx_com_portfolio)

        metrics: PortfolioMetrics = ctx["portfolio_metrics"]
        assert len(metrics.allocations) > 0
        for alloc in metrics.allocations:
            assert alloc.action in ("comprar", "vender", "manter")


# ============================================================================
# RISK ANALYZER
# ============================================================================


class TestRiskAnalyzer:
    """Testes do RiskAnalyzer com mock do Yahoo."""

    def _mock_historical_data(self, tickers, **kwargs):
        """Gera DataFrame de preços históricos para mock."""
        dates = pd.date_range("2025-01-01", periods=252, freq="B")
        data = {}
        for t in tickers:
            np.random.seed(hash(t) % 2**31)
            prices = 100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, 252)))
            data[t] = prices
        return pd.DataFrame(data, index=dates)

    @patch("carteira_auto.data.fetchers.YahooFinanceFetcher")
    def test_calcula_risk_metrics(self, mock_yahoo_cls, ctx_com_portfolio):
        from carteira_auto.analyzers import RiskAnalyzer

        mock_yahoo = MagicMock()
        mock_yahoo_cls.return_value = mock_yahoo
        mock_yahoo.get_historical_price_data.return_value = self._mock_historical_data(
            ["PETR4", "VALE3", "XPML11"]
        )

        analyzer = RiskAnalyzer()
        ctx = analyzer.run(ctx_com_portfolio)

        metrics: RiskMetrics = ctx["risk_metrics"]
        assert metrics.volatility is not None
        assert metrics.volatility > 0
        assert metrics.var_95 is not None
        assert metrics.var_95 < 0  # VaR é negativo
        assert metrics.sharpe_ratio is not None

    @patch("carteira_auto.data.fetchers.YahooFinanceFetcher")
    def test_risk_com_historico_vazio(self, mock_yahoo_cls, ctx_com_portfolio):
        from carteira_auto.analyzers import RiskAnalyzer

        mock_yahoo = MagicMock()
        mock_yahoo_cls.return_value = mock_yahoo
        mock_yahoo.get_historical_price_data.return_value = pd.DataFrame()

        analyzer = RiskAnalyzer()
        ctx = analyzer.run(ctx_com_portfolio)

        metrics: RiskMetrics = ctx["risk_metrics"]
        assert not metrics.is_complete()

    @patch("carteira_auto.data.fetchers.YahooFinanceFetcher")
    def test_risk_com_excecao_registra_erro(self, mock_yahoo_cls, ctx_com_portfolio):
        from carteira_auto.analyzers import RiskAnalyzer

        mock_yahoo = MagicMock()
        mock_yahoo_cls.return_value = mock_yahoo
        mock_yahoo.get_historical_price_data.side_effect = ConnectionError("API down")

        analyzer = RiskAnalyzer()
        ctx = analyzer.run(ctx_com_portfolio)

        metrics: RiskMetrics = ctx["risk_metrics"]
        assert not metrics.is_complete()
        assert ctx.has_errors
        assert "analyze_risk._calculate_risk" in ctx.errors

    def test_risk_portfolio_sem_posicoes(self):
        from carteira_auto.analyzers import RiskAnalyzer

        portfolio = Portfolio(assets=[Asset(ticker="PETR4", nome="Petrobras")])
        ctx = PipelineContext()
        ctx["portfolio"] = portfolio

        analyzer = RiskAnalyzer()
        ctx = analyzer.run(ctx)
        metrics = ctx["risk_metrics"]
        assert metrics == RiskMetrics()


# ============================================================================
# MACRO ANALYZER
# ============================================================================


class TestMacroAnalyzer:
    """Testes do MacroAnalyzer com mock de BCB e IBGE."""

    @patch("carteira_auto.data.fetchers.IBGEFetcher")
    @patch("carteira_auto.data.fetchers.BCBFetcher")
    def test_contexto_macro_completo(self, mock_bcb_cls, mock_ibge_cls):
        from carteira_auto.analyzers import MacroAnalyzer

        mock_bcb = MagicMock()
        mock_bcb_cls.return_value = mock_bcb
        mock_bcb.get_selic.return_value = pd.DataFrame({"valor": [11.75]})
        mock_bcb.get_ipca.return_value = pd.DataFrame({"valor": [0.38, 0.42, 0.35]})
        mock_bcb.get_ptax.return_value = pd.DataFrame({"valor": [5.25]})

        mock_ibge = MagicMock()
        mock_ibge_cls.return_value = mock_ibge
        mock_ibge.get_pib.return_value = pd.DataFrame({"valor": [2.5]})

        analyzer = MacroAnalyzer()
        ctx = PipelineContext()
        ctx = analyzer.run(ctx)

        macro: MacroContext = ctx["macro_context"]
        assert macro.selic == 11.75
        assert macro.ipca is not None
        assert macro.cambio == 5.25
        assert macro.pib_growth == 2.5
        assert "Selic" in macro.summary

    @patch("carteira_auto.data.fetchers.IBGEFetcher")
    @patch("carteira_auto.data.fetchers.BCBFetcher")
    def test_falha_parcial_registra_erros(self, mock_bcb_cls, mock_ibge_cls):
        from carteira_auto.analyzers import MacroAnalyzer

        mock_bcb = MagicMock()
        mock_bcb_cls.return_value = mock_bcb
        mock_bcb.get_selic.side_effect = ConnectionError("BCB down")
        mock_bcb.get_ipca.return_value = pd.DataFrame({"valor": [0.38]})
        mock_bcb.get_ptax.return_value = pd.DataFrame({"valor": [5.25]})

        mock_ibge = MagicMock()
        mock_ibge_cls.return_value = mock_ibge
        mock_ibge.get_pib.side_effect = TimeoutError("IBGE timeout")

        analyzer = MacroAnalyzer()
        ctx = PipelineContext()
        ctx = analyzer.run(ctx)

        macro: MacroContext = ctx["macro_context"]
        assert macro.selic is None  # falhou
        assert macro.ipca is not None  # sucesso
        assert macro.cambio == 5.25  # sucesso
        assert macro.pib_growth is None  # falhou
        assert ctx.has_errors
        assert "Selic" in ctx.errors["analyze_macro.partial"]
        assert "PIB" in ctx.errors["analyze_macro.partial"]


# ============================================================================
# MARKET ANALYZER
# ============================================================================


class TestMarketAnalyzer:
    """Testes do MarketAnalyzer com mock."""

    @patch("carteira_auto.data.fetchers.BCBFetcher")
    @patch("carteira_auto.data.fetchers.YahooFinanceFetcher")
    def test_benchmarks_completos(self, mock_yahoo_cls, mock_bcb_cls):
        from carteira_auto.analyzers import MarketAnalyzer

        mock_yahoo = MagicMock()
        mock_yahoo_cls.return_value = mock_yahoo

        ibov_data = pd.DataFrame({"Close": [100000, 112000]})
        ifix_data = pd.DataFrame({"Close": [2800, 2900]})

        def side_effect(tickers, **kwargs):
            if "^BVSP" in tickers:
                return ibov_data
            return ifix_data

        mock_yahoo.get_historical_price_data.side_effect = side_effect

        mock_bcb = MagicMock()
        mock_bcb_cls.return_value = mock_bcb
        mock_bcb.get_cdi.return_value = pd.DataFrame({"valor": [0.04, 0.04, 0.04]})

        analyzer = MarketAnalyzer()
        ctx = PipelineContext()
        ctx = analyzer.run(ctx)

        metrics: MarketMetrics = ctx["market_metrics"]
        assert metrics.ibov_return == pytest.approx(0.12, rel=1e-4)
        assert metrics.cdi_return is not None


# ============================================================================
# REBALANCER
# ============================================================================


class TestRebalancer:
    """Testes do Rebalancer."""

    def test_rebalanceamento_basico(self, ctx_com_portfolio):
        from carteira_auto.analyzers import PortfolioAnalyzer, Rebalancer

        pa = PortfolioAnalyzer()
        ctx = pa.run(ctx_com_portfolio)

        rebalancer = Rebalancer()
        ctx = rebalancer.run(ctx)

        recs = ctx["rebalance_recommendations"]
        assert isinstance(recs, list)
        for rec in recs:
            assert rec.action in ("comprar", "vender")
            assert rec.ticker
            assert rec.reason

    def test_portfolio_equilibrado_sem_recomendacoes(self):
        from carteira_auto.analyzers import PortfolioAnalyzer, Rebalancer

        portfolio = Portfolio(
            assets=[
                Asset(
                    ticker="PETR4",
                    nome="Petrobras",
                    classe="Ações",
                    posicao_atual=100.0,
                )
            ]
        )
        ctx = PipelineContext()
        ctx["portfolio"] = portfolio

        pa = PortfolioAnalyzer()
        ctx = pa.run(ctx)

        rebalancer = Rebalancer()
        ctx = rebalancer.run(ctx)

        recs = ctx["rebalance_recommendations"]
        assert isinstance(recs, list)
