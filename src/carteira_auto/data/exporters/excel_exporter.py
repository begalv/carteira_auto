"""Exportadores para planilhas Excel."""

import shutil
from pathlib import Path
from typing import Optional

from openpyxl import load_workbook

from carteira_auto.config import constants, settings
from carteira_auto.core.models import Portfolio
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import log_execution, timer

logger = get_logger(__name__)


class ExcelExporter:
    """Exportador genérico que copia uma planilha e aplica modificações.

    Preserva formatação e fórmulas da planilha original.
    Subclasses implementam a lógica de atualização específica.
    """

    def __init__(self, source_path: Path, output_path: Path):
        self.source_path = source_path
        self.output_path = output_path

    def _copy_and_open(self):
        """Copia a planilha original e abre a cópia para edição."""
        if not self.source_path.exists():
            raise FileNotFoundError(
                f"Planilha original não encontrada: {self.source_path}"
            )
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.source_path, self.output_path)
        return load_workbook(self.output_path)

    def _get_sheet(self, wb, sheet_name: str):
        """Obtém uma aba do workbook, lançando erro se não existir."""
        if sheet_name not in wb.sheetnames:
            raise ValueError(f"Aba '{sheet_name}' não encontrada")
        return wb[sheet_name]


class PortfolioPriceExporter(ExcelExporter):
    """Exporta preços atuais para a planilha da carteira.

    Copia a planilha original e atualiza apenas a coluna 'Preço Atual',
    preservando toda a formatação e fórmulas existentes.

    Usage:
        exporter = PortfolioPriceExporter()  # usa paths padrão de settings
        output = exporter.export_prices(portfolio)

        exporter = PortfolioPriceExporter(
            source_path=Path("minha/planilha.xlsx"),
            output_path=Path("saida/atualizada.xlsx"),
        )
        output = exporter.export_prices(portfolio)
    """

    # Índice da coluna "Preço Atual" na aba Carteira (1-based)
    _PRECO_ATUAL_COL = constants.CARTEIRA_COLUMNS.index("Preço Atual") + 1
    _TICKER_COL = constants.CARTEIRA_COLUMNS.index("Ticker") + 1

    def __init__(
        self,
        source_path: Optional[Path] = None,
        output_path: Optional[Path] = None,
    ):
        src = source_path or settings.paths.PORTFOLIO_FILE
        out = output_path or settings.paths.get_portfolio_output_path()
        super().__init__(src, out)

    @log_execution
    @timer
    def export_prices(self, portfolio: Portfolio) -> Path:
        """Atualiza a coluna 'Preço Atual' com os preços do portfolio.

        Returns:
            Path do arquivo exportado.
        """
        wb = self._copy_and_open()
        ws = self._get_sheet(wb, constants.CARTEIRA_SHEET_NAMES["carteira"])

        price_map = {
            asset.ticker: asset.preco_atual
            for asset in portfolio.assets
            if asset.preco_atual is not None
        }

        if not price_map:
            logger.warning("Nenhum preço atualizado no portfolio")
            wb.close()
            return self.output_path

        updated = 0
        for row in range(2, ws.max_row + 1):
            ticker_cell = ws.cell(row=row, column=self._TICKER_COL).value
            if ticker_cell and ticker_cell in price_map:
                price = round(price_map[ticker_cell], 2)
                ws.cell(row=row, column=self._PRECO_ATUAL_COL, value=price)
                updated += 1

        wb.save(self.output_path)
        wb.close()

        logger.info(
            f"Preços exportados: {updated}/{len(price_map)} ativos "
            f"atualizados em {self.output_path}"
        )
        return self.output_path
