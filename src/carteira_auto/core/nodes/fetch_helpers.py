"""Helpers de fallback para IngestNodes.

Orquestra tentativas hierárquicas entre fetchers diferentes,
com logging de warnings e marcação de proveniência nos dados.

Uso típico nos IngestNodes:

    result = fetch_with_fallback(
        strategies=[
            FetchStrategy(name="bcb", callable=lambda: bcb.get_selic()),
            FetchStrategy(name="ddm", callable=lambda: ddm.get_macro_series("selic")),
        ],
        logger=logger,
    )
    if result.data is not None:
        lake.store_macro("selic", result.data, source=result.source)
"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from carteira_auto.utils import get_logger

logger = get_logger(__name__)


@dataclass
class FetchStrategy:
    """Define uma estratégia de fetch para uma fonte de dados.

    Atributos:
        name: Identificador da fonte (ex: "bcb", "ddm", "yahoo").
        callable: Função sem argumentos que retorna os dados.
        transform: Função de normalização pós-fetch (opcional).
            Recebe os dados brutos e retorna dados normalizados.
    """

    name: str
    callable: Callable[[], Any]
    transform: Callable[[Any], Any] | None = None


@dataclass
class FetchResult:
    """Resultado de uma tentativa de fetch com fallback.

    Atributos:
        data: Dados retornados pela fonte (DataFrame, list, dict ou None).
        source: Nome da fonte que retornou os dados (ou "" se nenhuma).
        attempts: Lista ordenada das fontes tentadas.
        errors: Dicionário {nome_fonte: mensagem_de_erro} para fontes que falharam.
    """

    data: pd.DataFrame | list | dict | None = None
    source: str = ""
    attempts: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Retorna True se alguma fonte retornou dados válidos."""
        if self.data is None:
            return False
        if isinstance(self.data, pd.DataFrame):
            return not self.data.empty
        if isinstance(self.data, list | dict):
            return len(self.data) > 0
        return True

    @property
    def used_fallback(self) -> bool:
        """Retorna True se a fonte primária falhou e um fallback foi usado."""
        return len(self.attempts) > 1 and self.success


def _is_empty(data: Any) -> bool:
    """Verifica se os dados retornados estão vazios.

    Considera vazio: None, DataFrame vazio, lista/dict vazio.
    """
    if data is None:
        return True
    if isinstance(data, pd.DataFrame):
        return data.empty
    if isinstance(data, list | dict):
        return len(data) == 0
    return False


def fetch_with_fallback(
    strategies: list[FetchStrategy],
    fetch_logger: Any | None = None,
    critical: bool = False,
    label: str = "",
) -> FetchResult:
    """Executa fetchers em ordem hierárquica até obter dados válidos.

    Tenta cada strategy na ordem fornecida. Ao encontrar dados válidos,
    retorna imediatamente com marcação de proveniência (source).

    Se a fonte primária falhar e um fallback for usado, loga warning.
    Se TODAS as fontes falharem, loga error.

    Parâmetros:
        strategies: Lista ordenada de FetchStrategy (primeiro = maior prioridade).
        fetch_logger: Logger para registrar warnings/errors. Se None, usa logger do módulo.
        critical: Se True e todas falharem, inclui detalhes extras no resultado
            para registro em ctx["_errors"].
        label: Rótulo descritivo do dado sendo buscado (ex: "selic", "ipca").
            Usado nas mensagens de log para identificar qual indicador falhou.

    Retorna:
        FetchResult com os dados (ou None), fonte usada, tentativas e erros.
    """
    log = fetch_logger or logger
    result = FetchResult()
    description = f" [{label}]" if label else ""

    for strategy in strategies:
        result.attempts.append(strategy.name)

        try:
            raw_data = strategy.callable()

            # Aplicar transformação se definida
            if strategy.transform is not None:
                raw_data = strategy.transform(raw_data)

            # Verificar se os dados são válidos (não-vazios)
            if _is_empty(raw_data):
                msg = f"Fonte '{strategy.name}' retornou dados vazios{description}"
                log.debug(msg)
                result.errors[strategy.name] = "Dados vazios"
                continue

            # Sucesso — registrar proveniência
            result.data = raw_data
            result.source = strategy.name

            # Se não é a primeira tentativa, logar fallback
            if len(result.attempts) > 1:
                primary = result.attempts[0]
                log.warning(
                    f"Fallback{description}: '{primary}' falhou, "
                    f"usando '{strategy.name}'"
                )

            return result

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            result.errors[strategy.name] = error_msg
            log.debug(
                f"Fonte '{strategy.name}' falhou{description}: {error_msg}\n"
                f"{traceback.format_exc()}"
            )
            continue

    # Nenhuma fonte retornou dados
    source_names = [s.name for s in strategies]
    if critical:
        log.error(
            f"TODAS as fontes falharam{description}: "
            f"{source_names}. Erros: {result.errors}"
        )
    else:
        log.warning(
            f"Nenhuma fonte retornou dados{description}: "
            f"{source_names}. Erros: {result.errors}"
        )

    return result
