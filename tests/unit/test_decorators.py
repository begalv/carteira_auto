"""Testes unitários para decorators (carteira_auto.utils.decorators).

Testa @timer, @retry, @timeout, @fallback, @validate_positive_value,
@validate_allocation_sum, @cache_result e @log_execution.
"""

import time
from unittest.mock import MagicMock, patch

import pytest
from carteira_auto.utils.decorators import (
    cache_result,
    fallback,
    log_execution,
    retry,
    timeout,
    timer,
    validate_allocation_sum,
    validate_positive_value,
)

# ============================================================================
# @timer
# ============================================================================


class TestTimer:
    """Testes para o decorator @timer."""

    def test_executa_funcao_e_retorna_resultado(self):
        """@timer executa a função decorada e retorna o resultado correto."""

        @timer
        def soma(a, b):
            return a + b

        resultado = soma(2, 3)
        assert resultado == 5

    def test_preserva_nome_da_funcao(self):
        """@timer preserva o __name__ da função original via functools.wraps."""

        @timer
        def minha_funcao():
            pass

        assert minha_funcao.__name__ == "minha_funcao"


# ============================================================================
# @retry
# ============================================================================


class TestRetry:
    """Testes para o decorator @retry."""

    def test_retry_apos_falhas(self):
        """@retry tenta novamente até max_attempts e levanta exceção final."""
        call_count = 0

        @retry(max_attempts=3, delay=0.01)
        def falha_sempre():
            nonlocal call_count
            call_count += 1
            raise ValueError("Erro proposital")

        with patch("carteira_auto.utils.decorators.time.sleep"):
            with pytest.raises(ValueError, match="Erro proposital"):
                falha_sempre()

        assert call_count == 3

    def test_retry_sucesso_na_segunda_tentativa(self):
        """@retry retorna resultado quando função tem sucesso na 2a tentativa."""
        call_count = 0

        @retry(max_attempts=3, delay=0.01)
        def falha_uma_vez():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Erro temporário")
            return "sucesso"

        with patch("carteira_auto.utils.decorators.time.sleep"):
            resultado = falha_uma_vez()

        assert resultado == "sucesso"
        assert call_count == 2

    def test_retry_sucesso_imediato(self):
        """@retry retorna imediatamente quando não há erro."""

        @retry(max_attempts=3, delay=0.01)
        def funciona():
            return 42

        assert funciona() == 42


# ============================================================================
# @timeout
# ============================================================================


class TestTimeout:
    """Testes para o decorator @timeout."""

    def test_permite_funcao_rapida(self):
        """@timeout permite execução de funções que terminam antes do limite."""

        @timeout(seconds=2)
        def rapida():
            return "ok"

        assert rapida() == "ok"

    def test_timeout_em_funcao_lenta(self):
        """@timeout levanta TimeoutError para funções que excedem o limite."""

        @timeout(seconds=1)
        def lenta():
            time.sleep(5)
            return "nunca retorna"

        with pytest.raises(TimeoutError):
            lenta()


# ============================================================================
# @fallback
# ============================================================================


class TestFallback:
    """Testes para o decorator @fallback."""

    def test_fallback_chamado_em_erro(self):
        """@fallback chama a função alternativa quando a principal falha."""

        def alternativa():
            return "valor_fallback"

        @fallback(alternativa)
        def falha():
            raise RuntimeError("Erro")

        assert falha() == "valor_fallback"

    def test_fallback_nao_chamado_em_sucesso(self):
        """@fallback não é chamado quando a função principal tem sucesso."""
        alternativa = MagicMock(return_value="fallback")

        @fallback(alternativa)
        def funciona():
            return "original"

        assert funciona() == "original"
        alternativa.assert_not_called()

    def test_fallback_recebe_mesmos_args(self):
        """@fallback passa os mesmos argumentos para a função alternativa."""

        def alternativa(x, y):
            return x * y

        @fallback(alternativa)
        def falha(x, y):
            raise ValueError("Erro")

        assert falha(3, 4) == 12


# ============================================================================
# @validate_positive_value
# ============================================================================


class TestValidatePositiveValue:
    """Testes para o decorator @validate_positive_value."""

    def test_aceita_valor_positivo(self):
        """@validate_positive_value permite valores positivos."""

        @validate_positive_value
        def processa(valor):
            return valor * 2

        assert processa(10) == 20

    def test_rejeita_valor_negativo(self):
        """@validate_positive_value levanta ValueError para negativos."""

        @validate_positive_value
        def processa(valor):
            return valor * 2

        with pytest.raises(ValueError, match="Valor negativo não permitido"):
            processa(-5)

    def test_aceita_zero(self):
        """@validate_positive_value permite valor zero."""

        @validate_positive_value
        def processa(valor):
            return valor

        assert processa(0) == 0

    def test_rejeita_kwarg_negativo(self):
        """@validate_positive_value valida kwargs negativos também."""

        @validate_positive_value
        def processa(valor=10):
            return valor

        with pytest.raises(ValueError, match="Valor negativo não permitido"):
            processa(valor=-1)


# ============================================================================
# @validate_allocation_sum
# ============================================================================


class TestValidateAllocationSum:
    """Testes para o decorator @validate_allocation_sum."""

    def test_aceita_soma_igual_a_um(self):
        """@validate_allocation_sum permite alocações que somam 1.0."""

        @validate_allocation_sum
        def processa(alocacoes):
            return alocacoes

        resultado = processa({"PETR4": 0.5, "VALE3": 0.3, "ITUB4": 0.2})
        assert resultado == {"PETR4": 0.5, "VALE3": 0.3, "ITUB4": 0.2}

    def test_rejeita_soma_diferente_de_um(self):
        """@validate_allocation_sum levanta ValueError quando soma != 1.0."""

        @validate_allocation_sum
        def processa(alocacoes):
            return alocacoes

        with pytest.raises(ValueError, match="Soma das alocações deve ser 100%"):
            processa({"PETR4": 0.5, "VALE3": 0.3})

    def test_aceita_soma_dentro_da_tolerancia(self):
        """@validate_allocation_sum aceita soma entre 0.99 e 1.01."""

        @validate_allocation_sum
        def processa(alocacoes):
            return alocacoes

        resultado = processa({"PETR4": 0.505, "VALE3": 0.5})
        assert resultado is not None


# ============================================================================
# @cache_result
# ============================================================================


class TestCacheResult:
    """Testes para o decorator @cache_result."""

    def test_cache_hit(self):
        """@cache_result retorna valor cacheado na segunda chamada."""
        call_count = 0

        @cache_result(ttl_seconds=10)
        def calcula(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        assert calcula(5) == 10
        assert calcula(5) == 10
        assert call_count == 1  # Só chamou a função uma vez

    def test_cache_expira_com_ttl(self):
        """@cache_result invalida cache após TTL expirar."""
        call_count = 0

        @cache_result(ttl_seconds=1)
        def calcula(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        assert calcula(5) == 10
        assert call_count == 1

        # Espera TTL expirar
        time.sleep(1.1)

        assert calcula(5) == 10
        assert call_count == 2  # Função chamada novamente após expiração

    def test_cache_args_diferentes(self):
        """@cache_result diferencia chamadas com argumentos diferentes."""
        call_count = 0

        @cache_result(ttl_seconds=10)
        def calcula(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        assert calcula(5) == 10
        assert calcula(10) == 20
        assert call_count == 2


# ============================================================================
# @log_execution
# ============================================================================


class TestLogExecution:
    """Testes para o decorator @log_execution."""

    def test_loga_e_retorna_resultado(self):
        """@log_execution registra logs e retorna o resultado da função."""

        @log_execution
        def calcula(x, y):
            return x + y

        resultado = calcula(3, 7)
        assert resultado == 10

    def test_preserva_nome_da_funcao(self):
        """@log_execution preserva o __name__ da função original."""

        @log_execution
        def minha_funcao():
            pass

        assert minha_funcao.__name__ == "minha_funcao"

    def test_relanca_excecao_apos_logar(self):
        """@log_execution relança a exceção após registrar o erro no log."""

        @log_execution
        def falha():
            raise RuntimeError("Erro proposital")

        with pytest.raises(RuntimeError, match="Erro proposital"):
            falha()
