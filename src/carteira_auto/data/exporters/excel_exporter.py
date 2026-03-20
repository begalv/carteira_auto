"""Exportador de preços atuais para a planilha da carteira."""

import shutil
from datetime import date
from pathlib import Path
from typing import Optional

from openpyxl import load_workbook

from carteira_auto.config import constants, settings
from carteira_auto.core.models import PortfolioSnapshot
from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import log_execution, timer

logger = get_logger(__name__)

# Índice da coluna "Preço Atual" na aba Carteira (1-based, coluna T = 20)
PRECO_ATUAL_COL = constants.CARTEIRA_COLUMNS.index("Preço Atual") + 1


class ExcelExporter:
    """Exporta preços atuais para a planilha, preservando formatação original."""

    def __init__(
        self,
        source_path: Optional[Path] = None,
        output_path: Optional[Path] = None,
    ):
        self.source_path = source_path or (
            settings.paths.RAW_DATA_DIR / "Carteira 2026.xlsx"
        )
        self.output_path = output_path or (
            settings.paths.PORTFOLIOS_DIR / f"Carteira_{date.today().isoformat()}.xlsx"
        )

    @log_execution
    @timer
    def export_prices(self, snapshot: PortfolioSnapshot) -> Path:
        """Copia a planilha original e atualiza apenas a coluna 'Preço Atual'.

        Returns:
            Path do arquivo exportado.
        """
        if not self.source_path.exists():
            raise FileNotFoundError(
                f"Planilha original não encontrada: {self.source_path}"
            )

        # Garante que o diretório de saída existe
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Copia a planilha original para preservar formatação e fórmulas
        shutil.copy2(self.source_path, self.output_path)

        # Abre a cópia e atualiza preços
        wb = load_workbook(self.output_path)
        sheet_name = constants.SHEET_NAMES["carteira"]

        if sheet_name not in wb.sheetnames:
            raise ValueError(f"Aba '{sheet_name}' não encontrada")

        ws = wb[sheet_name]

        # Monta mapa ticker → preço a partir do snapshot
        price_map = {
            asset.ticker: asset.preco_atual
            for asset in snapshot.assets
            if asset.preco_atual is not None
        }

        if not price_map:
            logger.warning("Nenhum preço atualizado no snapshot")
            wb.close()
            return self.output_path

        # Encontra o índice da coluna Ticker (coluna B = 2)
        ticker_col = constants.CARTEIRA_COLUMNS.index("Ticker") + 1

        updated = 0
        for row in range(2, ws.max_row + 1):
            ticker_cell = ws.cell(row=row, column=ticker_col).value
            if ticker_cell and ticker_cell in price_map:
                price = round(price_map[ticker_cell], 2)
                ws.cell(row=row, column=PRECO_ATUAL_COL, value=price)
                updated += 1

        wb.save(self.output_path)
        wb.close()

        logger.info(
            f"Preços exportados: {updated}/{len(price_map)} ativos atualizados "
            f"em {self.output_path}"
        )
        return self.output_path
