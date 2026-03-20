"""Snapshot Store — persiste métricas em JSON para queries rápidas.

Estrutura:
    data/outputs/snapshots/
        2026-03-20.json
        2026-03-21.json

Cada JSON contém métricas calculadas pelos analyzers,
permitindo construir séries temporais sem abrir planilhas Excel.
"""

import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from carteira_auto.config import settings
from carteira_auto.utils import get_logger

logger = get_logger(__name__)


class SnapshotStore:
    """Armazena e recupera snapshots de métricas em JSON."""

    def __init__(self):
        self.portfolios_dir = settings.paths.PORTFOLIOS_DIR
        self.snapshots_dir = settings.paths.SNAPSHOTS_DIR
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    def save_metadata(
        self,
        data: dict,
        snapshot_date: date | None = None,
    ) -> Path:
        """Salva JSON com métricas do dia.

        Args:
            data: Dict com métricas a persistir.
            snapshot_date: Data do snapshot (default: hoje).

        Returns:
            Path do arquivo JSON salvo.
        """
        if snapshot_date is None:
            snapshot_date = date.today()

        # Adiciona timestamp
        payload = {
            "date": snapshot_date.isoformat(),
            "timestamp": datetime.now().isoformat(),
            **data,
        }

        filepath = self._snapshot_path(snapshot_date)
        filepath.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

        logger.info(f"Snapshot salvo: {filepath}")
        return filepath

    def load_metadata(self, snapshot_date: date) -> dict | None:
        """Lê JSON de uma data específica.

        Args:
            snapshot_date: Data do snapshot.

        Returns:
            Dict com métricas ou None se não existe.
        """
        filepath = self._snapshot_path(snapshot_date)
        if not filepath.exists():
            return None

        return json.loads(filepath.read_text())

    def list_snapshots(self) -> list[date]:
        """Lista datas de snapshots disponíveis.

        Busca tanto em SNAPSHOTS_DIR (JSON) quanto PORTFOLIOS_DIR (Excel).

        Returns:
            Lista de datas ordenadas.
        """
        dates = set()

        # JSONs
        for f in self.snapshots_dir.glob("*.json"):
            try:
                dates.add(date.fromisoformat(f.stem))
            except ValueError:
                continue

        # Planilhas Excel (Carteira_YYYY-MM-DD.xlsx)
        for f in self.portfolios_dir.glob("Carteira_*.xlsx"):
            try:
                date_str = f.stem.replace("Carteira_", "")
                dates.add(date.fromisoformat(date_str))
            except ValueError:
                continue

        return sorted(dates)

    def get_time_series(
        self,
        metric: str,
        start: date | None = None,
        end: date | None = None,
    ) -> pd.DataFrame:
        """Agrega dados dos JSONs em série temporal.

        Args:
            metric: Nome da métrica (ex: "total_value").
            start: Data inicial (default: mais antigo).
            end: Data final (default: mais recente).

        Returns:
            DataFrame com colunas ['date', metric].
        """
        snapshots = self.list_snapshots()

        if start:
            snapshots = [d for d in snapshots if d >= start]
        if end:
            snapshots = [d for d in snapshots if d <= end]

        rows = []
        for d in snapshots:
            data = self.load_metadata(d)
            if data and metric in data:
                rows.append({"date": d, metric: data[metric]})

        if not rows:
            return pd.DataFrame(columns=["date", metric])

        return pd.DataFrame(rows)

    def _snapshot_path(self, snapshot_date: date) -> Path:
        """Retorna path do JSON para uma data."""
        return self.snapshots_dir / f"{snapshot_date.isoformat()}.json"
