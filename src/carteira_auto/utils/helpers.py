import re
from datetime import date, datetime
from decimal import Decimal
from typing import Union

from carteira_auto.config import constants

# ============================================================================
# PARSING E FORMATAÇÃO
# ============================================================================


def parse_brl_currency(value: str) -> Decimal:
    """Converte string de moeda BR para Decimal."""
    value = value.replace("R$", "").strip()
    value = value.replace(".", "").replace(",", ".")
    return Decimal(value)


def format_currency(value: Union[float, Decimal, int], symbol: str = "R$") -> str:
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
