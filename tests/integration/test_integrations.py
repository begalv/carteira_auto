"""Testes de integração E2E — pipelines completos com dados mockados."""

from unittest.mock import MagicMock, patch

import pytest

from carteira_auto.core.engine import DAGEngine, Node
from carteira_auto.core.models import Asset, Portfolio

pytestmark = pytest.mark.integration

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_portfolio():
    """Portfolio de teste com dados completos."""
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
        ]
    )


# ============================================================================
# DAGEngine E2E
# ============================================================================


class TestDAGEngineE2E:
    """Testes E2E do DAGEngine com nodes reais."""

    def test_pipeline_dry_run(self):
        """dry_run retorna plano de execução sem executar."""
        from carteira_auto.core.registry import create_engine

        engine = create_engine()
        plan = engine.dry_run("analyze_portfolio")

        assert "load_portfolio" in plan
        assert "fetch_portfolio_prices" in plan
        assert "analyze_portfolio" in plan
        # Ordem topológica: load → fetch → analyze
        assert plan.index("load_portfolio") < plan.index("fetch_portfolio_prices")
        assert plan.index("fetch_portfolio_prices") < plan.index("analyze_portfolio")

    def test_pipeline_dry_run_macro(self):
        """Macro não tem dependências, dry_run retorna só o nó."""
        from carteira_auto.core.registry import create_engine

        engine = create_engine()
        plan = engine.dry_run("analyze_macro")
        assert plan == ["analyze_macro"]

    def test_pipeline_com_erro_graceful(self, mock_portfolio):
        """Pipeline continua após erro em um nó (fail_fast=False)."""

        class FailNode(Node):
            name = "fail_node"
            dependencies: list[str] = []

            def run(self, ctx):
                raise RuntimeError("Falha simulada")

        class SuccessNode(Node):
            name = "success_node"
            dependencies: list[str] = []

            def run(self, ctx):
                ctx["success"] = True
                return ctx

        engine = DAGEngine(fail_fast=False)
        engine.register(FailNode())
        engine.register(SuccessNode())

        # Precisamos de um node que dependa de ambos para rodar ambos
        class FinalNode(Node):
            name = "final"
            dependencies = ["fail_node", "success_node"]

            def run(self, ctx):
                ctx["final"] = True
                return ctx

        engine.register(FinalNode())
        ctx = engine.run("final")

        assert ctx.has_errors
        assert "fail_node" in ctx.errors
        assert ctx.get("success") is True


class TestRegistryPipelines:
    """Testes dos presets de pipeline do registry."""

    def test_todos_presets_resolvem(self):
        """Todos os pipeline presets resolvem sem erro."""
        from carteira_auto.core.registry import (
            PIPELINE_PRESETS,
            create_engine,
        )

        engine = create_engine()
        for pipeline_name, terminal_node in PIPELINE_PRESETS.items():
            plan = engine.dry_run(terminal_node)
            assert len(plan) >= 1, f"Pipeline '{pipeline_name}' retornou plano vazio"

    def test_get_terminal_node_valido(self):
        """get_terminal_node retorna node correto para pipeline válido."""
        from carteira_auto.core.registry import get_terminal_node

        assert get_terminal_node("analyze") == "analyze_portfolio"
        assert get_terminal_node("risk") == "analyze_risk"
        assert get_terminal_node("macro") == "analyze_macro"

    def test_get_terminal_node_invalido(self):
        """get_terminal_node levanta KeyError para pipeline inexistente."""
        from carteira_auto.core.registry import get_terminal_node

        with pytest.raises(KeyError, match="não encontrado"):
            get_terminal_node("pipeline_que_nao_existe")

    def test_list_pipelines(self):
        """list_pipelines retorna dict com todos os presets."""
        from carteira_auto.core.registry import list_pipelines

        pipelines = list_pipelines()
        assert len(pipelines) > 0
        assert "analyze" in pipelines
        assert isinstance(pipelines["analyze"], str)


class TestPortfolioAnalysisPipeline:
    """Testa fluxo Load → Fetch → Analyze com dados mockados."""

    @patch("carteira_auto.data.fetchers.YahooFinanceFetcher")
    @patch("carteira_auto.data.loaders.PortfolioLoader")
    def test_load_fetch_analyze(self, mock_loader_cls, mock_yahoo_cls, mock_portfolio):
        """Pipeline completo de análise de carteira."""
        from carteira_auto.analyzers import PortfolioAnalyzer
        from carteira_auto.core.nodes.portfolio_nodes import (
            FetchPortfolioPricesNode,
            LoadPortfolioNode,
        )

        # Mock loader
        mock_loader = MagicMock()
        mock_loader_cls.return_value = mock_loader
        mock_loader.load_portfolio.return_value = mock_portfolio

        # Mock Yahoo
        mock_yahoo = MagicMock()
        mock_yahoo_cls.return_value = mock_yahoo
        mock_yahoo.get_multiple_prices.return_value = {
            "PETR4": 36.0,
            "VALE3": 66.0,
        }

        # Monta pipeline manual
        engine = DAGEngine()
        engine.register(LoadPortfolioNode())
        engine.register(FetchPortfolioPricesNode())
        engine.register(PortfolioAnalyzer())

        ctx = engine.run("analyze_portfolio")

        # Verifica resultados
        assert "portfolio" in ctx
        assert "portfolio_metrics" in ctx
        metrics = ctx["portfolio_metrics"]
        assert metrics.total_value > 0
        assert len(metrics.allocations) > 0

        # Preços foram atualizados (sem mutação in-place)
        portfolio = ctx["portfolio"]
        petr4 = next(a for a in portfolio.assets if a.ticker == "PETR4")
        assert petr4.preco_atual == 36.0  # atualizado pelo fetch
