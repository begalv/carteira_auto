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
    ctx["target_allocations"] = {"Ações": 0.80, "Renda Fixa": 0.20}
    ctx["rebalance_threshold"] = 0.05
    ctx["min_trade_value"] = 100.0
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
        """Verifica que todos os 11 campos de MacroContext são preenchidos."""
        from carteira_auto.analyzers import MacroAnalyzer

        mock_bcb = MagicMock()
        mock_bcb_cls.return_value = mock_bcb
        # Taxas de juros
        mock_bcb.get_selic.return_value = pd.DataFrame({"valor": [11.75]})
        mock_bcb.get_cdi.return_value = pd.DataFrame({"valor": [0.042, 0.042, 0.042]})
        mock_bcb.get_poupanca.return_value = pd.DataFrame({"valor": [0.6183]})
        mock_bcb.get_tr.return_value = pd.DataFrame({"valor": [0.0]})
        # Inflação
        mock_bcb.get_ipca.return_value = pd.DataFrame({"valor": [0.38, 0.42, 0.35]})
        mock_bcb.get_igpm.return_value = pd.DataFrame({"valor": [0.15, 0.22, 0.31]})
        mock_bcb.get_inpc.return_value = pd.DataFrame({"valor": [0.40, 0.41, 0.36]})
        # Câmbio
        mock_bcb.get_ptax.return_value = pd.DataFrame({"valor": [5.25]})
        mock_bcb.get_ptax_venda.return_value = pd.DataFrame({"valor": [5.27]})

        mock_ibge = MagicMock()
        mock_ibge_cls.return_value = mock_ibge
        mock_ibge.get_pib.return_value = pd.DataFrame({"valor": [2.5]})
        mock_ibge.get_unemployment.return_value = pd.DataFrame({"valor": [6.2]})

        analyzer = MacroAnalyzer()
        ctx = PipelineContext()
        ctx = analyzer.run(ctx)

        macro: MacroContext = ctx["macro_context"]
        # Taxas de juros
        assert macro.selic == 11.75
        assert macro.cdi is not None  # CDI acumulado % a.a.
        assert macro.poupanca == pytest.approx(0.6183)
        assert macro.tr == pytest.approx(0.0)
        # Inflação
        assert macro.ipca is not None  # IPCA acumulado 12m
        assert macro.igpm is not None  # IGP-M acumulado 12m
        assert macro.inpc is not None  # INPC acumulado 12m
        # Câmbio
        assert macro.cambio == 5.25
        assert macro.dolar_ptax_venda == 5.27
        # Atividade
        assert macro.pib_growth == 2.5
        assert macro.desocupacao == 6.2  # ← novo campo (taxa de desemprego)
        # Summary
        assert "Selic" in macro.summary
        assert "Desocup" in macro.summary

    @patch("carteira_auto.data.fetchers.IBGEFetcher")
    @patch("carteira_auto.data.fetchers.BCBFetcher")
    def test_macro_campos_novos_independentes(self, mock_bcb_cls, mock_ibge_cls):
        """Falha em campos novos (CDI, IGP-M, desocupação) não afeta campos legados."""
        from carteira_auto.analyzers import MacroAnalyzer

        mock_bcb = MagicMock()
        mock_bcb_cls.return_value = mock_bcb
        mock_bcb.get_selic.return_value = pd.DataFrame({"valor": [11.75]})
        mock_bcb.get_cdi.side_effect = ConnectionError("CDI down")
        mock_bcb.get_igpm.side_effect = TimeoutError("IGP-M timeout")
        mock_bcb.get_inpc.side_effect = TimeoutError("INPC timeout")
        mock_bcb.get_poupanca.side_effect = ConnectionError("Poupança down")
        mock_bcb.get_tr.side_effect = ConnectionError("TR down")
        mock_bcb.get_ipca.return_value = pd.DataFrame({"valor": [0.38]})
        mock_bcb.get_ptax.return_value = pd.DataFrame({"valor": [5.25]})
        mock_bcb.get_ptax_venda.return_value = pd.DataFrame({"valor": [5.27]})

        mock_ibge = MagicMock()
        mock_ibge_cls.return_value = mock_ibge
        mock_ibge.get_pib.return_value = pd.DataFrame({"valor": [2.5]})
        mock_ibge.get_unemployment.side_effect = TimeoutError("PNAD timeout")

        analyzer = MacroAnalyzer()
        ctx = PipelineContext()
        ctx = analyzer.run(ctx)

        macro: MacroContext = ctx["macro_context"]
        assert macro.selic == 11.75  # sucesso
        assert macro.ipca is not None  # sucesso
        assert macro.cambio == 5.25  # sucesso
        assert macro.dolar_ptax_venda == 5.27  # sucesso
        assert macro.pib_growth == 2.5  # sucesso
        # Campos que falharam → None
        assert macro.cdi is None
        assert macro.igpm is None
        assert macro.inpc is None
        assert macro.poupanca is None
        assert macro.tr is None
        assert macro.desocupacao is None
        # Erros registrados
        assert ctx.has_errors

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
        """Verifica todos os 8 benchmarks de MarketMetrics."""
        from carteira_auto.analyzers import MarketAnalyzer

        mock_yahoo = MagicMock()
        mock_yahoo_cls.return_value = mock_yahoo

        ibov_data = pd.DataFrame({"Close": [100_000.0, 112_000.0]})
        ifix_data = pd.DataFrame({"Close": [2_800.0, 2_900.0]})
        sp500_data = pd.DataFrame({"Close": [4_000.0, 4_800.0]})
        dolar_data = pd.DataFrame({"Close": [5.0, 5.5]})
        ouro_data = pd.DataFrame({"Close": [1_800.0, 2_100.0]})

        def side_effect(tickers, **kwargs):
            t = tickers if isinstance(tickers, str) else tickers[0]
            if t == "^BVSP":
                return ibov_data
            elif t == "IFIX.SA":
                return ifix_data
            elif t == "^GSPC":
                return sp500_data
            elif t == "BRL=X":
                return dolar_data
            elif t == "GC=F":
                return ouro_data
            return pd.DataFrame({"Close": [100.0, 100.0]})

        mock_yahoo.get_historical_price_data.side_effect = side_effect

        mock_bcb = MagicMock()
        mock_bcb_cls.return_value = mock_bcb
        mock_bcb.get_cdi.return_value = pd.DataFrame({"valor": [0.042, 0.042, 0.042]})
        mock_bcb.get_selic.return_value = pd.DataFrame({"valor": [11.75, 11.75]})
        mock_bcb.get_ptax.return_value = pd.DataFrame({"valor": [5.25]})

        analyzer = MarketAnalyzer()
        ctx = PipelineContext()
        ctx = analyzer.run(ctx)

        metrics: MarketMetrics = ctx["market_metrics"]
        # Benchmarks BR
        assert metrics.ibov_return == pytest.approx(0.12, rel=1e-4)
        assert metrics.ifix_return == pytest.approx(2900 / 2800 - 1, rel=1e-4)
        assert metrics.cdi_return is not None
        assert metrics.selic_retorno is not None
        # Internacional
        assert metrics.sp500_return == pytest.approx(4800 / 4000 - 1, rel=1e-4)
        assert metrics.dolar_retorno == pytest.approx(5.5 / 5.0 - 1, rel=1e-4)
        assert metrics.ouro_retorno == pytest.approx(2100 / 1800 - 1, rel=1e-3)
        # Câmbio atual
        assert metrics.brl_usd == pytest.approx(5.25)

    @patch("carteira_auto.data.fetchers.BCBFetcher")
    @patch("carteira_auto.data.fetchers.YahooFinanceFetcher")
    def test_benchmarks_falha_parcial(self, mock_yahoo_cls, mock_bcb_cls):
        """Falha em um benchmark não impede os demais."""
        from carteira_auto.analyzers import MarketAnalyzer

        mock_yahoo = MagicMock()
        mock_yahoo_cls.return_value = mock_yahoo

        def side_effect(tickers, **kwargs):
            t = tickers if isinstance(tickers, str) else tickers[0]
            if t == "^BVSP":
                return pd.DataFrame({"Close": [100_000.0, 112_000.0]})
            raise ConnectionError(f"Yahoo down para {t}")

        mock_yahoo.get_historical_price_data.side_effect = side_effect

        mock_bcb = MagicMock()
        mock_bcb_cls.return_value = mock_bcb
        mock_bcb.get_cdi.return_value = pd.DataFrame({"valor": [0.042]})
        mock_bcb.get_selic.side_effect = TimeoutError("BCB timeout")
        mock_bcb.get_ptax.side_effect = TimeoutError("BCB timeout")

        analyzer = MarketAnalyzer()
        ctx = PipelineContext()
        ctx = analyzer.run(ctx)

        metrics: MarketMetrics = ctx["market_metrics"]
        assert metrics.ibov_return == pytest.approx(0.12, rel=1e-4)
        assert metrics.cdi_return is not None
        assert metrics.ifix_return is None
        assert metrics.sp500_return is None
        assert metrics.selic_retorno is None
        assert ctx.has_errors


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
