"""Result type para tratamento explícito de erros — Ok(value) ou Err(error).

Inspirado no Result do Rust. Permite que analyzers e nodes retornem
resultados tipados sem engolir exceções silenciosamente.

Usage:
    from carteira_auto.core.result import Result, Ok, Err

    def calcular_risco(dados: pd.DataFrame) -> Result[RiskMetrics]:
        try:
            metrics = ...  # cálculo
            return Ok(metrics)
        except Exception as e:
            return Err(str(e), {"traceback": traceback.format_exc()})

    resultado = calcular_risco(df)
    if resultado.is_ok():
        metrics = resultado.unwrap()
    else:
        logger.error(resultado.error)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    """Resultado de sucesso contendo o valor."""

    value: T

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def unwrap(self) -> T:
        """Retorna o valor. Seguro pois é Ok."""
        return self.value

    def unwrap_or(self, default: T) -> T:
        """Retorna o valor (ignora default pois é Ok)."""
        return self.value

    def __repr__(self) -> str:
        return f"Ok({self.value!r})"


@dataclass(frozen=True, slots=True)
class Err(Generic[T]):
    """Resultado de erro contendo mensagem e detalhes opcionais."""

    error: str
    details: dict = field(default_factory=dict)

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    def unwrap(self) -> T:
        """Levanta exceção pois é Err."""
        raise ValueError(f"Chamou unwrap() em Err: {self.error}")

    def unwrap_or(self, default: T) -> T:
        """Retorna o default pois é Err."""
        return default

    def __repr__(self) -> str:
        return f"Err({self.error!r})"


# Type alias para uso nos type hints
Result = Ok[T] | Err[T]
