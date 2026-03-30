"""Testes unitários para o helper FetchWithFallback.

Testa hierarquia de fallback, rastreamento de proveniência,
tratamento de erros e dados vazios.
"""

import logging

import pandas as pd
from carteira_auto.core.nodes.fetch_helpers import (
    FetchResult,
    FetchStrategy,
    fetch_with_fallback,
)

# ============================================================================
# Fixtures
# ============================================================================


def _make_df(rows: int = 3) -> pd.DataFrame:
    """Cria DataFrame de teste com dados de série temporal."""
    return pd.DataFrame(
        {
            "data": pd.date_range("2024-01-01", periods=rows),
            "valor": [1.0 + i for i in range(rows)],
        }
    )


def _failing_callable() -> pd.DataFrame:
    """Callable que sempre falha."""
    raise ConnectionError("API indisponível")


def _empty_df_callable() -> pd.DataFrame:
    """Callable que retorna DataFrame vazio."""
    return pd.DataFrame()


def _empty_list_callable() -> list:
    """Callable que retorna lista vazia."""
    return []


def _none_callable() -> None:
    """Callable que retorna None."""
    return None


# ============================================================================
# TestFetchResult
# ============================================================================


class TestFetchResult:
    """Testes do dataclass FetchResult."""

    def test_success_com_dataframe(self):
        result = FetchResult(data=_make_df(), source="bcb")
        assert result.success is True

    def test_success_com_lista(self):
        result = FetchResult(data=[{"a": 1}], source="ddm")
        assert result.success is True

    def test_success_com_dict(self):
        result = FetchResult(data={"key": "val"}, source="yahoo")
        assert result.success is True

    def test_nao_sucesso_com_none(self):
        result = FetchResult(data=None, source="")
        assert result.success is False

    def test_nao_sucesso_com_df_vazio(self):
        result = FetchResult(data=pd.DataFrame(), source="bcb")
        assert result.success is False

    def test_nao_sucesso_com_lista_vazia(self):
        result = FetchResult(data=[], source="ddm")
        assert result.success is False

    def test_used_fallback_false_quando_primaria_sucesso(self):
        result = FetchResult(data=_make_df(), source="bcb", attempts=["bcb"])
        assert result.used_fallback is False

    def test_used_fallback_true_quando_secundaria(self):
        result = FetchResult(data=_make_df(), source="ddm", attempts=["bcb", "ddm"])
        assert result.used_fallback is True


# ============================================================================
# TestFetchWithFallback
# ============================================================================


class TestFetchWithFallback:
    """Testes da função fetch_with_fallback."""

    def test_fonte_primaria_sucesso(self):
        """Fonte primária retorna dados — não tenta fallback."""
        df = _make_df()
        strategies = [
            FetchStrategy(name="bcb", callable=lambda: df),
            FetchStrategy(name="ddm", callable=_failing_callable),
        ]
        result = fetch_with_fallback(strategies)

        assert result.success is True
        assert result.source == "bcb"
        assert result.attempts == ["bcb"]
        assert len(result.errors) == 0

    def test_fallback_quando_primaria_falha(self):
        """Fonte primária falha → usa fallback."""
        df = _make_df()
        strategies = [
            FetchStrategy(name="bcb", callable=_failing_callable),
            FetchStrategy(name="ddm", callable=lambda: df),
        ]
        result = fetch_with_fallback(strategies)

        assert result.success is True
        assert result.source == "ddm"
        assert result.attempts == ["bcb", "ddm"]
        assert "bcb" in result.errors
        assert result.used_fallback is True

    def test_fallback_quando_primaria_retorna_vazio(self):
        """Fonte primária retorna DataFrame vazio → tenta fallback."""
        df = _make_df()
        strategies = [
            FetchStrategy(name="bcb", callable=_empty_df_callable),
            FetchStrategy(name="ddm", callable=lambda: df),
        ]
        result = fetch_with_fallback(strategies)

        assert result.success is True
        assert result.source == "ddm"
        assert result.used_fallback is True

    def test_todas_falham(self):
        """Todas as fontes falham → retorna resultado vazio."""
        strategies = [
            FetchStrategy(name="bcb", callable=_failing_callable),
            FetchStrategy(name="ddm", callable=_failing_callable),
        ]
        result = fetch_with_fallback(strategies)

        assert result.success is False
        assert result.source == ""
        assert result.data is None
        assert result.attempts == ["bcb", "ddm"]
        assert len(result.errors) == 2

    def test_todas_retornam_vazio(self):
        """Todas retornam dados vazios — falha graciosamente."""
        strategies = [
            FetchStrategy(name="bcb", callable=_empty_df_callable),
            FetchStrategy(name="ddm", callable=_empty_list_callable),
        ]
        result = fetch_with_fallback(strategies)

        assert result.success is False
        assert result.data is None

    def test_transform_aplicado(self):
        """Transform é aplicado ao resultado do fetch."""
        raw_data = [{"data": "2024-01-01", "valor": 1.0}]

        def transform(data: list) -> pd.DataFrame:
            return pd.DataFrame(data)

        strategies = [
            FetchStrategy(name="ddm", callable=lambda: raw_data, transform=transform),
        ]
        result = fetch_with_fallback(strategies)

        assert result.success is True
        assert isinstance(result.data, pd.DataFrame)
        assert len(result.data) == 1

    def test_transform_falha_tenta_proximo(self):
        """Se o transform falhar, tenta próxima fonte."""
        df = _make_df()

        def bad_transform(data: list) -> pd.DataFrame:
            raise ValueError("Transform falhou")

        strategies = [
            FetchStrategy(
                name="ddm",
                callable=lambda: [{"a": 1}],
                transform=bad_transform,
            ),
            FetchStrategy(name="bcb", callable=lambda: df),
        ]
        result = fetch_with_fallback(strategies)

        assert result.success is True
        assert result.source == "bcb"

    def test_none_retornado_tratado_como_vazio(self):
        """None retornado por callable é tratado como vazio."""
        df = _make_df()
        strategies = [
            FetchStrategy(name="bcb", callable=_none_callable),
            FetchStrategy(name="ddm", callable=lambda: df),
        ]
        result = fetch_with_fallback(strategies)

        assert result.success is True
        assert result.source == "ddm"

    def test_critical_loga_error(self, caplog):
        """Modo critical loga error quando todas falham."""
        strategies = [
            FetchStrategy(name="bcb", callable=_failing_callable),
        ]
        with caplog.at_level(logging.ERROR):
            result = fetch_with_fallback(strategies, critical=True, label="selic")

        assert result.success is False
        assert "TODAS as fontes falharam" in caplog.text
        assert "selic" in caplog.text

    def test_label_aparece_no_log_de_fallback(self, caplog):
        """Label descritivo aparece nas mensagens de log."""
        df = _make_df()
        strategies = [
            FetchStrategy(name="bcb", callable=_failing_callable),
            FetchStrategy(name="ddm", callable=lambda: df),
        ]
        with caplog.at_level(logging.WARNING):
            fetch_with_fallback(strategies, label="ipca")

        assert "ipca" in caplog.text

    def test_estrategia_unica_sucesso(self):
        """Uma única estratégia que funciona."""
        df = _make_df()
        strategies = [FetchStrategy(name="yahoo", callable=lambda: df)]
        result = fetch_with_fallback(strategies)

        assert result.success is True
        assert result.source == "yahoo"
        assert not result.used_fallback

    def test_estrategia_unica_falha(self):
        """Uma única estratégia que falha."""
        strategies = [FetchStrategy(name="yahoo", callable=_failing_callable)]
        result = fetch_with_fallback(strategies)

        assert result.success is False

    def test_lista_vazia_de_strategies(self):
        """Lista vazia de strategies retorna resultado vazio."""
        result = fetch_with_fallback([])

        assert result.success is False
        assert result.data is None
        assert result.attempts == []

    def test_tres_niveis_de_fallback(self):
        """Fallback em 3 níveis: primário → secundário → terciário."""
        df = _make_df()
        strategies = [
            FetchStrategy(name="yahoo", callable=_failing_callable),
            FetchStrategy(name="ddm", callable=_empty_df_callable),
            FetchStrategy(name="tradingcomdados", callable=lambda: df),
        ]
        result = fetch_with_fallback(strategies)

        assert result.success is True
        assert result.source == "tradingcomdados"
        assert result.attempts == ["yahoo", "ddm", "tradingcomdados"]
        assert "yahoo" in result.errors
        assert "ddm" in result.errors
