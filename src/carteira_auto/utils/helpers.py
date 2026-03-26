from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

import numpy as np

from carteira_auto.config import constants

if TYPE_CHECKING:
    import pandas as pd

# ============================================================================
# PARSING E FORMATAÇÃO
# ============================================================================


def parse_brl_currency(value: str) -> Decimal:
    """Converte string de moeda BR para Decimal."""
    value = value.replace("R$", "").strip()
    value = value.replace(".", "").replace(",", ".")
    return Decimal(value)


def format_currency(value: float | Decimal | int, symbol: str = "R$") -> str:
    """Formata valor como moeda brasileira."""
    if value is None:
        return f"{symbol} 0,00"

    value_decimal = Decimal(str(value))
    formatted = f"{value_decimal:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{symbol} {formatted}"


def format_percentage(value: float, decimals: int = 2) -> str:
    """Formata porcentagem com sinal."""
    if value is None:
        return "0,00%"

    sign = "+" if value > 0 else "-"
    formatted = f"{abs(value):.{decimals}f}"
    formatted = formatted.replace(".", ",")
    return f"{sign}{formatted}%"


# ============================================================================
# VALIDAÇÃO & SEGURANÇA
# ============================================================================


def validate_ticker(ticker: str) -> tuple[bool, str]:
    """Valida ticker e retorna tipo."""

    for tipo, pattern in constants.VALID_TICKER_PATTERNS.items():
        if re.match(pattern, ticker.upper()):
            return True, tipo
    return False, "INVALID"


# ============================================================================
# DATA E HORA
# ============================================================================


def is_market_open() -> bool:
    """Verifica se o mercado B3 está aberto."""

    now = datetime.now()
    # Verifica se é dia útil (segunda a sexta)
    if now.weekday() >= 5:  # 5 = sábado, 6 = domingo
        return False

    # Verifica horário (10:00 às 17:00)
    open_time = datetime.strptime(constants.MARKET_SESSIONS["B3"][0], "%H:%M").time()
    close_time = datetime.strptime(constants.MARKET_SESSIONS["B3"][1], "%H:%M").time()

    return open_time <= now.time() <= close_time


def days_between_dates(start: date, end: date) -> int:
    """Calcula dias úteis entre duas datas (simplificado)."""
    days = (end - start).days
    # Remove finais de semana (aproximado)
    weekdays = days - (days // 7) * 2
    return max(0, weekdays)


# ============================================================================
# CONVERSÃO DE TAXAS — temporalidade (a.d., a.m., a.a.)
# ============================================================================

# Períodos de composição por unidade temporal
_PERIODS_PER_YEAR: dict[str, int] = {
    "a.d.": 252,  # dias úteis / ano (convenção BCB/B3)
    "a.m.": 12,  # meses / ano
    "a.a.": 1,  # já é anual
}

RateUnit = Literal["a.d.", "a.m.", "a.a."]


def convert_rate(
    rate_pct: float,
    from_unit: RateUnit,
    to_unit: RateUnit,
) -> float:
    """Converte taxa entre temporalidades via juros compostos.

    Fórmula base: (1 + r_from)^n_from = (1 + r_to)^n_to
    onde n = número de períodos por ano da respectiva unidade.

    Args:
        rate_pct: Taxa em % (ex: 13.75 para 13,75%).
        from_unit: Unidade de origem ("a.d.", "a.m.", "a.a.").
        to_unit: Unidade de destino ("a.d.", "a.m.", "a.a.").

    Returns:
        Taxa convertida em % na unidade de destino.

    Exemplos:
        >>> convert_rate(13.75, "a.a.", "a.m.")  # Selic 13,75% a.a. → ~1,08% a.m.
        1.0826...
        >>> convert_rate(0.0514, "a.d.", "a.a.")  # CDI 0,0514% a.d. → ~13,8% a.a.
        13.79...
        >>> convert_rate(0.65, "a.m.", "a.a.")    # Poupança 0,65% a.m. → ~8,08% a.a.
        8.085...
    """
    if from_unit == to_unit:
        return rate_pct

    n_from = _PERIODS_PER_YEAR[from_unit]
    n_to = _PERIODS_PER_YEAR[to_unit]

    # (1 + r_from)^n_from = (1 + r_to)^n_to
    # r_to = (1 + r_from)^(n_from / n_to) - 1
    r_decimal = rate_pct / 100
    r_converted = (1 + r_decimal) ** (n_from / n_to) - 1
    return r_converted * 100


def accumulate_rates(
    rates_pct: pd.Series | np.ndarray | list[float],
    unit: RateUnit,
) -> float:
    """Acumula série de taxas via composição (produtório).

    Aplica: ((1 + r1/100) × (1 + r2/100) × ... × (1 + rn/100) - 1) × 100

    Args:
        rates_pct: Série de taxas em % na temporalidade indicada.
        unit: Unidade temporal das taxas ("a.d.", "a.m.", "a.a.").
            Usado apenas para documentação — a composição é a mesma.

    Returns:
        Taxa acumulada total em % (NÃO anualizada).

    Exemplos:
        >>> accumulate_rates([0.042, 0.042, 0.042], "a.d.")  # 3 dias de CDI
        0.12605...
        >>> accumulate_rates([0.38, 0.42, 0.35], "a.m.")  # 3 meses de IPCA
        1.15429...
    """
    factors = np.asarray(rates_pct, dtype=float) / 100 + 1
    return float((factors.prod() - 1) * 100)


def accumulate_and_annualize(
    rates_pct: pd.Series | np.ndarray | list[float],
    unit: RateUnit,
) -> float:
    """Acumula série de taxas e converte para % a.a.

    Primeiro acumula via produtório, depois anualiza pelo número
    de períodos na série vs períodos esperados por ano.

    Args:
        rates_pct: Série de taxas em %.
        unit: Unidade temporal das taxas.

    Returns:
        Taxa anualizada em % a.a.

    Exemplos:
        >>> accumulate_and_annualize([0.042] * 252, "a.d.")  # 1 ano de CDI
        11.14...  # ≈ CDI a.a.
        >>> accumulate_and_annualize([0.5] * 12, "a.m.")     # 12 meses de poupança
        6.167...  # ≈ poupança a.a.
    """
    n_periods = len(np.asarray(rates_pct))
    if n_periods == 0:
        return 0.0

    acum_pct = accumulate_rates(rates_pct, unit)
    periods_per_year = _PERIODS_PER_YEAR[unit]

    # Anualiza: (1 + acum)^(periods_per_year / n_periods) - 1
    years = n_periods / periods_per_year
    if years <= 0:
        return acum_pct

    r_annual = (1 + acum_pct / 100) ** (1 / years) - 1
    return r_annual * 100
