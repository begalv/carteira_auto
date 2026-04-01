"""Testes unitários do ReferenceLake.

Testa persistência e consulta de dados de referência:
composição de índices, expectativas Focus, targets de analistas,
taxas de crédito, CNAE, mapeamento ticker→CNPJ, major holders,
cadastro de fundos, composição de carteiras, intermediários e
registro de ativos.
"""

import pandas as pd
import pytest

from carteira_auto.data.lake.reference_lake import ReferenceLake


@pytest.fixture
def lake(tmp_path):
    """ReferenceLake em diretório temporário."""
    return ReferenceLake(tmp_path / "reference.db")


# ============================================================================
# Composição de Índices
# ============================================================================


class TestIndexComposition:
    def test_store_e_get_composicao(self, lake):
        df = pd.DataFrame(
            {
                "ticker": ["PETR4", "VALE3", "ITUB4"],
                "weight": [10.5, 8.3, 7.1],
            }
        )
        count = lake.store_index_composition("IBOV", df, source="tradingcomdados")
        assert count == 3

        result = lake.get_index_composition("IBOV")
        assert len(result) == 3
        assert result.iloc[0]["ticker"] == "PETR4"

    def test_get_composicao_inexistente(self, lake):
        result = lake.get_index_composition("XPTO")
        assert result.empty

    def test_store_df_vazio(self, lake):
        count = lake.store_index_composition("IBOV", pd.DataFrame(), source="ddm")
        assert count == 0

    def test_get_available_indexes(self, lake):
        df = pd.DataFrame({"ticker": ["A", "B"], "weight": [50, 50]})
        lake.store_index_composition("IBOV", df, source="t")
        lake.store_index_composition("IFIX", df, source="t")

        indexes = lake.get_available_indexes()
        assert "IBOV" in indexes
        assert "IFIX" in indexes

    def test_upsert_atualiza_peso(self, lake):
        df1 = pd.DataFrame({"ticker": ["PETR4"], "weight": [10.0]})
        lake.store_index_composition("IBOV", df1, source="t", ref_date="2024-01-01")

        df2 = pd.DataFrame({"ticker": ["PETR4"], "weight": [12.0]})
        lake.store_index_composition("IBOV", df2, source="t", ref_date="2024-01-01")

        result = lake.get_index_composition("IBOV", ref_date="2024-01-01")
        assert len(result) == 1
        assert result.iloc[0]["weight"] == 12.0


# ============================================================================
# Expectativas Focus
# ============================================================================


class TestFocusExpectations:
    def test_store_e_get_focus(self, lake):
        data = [
            {
                "reference_date": "2024-01-15",
                "target_period": "2024",
                "median": 9.25,
                "mean": 9.30,
                "min_value": 8.50,
                "max_value": 10.00,
                "respondents": 50,
            },
            {
                "reference_date": "2024-01-15",
                "target_period": "2025",
                "median": 8.50,
                "mean": 8.60,
                "min_value": 7.00,
                "max_value": 9.50,
                "respondents": 45,
            },
        ]
        count = lake.store_focus_expectations("selic", data)
        assert count == 2

        result = lake.get_focus_expectations("selic")
        assert len(result) == 2

    def test_store_focus_com_dataframe(self, lake):
        df = pd.DataFrame(
            {
                "reference_date": ["2024-01-15"],
                "target_period": ["2024"],
                "median": [4.0],
                "mean": [4.1],
                "min_value": [3.5],
                "max_value": [5.0],
                "respondents": [40],
            }
        )
        count = lake.store_focus_expectations("ipca", df)
        assert count == 1

    def test_store_focus_vazio(self, lake):
        assert lake.store_focus_expectations("pib", []) == 0
        assert lake.store_focus_expectations("pib", pd.DataFrame()) == 0


# ============================================================================
# Targets de Analistas
# ============================================================================


class TestAnalystTargets:
    def test_store_e_get_targets(self, lake):
        targets = {
            "target_high": 45.0,
            "target_low": 30.0,
            "target_mean": 38.5,
            "target_median": 39.0,
            "recommendation": "buy",
            "num_analysts": 12,
        }
        count = lake.store_analyst_targets("PETR4", targets, source="yahoo")
        assert count == 1

        result = lake.get_analyst_targets("PETR4")
        assert result is not None
        assert result["target_mean"] == 38.5
        assert result["recommendation"] == "buy"

    def test_get_targets_inexistente(self, lake):
        result = lake.get_analyst_targets("XPTO")
        assert result is None

    def test_store_targets_vazio(self, lake):
        assert lake.store_analyst_targets("PETR4", {}) == 0


# ============================================================================
# Upgrades / Downgrades
# ============================================================================


class TestUpgradesDowngrades:
    def test_store_upgrades(self, lake):
        df = pd.DataFrame(
            {
                "date": ["2024-01-10", "2024-02-15"],
                "firm": ["Goldman Sachs", "JP Morgan"],
                "to_grade": ["Buy", "Overweight"],
                "from_grade": ["Neutral", "Equal-weight"],
                "action": ["upgrade", "upgrade"],
            }
        )
        count = lake.store_upgrades_downgrades("VALE3", df, source="yahoo")
        assert count == 2

    def test_store_none_retorna_zero(self, lake):
        assert lake.store_upgrades_downgrades("X", None) == 0

    def test_store_df_vazio(self, lake):
        assert lake.store_upgrades_downgrades("X", pd.DataFrame()) == 0


# ============================================================================
# Taxas de Crédito
# ============================================================================


class TestLendingRates:
    def test_store_lending_rates(self, lake):
        data = [
            {
                "modality": "credito_pessoal",
                "bank": "BB",
                "rate": 5.5,
                "date": "2024-01",
            },
            {
                "modality": "credito_pessoal",
                "bank": "CEF",
                "rate": 4.8,
                "date": "2024-01",
            },
        ]
        count = lake.store_lending_rates(data)
        assert count == 2

    def test_store_lending_rates_df(self, lake):
        df = pd.DataFrame(
            {
                "modality": ["consignado"],
                "bank": ["Itaú"],
                "rate": [2.5],
                "date": ["2024-01"],
            }
        )
        count = lake.store_lending_rates(df)
        assert count == 1


# ============================================================================
# CNAE
# ============================================================================


class TestCNAE:
    def test_store_cnae(self, lake):
        classifications = [
            {
                "code": "A",
                "description": "Agricultura",
                "section": "A",
                "level": "section",
            },
            {
                "code": "01",
                "description": "Lavoura temporária",
                "section": "A",
                "division": "01",
                "level": "division",
            },
        ]
        count = lake.store_cnae(classifications)
        assert count == 2

    def test_store_cnae_vazio(self, lake):
        assert lake.store_cnae([]) == 0


# ============================================================================
# Ticker → CNPJ
# ============================================================================


class TestTickerCNPJ:
    def test_store_e_get_mapping(self, lake):
        mapping = {
            "PETR4": {"cnpj": "33.000.167/0001-01", "company_name": "Petrobras"},
            "VALE3": {"cnpj": "33.592.510/0001-54", "company_name": "Vale"},
        }
        count = lake.store_ticker_cnpj(mapping, source="ddm")
        assert count == 2

        assert lake.get_ticker_cnpj("PETR4") == "33.000.167/0001-01"
        assert lake.get_ticker_cnpj("XPTO") is None

    def test_get_all_mapping(self, lake):
        mapping = {
            "PETR4": {"cnpj": "33.000.167/0001-01", "company_name": "Petrobras"},
        }
        lake.store_ticker_cnpj(mapping, source="ddm")

        all_map = lake.get_all_ticker_cnpj()
        assert "PETR4" in all_map

    def test_store_mapping_string_simples(self, lake):
        """Suporta mapeamento simples {ticker: cnpj_string}."""
        mapping = {"PETR4": "33.000.167/0001-01"}
        count = lake.store_ticker_cnpj(mapping, source="cvm")
        assert count == 1


# ============================================================================
# Informações Gerais
# ============================================================================


class TestInfo:
    def test_count_records_vazio(self, lake):
        counts = lake.count_records()
        assert all(v == 0 for v in counts.values())
        assert "index_compositions" in counts
        assert "focus_expectations" in counts
        assert "analyst_targets" in counts
        assert "major_holders" in counts
        assert "fund_registry" in counts
        assert "fund_portfolios" in counts
        assert "intermediaries" in counts
        assert "asset_registry" in counts


# ============================================================================
# Major Holders
# ============================================================================


class TestMajorHolders:
    def test_store_e_get_holders(self, lake):
        holders = {
            "insiders_pct": 5.2,
            "institutions_pct": 62.4,
            "institution_count": 320,
            "top_holders": [{"name": "BlackRock", "pct": 8.1}],
        }
        count = lake.store_major_holders("PETR4", holders, source="yahoo")
        assert count == 1

        result = lake.get_major_holders("PETR4")
        assert result is not None
        assert result["insiders_pct"] == 5.2
        assert result["institutions_pct"] == 62.4
        assert isinstance(result["top_holders"], list)

    def test_get_holders_inexistente(self, lake):
        assert lake.get_major_holders("XPTO") is None

    def test_store_holders_vazio(self, lake):
        assert lake.store_major_holders("PETR4", {}) == 0

    def test_top_holders_json_string(self, lake):
        """Aceita top_holders como string JSON pré-serializada."""
        import json

        holders = {
            "insiders_pct": 1.0,
            "institutions_pct": 50.0,
            "top_holders": json.dumps([{"name": "Vanguard", "pct": 5.0}]),
        }
        lake.store_major_holders("VALE3", holders, source="yahoo")
        result = lake.get_major_holders("VALE3")
        assert isinstance(result["top_holders"], list)


# ============================================================================
# Cadastro de Fundos
# ============================================================================


class TestFundRegistry:
    def test_store_e_get_fundos(self, lake):
        funds = [
            {
                "cnpj": "11.111.111/0001-11",
                "name": "Fundo XYZ",
                "fund_type": "FIA",
                "manager": "Gestora ABC",
                "situation": "EM FUNCIONAMENTO NORMAL",
            },
            {
                "cnpj": "22.222.222/0001-22",
                "name": "FII ABC11",
                "fund_type": "FII",
                "manager": "Gestora XYZ",
                "situation": "EM FUNCIONAMENTO NORMAL",
            },
        ]
        count = lake.store_fund_registry(funds, source="cvm")
        assert count == 2

        result = lake.get_fund_registry(fund_type="FII")
        assert len(result) == 1
        assert "ABC11" in result.iloc[0]["name"]

    def test_store_fund_registry_df(self, lake):
        df = pd.DataFrame(
            {
                "cnpj": ["33.333.333/0001-33"],
                "name": ["Fundo Teste"],
                "fund_type": ["FIM"],
                "situation": ["EM FUNCIONAMENTO NORMAL"],
            }
        )
        count = lake.store_fund_registry(df, source="cvm")
        assert count == 1

    def test_store_fund_registry_vazio(self, lake):
        assert lake.store_fund_registry([], source="cvm") == 0


# ============================================================================
# Composição de Carteiras de Fundos
# ============================================================================


class TestFundPortfolios:
    def test_store_e_get_portfolio(self, lake):
        df = pd.DataFrame(
            {
                "asset": ["PETR4", "VALE3", "LFT 2026"],
                "asset_type": ["acao", "acao", "titulo_publico"],
                "weight": [25.0, 20.0, 55.0],
                "value": [1000000.0, 800000.0, 2200000.0],
            }
        )
        count = lake.store_fund_portfolios(
            "11.111.111/0001-11", df, source="cvm", ref_date="2024-01"
        )
        assert count == 3

        result = lake.get_fund_portfolio("11.111.111/0001-11", ref_date="2024-01")
        assert len(result) == 3

    def test_get_portfolio_mais_recente(self, lake):
        cnpj = "11.111.111/0001-11"
        df1 = pd.DataFrame({"asset": ["PETR4"], "value": [100.0]})
        df2 = pd.DataFrame({"asset": ["VALE3"], "value": [200.0]})
        lake.store_fund_portfolios(cnpj, df1, ref_date="2024-01")
        lake.store_fund_portfolios(cnpj, df2, ref_date="2024-02")

        result = lake.get_fund_portfolio(cnpj)
        assert result.iloc[0]["asset"] == "VALE3"

    def test_store_portfolio_vazio(self, lake):
        assert lake.store_fund_portfolios("X", pd.DataFrame()) == 0


# ============================================================================
# Intermediários
# ============================================================================


class TestIntermediaries:
    def test_store_intermediarios(self, lake):
        data = [
            {
                "cnpj": "44.444.444/0001-44",
                "name": "Corretora XYZ",
                "intermediary_type": "corretora",
                "situation": "autorizado",
            },
        ]
        count = lake.store_intermediaries(data, source="cvm")
        assert count == 1

    def test_store_intermediarios_vazio(self, lake):
        assert lake.store_intermediaries([], source="cvm") == 0

    def test_store_intermediarios_df(self, lake):
        df = pd.DataFrame(
            {
                "cnpj": ["55.555.555/0001-55"],
                "name": ["Distribuidora ABC"],
                "intermediary_type": ["distribuidora"],
                "situation": ["autorizado"],
            }
        )
        count = lake.store_intermediaries(df, source="cvm")
        assert count == 1


# ============================================================================
# Registro de Ativos
# ============================================================================


class TestAssetRegistry:
    def test_store_e_get_acoes(self, lake):
        acoes = [
            {"ticker": "PETR4", "name": "Petrobras", "sector": "Energia"},
            {"ticker": "VALE3", "name": "Vale", "sector": "Mineração"},
        ]
        count = lake.store_asset_registry(
            acoes, asset_type="stock", source="tradingcomdados"
        )
        assert count == 2

        result = lake.get_asset_registry(asset_type="stock")
        assert len(result) == 2
        assert "PETR4" in result["ticker"].values

    def test_store_fiis(self, lake):
        df = pd.DataFrame(
            {
                "ticker": ["HGLG11", "KNRI11"],
                "name": ["CSHG Logística", "Kinea Renda"],
                "sector": ["Logística", "Diversificado"],
            }
        )
        count = lake.store_asset_registry(
            df, asset_type="fii", source="tradingcomdados"
        )
        assert count == 2

    def test_get_todos_assets(self, lake):
        lake.store_asset_registry(
            [{"ticker": "BOVA11", "name": "iShares Ibovespa"}],
            asset_type="etf",
        )
        result = lake.get_asset_registry()
        assert len(result) >= 1
        assert "etf" in result["asset_type"].values

    def test_store_asset_registry_vazio(self, lake):
        assert lake.store_asset_registry([], asset_type="stock") == 0
