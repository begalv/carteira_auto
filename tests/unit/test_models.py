"""Testes dos modelos de dados — portfolio, analysis, economic e Result type."""

import pytest
from carteira_auto.core.models.analysis import (
    AllocationResult,
    MacroContext,
    MarketMetrics,
    PortfolioMetrics,
    RebalanceRecommendation,
    RiskMetrics,
)
from carteira_auto.core.models.economic import (
    EconomicSectorIndicator,
    MacroIndicator,
    MacroSnapshot,
    MarketIndicator,
    SectorIndicator,
)
from carteira_auto.core.models.portfolio import Asset, Portfolio, SoldAsset
from carteira_auto.core.result import Err, Ok
from pydantic import ValidationError

# ============================================================================
# RESULT TYPE
# ============================================================================


class TestOk:
    """Testes do Result Ok."""

    def test_ok_basico(self):
        r = Ok(42)
        assert r.is_ok()
        assert not r.is_err()
        assert r.unwrap() == 42

    def test_ok_unwrap_or_retorna_valor(self):
        r = Ok("sucesso")
        assert r.unwrap_or("fallback") == "sucesso"

    def test_ok_repr(self):
        r = Ok(10)
        assert "Ok(10)" in repr(r)

    def test_ok_com_objeto_complexo(self):
        metrics = RiskMetrics(volatility=0.15, sharpe_ratio=1.2)
        r = Ok(metrics)
        assert r.unwrap().volatility == 0.15


class TestErr:
    """Testes do Result Err."""

    def test_err_basico(self):
        r = Err("falha na API")
        assert r.is_err()
        assert not r.is_ok()
        assert r.error == "falha na API"

    def test_err_unwrap_levanta_excecao(self):
        r = Err("erro")
        with pytest.raises(ValueError, match="Chamou unwrap.*Err"):
            r.unwrap()

    def test_err_unwrap_or_retorna_default(self):
        r = Err("erro")
        assert r.unwrap_or(0) == 0

    def test_err_com_detalhes(self):
        r = Err("timeout", {"endpoint": "/api/v1", "elapsed_ms": 5000})
        assert r.details["endpoint"] == "/api/v1"
        assert r.details["elapsed_ms"] == 5000

    def test_err_repr(self):
        r = Err("falha")
        assert "Err('falha')" in repr(r)


# ============================================================================
# ASSET
# ============================================================================


class TestAsset:
    """Testes de criação e validação de Asset."""

    def test_asset_minimo(self):
        """Asset com apenas campos obrigatórios."""
        asset = Asset(ticker="PETR4", nome="Petrobras PN")
        assert asset.ticker == "PETR4"
        assert asset.nome == "Petrobras PN"
        assert asset.preco_atual is None

    def test_asset_completo(self):
        """Asset com todos os campos preenchidos."""
        asset = Asset(
            ticker="VALE3",
            nome="Vale ON",
            classe="Ação BR",
            setor="Materiais Básicos",
            subsetor="Mineração",
            segmento="Minerais Metálicos",
            pct_meta=0.10,
            valor_meta=10000.0,
            pct_atual=0.08,
            pct_inicial=0.05,
            posicao_atual=8000.0,
            preco_posicao=7500.0,
            valorizacao=500.0,
            valorizacao_pct=0.0667,
            proventos_recebidos=200.0,
            diferenca=-2000.0,
            rentabilidade=0.0933,
            rentabilidade_proporcional=0.007,
            preco_atual=65.50,
            preco_medio=58.00,
            n_cotas_atual=122.0,
        )
        assert asset.preco_atual == 65.50
        assert asset.pct_meta == 0.10

    def test_asset_ticker_vazio_falha(self):
        with pytest.raises(ValidationError, match="ticker não pode ser vazio"):
            Asset(ticker="", nome="Teste")

    def test_asset_ticker_espacos_falha(self):
        with pytest.raises(ValidationError, match="ticker não pode ser vazio"):
            Asset(ticker="   ", nome="Teste")

    def test_asset_ticker_strip(self):
        """Ticker com espaços é limpo automaticamente."""
        asset = Asset(ticker="  PETR4  ", nome="Petrobras")
        assert asset.ticker == "PETR4"

    def test_asset_nome_vazio_falha(self):
        with pytest.raises(ValidationError, match="nome não pode ser vazio"):
            Asset(ticker="PETR4", nome="")

    def test_asset_preco_negativo_falha(self):
        with pytest.raises(ValidationError, match="preco_atual.*negativo"):
            Asset(ticker="PETR4", nome="Petrobras", preco_atual=-10.0)

    def test_asset_preco_medio_negativo_falha(self):
        with pytest.raises(ValidationError, match="preco_medio.*negativo"):
            Asset(ticker="PETR4", nome="Petrobras", preco_medio=-5.0)

    def test_asset_preco_posicao_negativo_falha(self):
        with pytest.raises(ValidationError, match="preco_posicao.*negativo"):
            Asset(ticker="PETR4", nome="Petrobras", preco_posicao=-1.0)

    def test_asset_posicao_negativa_falha(self):
        with pytest.raises(ValidationError, match="posicao_atual.*negativo"):
            Asset(ticker="PETR4", nome="Petrobras", posicao_atual=-100.0)

    def test_asset_cotas_negativas_falha(self):
        with pytest.raises(ValidationError, match="n_cotas_atual.*negativo"):
            Asset(ticker="PETR4", nome="Petrobras", n_cotas_atual=-10.0)

    def test_asset_pct_meta_negativo_falha(self):
        with pytest.raises(ValidationError, match="pct_meta.*negativo"):
            Asset(ticker="PETR4", nome="Petrobras", pct_meta=-0.1)

    def test_asset_valor_meta_negativo_falha(self):
        with pytest.raises(ValidationError, match="valor_meta.*negativo"):
            Asset(ticker="PETR4", nome="Petrobras", valor_meta=-100.0)

    def test_asset_preco_zero_valido(self):
        """Preço zero é válido (pode acontecer com ativos delisted)."""
        asset = Asset(ticker="OIBR3", nome="Oi ON", preco_atual=0.0)
        assert asset.preco_atual == 0.0

    def test_asset_valorizacao_negativa_valida(self):
        """Valorização pode ser negativa (prejuízo)."""
        asset = Asset(ticker="PETR4", nome="Petrobras", valorizacao=-500.0)
        assert asset.valorizacao == -500.0

    def test_asset_rentabilidade_negativa_valida(self):
        """Rentabilidade pode ser negativa."""
        asset = Asset(ticker="PETR4", nome="Petrobras", rentabilidade=-0.15)
        assert asset.rentabilidade == -0.15

    def test_asset_diferenca_negativa_valida(self):
        """Diferença pode ser negativa (abaixo da meta)."""
        asset = Asset(ticker="PETR4", nome="Petrobras", diferenca=-2000.0)
        assert asset.diferenca == -2000.0

    def test_asset_campos_fundamentalistas(self):
        """Campos fundamentalistas são opcionais e aceitos corretamente."""
        asset = Asset(
            ticker="ITUB4",
            nome="Itaú Unibanco PN",
            p_l=8.5,
            p_vp=1.8,
            ev_ebitda=6.2,
            dy_12m=5.3,
            market_cap=280_000.0,
            roe=19.5,
            roa=2.1,
            margem_liquida=25.0,
            margem_ebitda=40.0,
            receita_liquida=95_000.0,
            ebitda=38_000.0,
            lpa=3.85,
            vpa=21.3,
            cagr_receita_5a=8.5,
            divida_liquida_ebitda=2.1,
            beta_5a=0.85,
            free_float=65.0,
            liquidez_media_diaria=500.0,
        )
        assert asset.p_l == 8.5
        assert asset.roe == 19.5
        assert asset.dy_12m == 5.3
        assert asset.beta_5a == 0.85
        # Campos não preenchidos devem ser None
        assert asset.preco_atual is None

    def test_asset_fundamentalistas_podem_ser_negativos(self):
        """P/L, ROE, margens etc. podem ser negativos (empresa com prejuízo)."""
        asset = Asset(
            ticker="MGLU3",
            nome="Magazine Luiza ON",
            p_l=-12.5,  # prejuízo
            roe=-8.3,  # ROE negativo
            margem_liquida=-2.1,  # margem negativa
            divida_liquida_ebitda=-0.5,  # caixa líquido (negativo = posição de caixa)
        )
        assert asset.p_l == -12.5
        assert asset.roe == -8.3
        assert asset.margem_liquida == -2.1
        assert asset.divida_liquida_ebitda == -0.5

    def test_asset_serializacao(self):
        """Asset serializa e deserializa corretamente."""
        asset = Asset(ticker="PETR4", nome="Petrobras", preco_atual=35.0)
        d = asset.model_dump()
        assert d["ticker"] == "PETR4"
        assert d["preco_atual"] == 35.0

        restored = Asset(**d)
        assert restored == asset

    def test_asset_model_copy(self):
        """model_copy cria cópia independente."""
        original = Asset(ticker="PETR4", nome="Petrobras", preco_atual=35.0)
        copia = original.model_copy(update={"preco_atual": 40.0})
        assert copia.preco_atual == 40.0
        assert original.preco_atual == 35.0


# ============================================================================
# SOLD ASSET
# ============================================================================


class TestSoldAsset:
    """Testes de criação e validação de SoldAsset."""

    def test_sold_asset_minimo(self):
        sa = SoldAsset(ticker="MGLU3", nome="Magazine Luiza")
        assert sa.ticker == "MGLU3"

    def test_sold_asset_ticker_vazio_falha(self):
        with pytest.raises(ValidationError, match="ticker não pode ser vazio"):
            SoldAsset(ticker="", nome="Teste")

    def test_sold_asset_preco_negativo_falha(self):
        with pytest.raises(ValidationError, match="preco_na_venda.*negativo"):
            SoldAsset(
                ticker="MGLU3",
                nome="Magazine Luiza",
                preco_na_venda=-10.0,
            )

    def test_sold_asset_cotas_negativas_falha(self):
        with pytest.raises(ValidationError, match="n_cotas_vendidas.*negativo"):
            SoldAsset(
                ticker="MGLU3",
                nome="Magazine Luiza",
                n_cotas_vendidas=-5.0,
            )

    def test_sold_asset_completo(self):
        sa = SoldAsset(
            ticker="MGLU3",
            nome="Magazine Luiza",
            classe="Ação BR",
            setor="Consumo",
            valor_venda=5000.0,
            preco_posicao=4000.0,
            valorizacao=1000.0,
            valorizacao_pct=0.25,
            proventos_recebidos=50.0,
            diferenca=1050.0,
            rentabilidade=0.2625,
            preco_na_venda=25.0,
            preco_medio_compra=20.0,
            n_cotas_vendidas=200.0,
            posicao_ativa=False,
            mes="2026-01",
        )
        assert sa.valor_venda == 5000.0


# ============================================================================
# PORTFOLIO
# ============================================================================


class TestPortfolio:
    """Testes de criação e validação de Portfolio."""

    def test_portfolio_basico(self):
        assets = [Asset(ticker="PETR4", nome="Petrobras")]
        portfolio = Portfolio(assets=assets)
        assert len(portfolio.assets) == 1
        assert portfolio.sold_assets == []

    def test_portfolio_vazio_falha(self):
        with pytest.raises(ValidationError, match="ao menos um ativo"):
            Portfolio(assets=[])

    def test_portfolio_com_vendas(self):
        assets = [Asset(ticker="PETR4", nome="Petrobras")]
        sold = [SoldAsset(ticker="MGLU3", nome="Magazine Luiza")]
        portfolio = Portfolio(assets=assets, sold_assets=sold)
        assert len(portfolio.sold_assets) == 1

    def test_portfolio_serializacao(self):
        assets = [
            Asset(ticker="PETR4", nome="Petrobras", preco_atual=35.0),
            Asset(ticker="VALE3", nome="Vale", preco_atual=65.0),
        ]
        portfolio = Portfolio(assets=assets)
        d = portfolio.model_dump()
        restored = Portfolio(**d)
        assert len(restored.assets) == 2
        assert restored.assets[0].ticker == "PETR4"


# ============================================================================
# ANALYSIS MODELS
# ============================================================================


class TestAllocationResult:
    """Testes do AllocationResult."""

    def test_allocation_valida(self):
        a = AllocationResult(
            asset_class="Ação BR",
            current_pct=0.45,
            target_pct=0.40,
            deviation=0.05,
            action="vender",
        )
        assert a.action == "vender"

    def test_allocation_action_invalida_falha(self):
        with pytest.raises(ValidationError):
            AllocationResult(
                asset_class="Ação BR",
                current_pct=0.45,
                target_pct=0.40,
                deviation=0.05,
                action="segurar",  # não é literal válido
            )

    def test_allocation_sem_action(self):
        a = AllocationResult(
            asset_class="FII",
            current_pct=0.20,
            target_pct=0.20,
            deviation=0.0,
        )
        assert a.action is None


class TestRiskMetrics:
    """Testes do RiskMetrics."""

    def test_risk_metrics_vazio(self):
        r = RiskMetrics()
        assert r.volatility is None
        assert not r.is_complete()

    def test_risk_metrics_completo(self):
        r = RiskMetrics(
            volatility=0.20,
            var_95=-0.033,
            var_99=-0.047,
            sharpe_ratio=1.5,
            max_drawdown=-0.15,
            beta=0.85,
        )
        assert r.is_complete()

    def test_risk_metrics_parcial(self):
        r = RiskMetrics(volatility=0.20, sharpe_ratio=1.5)
        assert not r.is_complete()


class TestPortfolioMetrics:
    """Testes do PortfolioMetrics."""

    def test_portfolio_metrics(self):
        pm = PortfolioMetrics(
            total_value=100000.0,
            total_cost=80000.0,
            total_return=20000.0,
            total_return_pct=0.25,
        )
        assert pm.total_return_pct == 0.25
        assert pm.allocations == []


class TestMarketMetrics:
    """Testes do MarketMetrics."""

    def test_market_metrics_vazio(self):
        mm = MarketMetrics()
        assert mm.ibov_return is None

    def test_market_metrics_completo(self):
        mm = MarketMetrics(ibov_return=0.12, ifix_return=0.08, cdi_return=0.1175)
        assert mm.cdi_return == 0.1175


class TestMacroContext:
    """Testes do MacroContext."""

    def test_macro_context(self):
        mc = MacroContext(selic=0.1175, ipca=0.045, cambio=5.25)
        assert mc.selic == 0.1175


class TestRebalanceRecommendation:
    """Testes do RebalanceRecommendation."""

    def test_rebalance_comprar(self):
        r = RebalanceRecommendation(
            ticker="PETR4",
            action="comprar",
            quantity=10.0,
            value=350.0,
            reason="Abaixo da meta em 5%",
        )
        assert r.action == "comprar"

    def test_rebalance_action_invalida_falha(self):
        with pytest.raises(ValidationError):
            RebalanceRecommendation(
                ticker="PETR4",
                action="manter",  # não é literal válido para Rebalance
            )


# ============================================================================
# ECONOMIC MODELS
# ============================================================================


class TestEconomicModels:
    """Testes dos modelos econômicos."""

    def test_macro_indicator(self):
        from datetime import date

        mi = MacroIndicator(
            name="Selic",
            value=11.75,
            date=date(2026, 3, 1),
            source="bcb",
            unit="%",
        )
        assert mi.name == "Selic"

    def test_macro_snapshot(self):
        from datetime import date, datetime

        indicators = [
            MacroIndicator(
                name="Selic", value=11.75, date=date(2026, 3, 1), source="bcb"
            ),
            MacroIndicator(
                name="IPCA", value=4.5, date=date(2026, 3, 1), source="ibge"
            ),
        ]
        snap = MacroSnapshot(indicators=indicators, timestamp=datetime.now())
        assert len(snap.indicators) == 2

    def test_market_indicator(self):
        from datetime import date

        mi = MarketIndicator(
            name="IBOV", value=128000.0, date=date(2026, 3, 1), source="yahoo"
        )
        assert mi.value == 128000.0

    def test_sector_indicator(self):
        si = SectorIndicator(sector="Financeiro", return_pct=0.15)
        assert si.sector == "Financeiro"

    def test_economic_sector_indicator(self):
        esi = EconomicSectorIndicator(
            sector="Agropecuária", gdp_share=0.07, growth_rate=0.03
        )
        assert esi.gdp_share == 0.07
