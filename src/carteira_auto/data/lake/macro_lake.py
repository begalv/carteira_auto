"""MacroLake — persistência de indicadores macroeconômicos em SQLite.

Armazena séries temporais de indicadores macro (BCB, FRED, IBGE, Tesouro)
com metadados de fonte e frequência. Suporta consultas por indicador e
período, além de exportação para Parquet.
"""

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from carteira_auto.utils.logger import get_logger

logger = get_logger(__name__)

MACRO_SCHEMA = """
CREATE TABLE IF NOT EXISTS macro_indicators (
    indicator TEXT NOT NULL,
    date TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT,
    source TEXT NOT NULL,
    frequency TEXT DEFAULT 'daily',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (indicator, date)
);

CREATE INDEX IF NOT EXISTS idx_macro_indicator ON macro_indicators(indicator);
CREATE INDEX IF NOT EXISTS idx_macro_date ON macro_indicators(date);
CREATE INDEX IF NOT EXISTS idx_macro_source ON macro_indicators(source);

CREATE TABLE IF NOT EXISTS macro_metadata (
    indicator TEXT PRIMARY KEY,
    description TEXT,
    unit TEXT,
    source TEXT,
    frequency TEXT,
    last_updated TEXT
);
"""


class MacroLake:
    """Persistência de indicadores macroeconômicos em SQLite.

    Lê: Séries temporais de fetchers (BCB, FRED, IBGE).
    Produz: DataFrames filtrados por indicador e período.

    Uso:
        lake = MacroLake(Path("data/lake/macro.db"))
        lake.store("selic", df, source="bcb", unit="%", frequency="daily")
        selic = lake.get_indicator("selic", start, end)
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Retorna conexão SQLite com WAL mode."""
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_schema(self) -> None:
        """Cria tabelas e índices se não existirem."""
        with self._get_connection() as conn:
            conn.executescript(MACRO_SCHEMA)

    def store(
        self,
        indicator: str,
        df: pd.DataFrame,
        source: str,
        unit: str = "",
        frequency: str = "daily",
    ) -> int:
        """Persiste série de indicador macro no lake.

        Args:
            indicator: Nome do indicador (ex: "selic", "ipca", "fed_funds").
            df: DataFrame com coluna 'value' e índice DatetimeIndex,
                OU DataFrame com colunas 'date' e 'value'.
            source: Fonte dos dados (ex: "bcb", "fred", "ibge").
            unit: Unidade do indicador (ex: "%", "R$", "índice").
            frequency: Frequência dos dados ("daily", "monthly", "quarterly").

        Returns:
            Número de registros inseridos/atualizados.
        """
        if df.empty:
            logger.warning(f"DataFrame vazio para indicador '{indicator}'")
            return 0

        records = self._normalize_records(df, indicator)
        if not records:
            return 0

        now = datetime.now().isoformat()
        rows = [
            (indicator, r["date"], r["value"], unit, source, frequency, now)
            for r in records
        ]

        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO macro_indicators
                    (indicator, date, value, unit, source, frequency, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            # Atualiza metadata
            conn.execute(
                """
                INSERT OR REPLACE INTO macro_metadata
                    (indicator, description, unit, source, frequency, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (indicator, indicator, unit, source, frequency, now),
            )
            count = len(rows)

        logger.info(
            f"MacroLake: {count} registros de '{indicator}' persistidos (fonte: {source})"
        )
        return count

    def get_indicator(
        self,
        indicator: str,
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> pd.DataFrame:
        """Consulta série de um indicador.

        Args:
            indicator: Nome do indicador.
            start: Data inicial (inclusive).
            end: Data final (inclusive).

        Returns:
            DataFrame com DatetimeIndex e coluna 'value'.
        """
        query = "SELECT date, value FROM macro_indicators WHERE indicator = ?"
        params: list = [indicator]

        if start:
            query += " AND date >= ?"
            params.append(start.isoformat())
        if end:
            query += " AND date <= ?"
            params.append(end.isoformat())

        query += " ORDER BY date"

        with self._get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)

        if df.empty:
            return pd.DataFrame(columns=["value"])

        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        return df

    def get_multiple_indicators(
        self,
        indicators: list[str],
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> pd.DataFrame:
        """Consulta múltiplos indicadores em formato wide.

        Returns:
            DataFrame com DatetimeIndex e colunas = nomes dos indicadores.
        """
        if not indicators:
            return pd.DataFrame()

        placeholders = ", ".join(["?"] * len(indicators))
        query = f"SELECT indicator, date, value FROM macro_indicators WHERE indicator IN ({placeholders})"
        params: list = list(indicators)

        if start:
            query += " AND date >= ?"
            params.append(start.isoformat())
        if end:
            query += " AND date <= ?"
            params.append(end.isoformat())

        query += " ORDER BY date"

        with self._get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)

        if df.empty:
            return pd.DataFrame()

        df["date"] = pd.to_datetime(df["date"])
        result = df.pivot(index="date", columns="indicator", values="value")
        return result

    def get_latest_value(self, indicator: str) -> Optional[float]:
        """Retorna o último valor de um indicador."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT value FROM macro_indicators WHERE indicator = ? ORDER BY date DESC LIMIT 1",
                (indicator,),
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def get_available_indicators(self) -> list[dict]:
        """Retorna lista de indicadores disponíveis com metadados."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT indicator, description, unit, source, frequency, last_updated FROM macro_metadata ORDER BY indicator"
            )
            return [
                {
                    "indicator": row[0],
                    "description": row[1],
                    "unit": row[2],
                    "source": row[3],
                    "frequency": row[4],
                    "last_updated": row[5],
                }
                for row in cursor.fetchall()
            ]

    def count_records(self, indicator: Optional[str] = None) -> int:
        """Conta registros no lake."""
        query = "SELECT COUNT(*) FROM macro_indicators"
        params: list = []
        if indicator:
            query += " WHERE indicator = ?"
            params.append(indicator)

        with self._get_connection() as conn:
            return conn.execute(query, params).fetchone()[0]

    def export_to_parquet(
        self, output_path: Path, indicators: Optional[list[str]] = None
    ) -> Path:
        """Exporta dados para Parquet."""
        query = "SELECT * FROM macro_indicators"
        params: list = []
        if indicators:
            placeholders = ", ".join(["?"] * len(indicators))
            query += f" WHERE indicator IN ({placeholders})"
            params = list(indicators)
        query += " ORDER BY indicator, date"

        with self._get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output_path, index=False, engine="pyarrow")
        logger.info(f"MacroLake: exportado {len(df)} registros para {output_path}")
        return output_path

    def _normalize_records(self, df: pd.DataFrame, indicator: str) -> list[dict]:
        """Normaliza DataFrame para lista de registros."""
        records = []

        if "date" in df.columns and "value" in df.columns:
            for _, row in df.iterrows():
                val = row["value"]
                if pd.notna(val):
                    records.append(
                        {
                            "date": self._to_date_str(row["date"]),
                            "value": float(val),
                        }
                    )
        elif "value" in df.columns:
            # Índice é a data
            for idx, row in df.iterrows():
                val = row["value"]
                if pd.notna(val):
                    records.append(
                        {
                            "date": self._to_date_str(idx),
                            "value": float(val),
                        }
                    )
        elif isinstance(df.index, pd.DatetimeIndex):
            # Primeira coluna é o valor
            col = df.columns[0]
            for idx, val in df[col].items():
                if pd.notna(val):
                    records.append(
                        {
                            "date": self._to_date_str(idx),
                            "value": float(val),
                        }
                    )
        else:
            logger.warning(f"Formato de DataFrame não reconhecido para '{indicator}'")

        return records

    @staticmethod
    def _to_date_str(value) -> str:
        """Converte valor para string de data ISO."""
        if isinstance(value, str):
            return value[:10]
        if isinstance(value, (datetime, pd.Timestamp)):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)[:10]
