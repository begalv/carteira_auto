"""FundamentalsLake — persistência de dados fundamentalistas em SQLite.

Armazena dados trimestrais de demonstrações financeiras (DRE, Balanço, DFC),
indicadores fundamentalistas (P/L, P/VP, ROE, etc.) e dados de FIIs.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from carteira_auto.utils.logger import get_logger

logger = get_logger(__name__)

FUNDAMENTALS_SCHEMA = """
CREATE TABLE IF NOT EXISTS fundamentals (
    ticker TEXT NOT NULL,
    period TEXT NOT NULL,
    indicator TEXT NOT NULL,
    value REAL,
    source TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (ticker, period, indicator)
);

CREATE INDEX IF NOT EXISTS idx_fund_ticker ON fundamentals(ticker);
CREATE INDEX IF NOT EXISTS idx_fund_period ON fundamentals(period);
CREATE INDEX IF NOT EXISTS idx_fund_indicator ON fundamentals(indicator);

CREATE TABLE IF NOT EXISTS financial_statements (
    ticker TEXT NOT NULL,
    period TEXT NOT NULL,
    statement_type TEXT NOT NULL,
    data TEXT NOT NULL,
    source TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (ticker, period, statement_type)
);

CREATE INDEX IF NOT EXISTS idx_fs_ticker ON financial_statements(ticker);
"""


class FundamentalsLake:
    """Persistência de dados fundamentalistas em SQLite.

    Lê: Dados de fetchers (CVM, Yahoo Finance).
    Produz: DataFrames com indicadores fundamentalistas por ticker e período.

    Uso:
        lake = FundamentalsLake(Path("data/lake/fundamentals.db"))
        lake.store_indicators("PETR4", "2025-Q3", {"pl": 5.2, "pvp": 0.8}, "cvm")
        metrics = lake.get_indicators("PETR4", periods=8)
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
        """Cria tabelas e índices."""
        with self._get_connection() as conn:
            conn.executescript(FUNDAMENTALS_SCHEMA)

    def store_indicators(
        self,
        ticker: str,
        period: str,
        indicators: dict[str, float],
        source: str,
    ) -> int:
        """Persiste indicadores fundamentalistas de um ticker para um período.

        Args:
            ticker: Código do ativo (ex: "PETR4").
            period: Período (ex: "2025-Q3", "2025-12").
            indicators: Dict {nome_indicador: valor}.
            source: Fonte dos dados (ex: "cvm", "yahoo").

        Returns:
            Número de registros inseridos/atualizados.
        """
        if not indicators:
            return 0

        now = datetime.now().isoformat()
        rows = [
            (ticker, period, name, value, source, now)
            for name, value in indicators.items()
            if value is not None and pd.notna(value)
        ]

        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO fundamentals
                    (ticker, period, indicator, value, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

        logger.info(
            f"FundamentalsLake: {len(rows)} indicadores de {ticker}/{period} persistidos"
        )
        return len(rows)

    def store_statement(
        self,
        ticker: str,
        period: str,
        statement_type: str,
        data: dict[str, Any],
        source: str,
    ) -> None:
        """Persiste demonstração financeira completa (DRE, Balanço, DFC).

        Args:
            ticker: Código do ativo.
            period: Período (ex: "2025-Q3").
            statement_type: Tipo ("dre", "balanco", "dfc").
            data: Dict com dados da demonstração.
            source: Fonte dos dados.
        """
        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO financial_statements
                    (ticker, period, statement_type, data, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    ticker,
                    period,
                    statement_type,
                    json.dumps(data, default=str),
                    source,
                    now,
                ),
            )

        logger.debug(
            f"FundamentalsLake: {statement_type} de {ticker}/{period} persistido"
        )

    def get_indicators(
        self,
        ticker: str,
        periods: int = 8,
        indicator_names: Optional[list[str]] = None,
    ) -> pd.DataFrame:
        """Consulta indicadores fundamentalistas de um ticker.

        Args:
            ticker: Código do ativo.
            periods: Número de períodos mais recentes a retornar.
            indicator_names: Lista de indicadores específicos. Se None, todos.

        Returns:
            DataFrame com index=period, columns=indicadores.
        """
        query = "SELECT period, indicator, value FROM fundamentals WHERE ticker = ?"
        params: list = [ticker]

        if indicator_names:
            placeholders = ", ".join(["?"] * len(indicator_names))
            query += f" AND indicator IN ({placeholders})"
            params.extend(indicator_names)

        query += " ORDER BY period DESC"

        with self._get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)

        if df.empty:
            return pd.DataFrame()

        result = df.pivot(index="period", columns="indicator", values="value")
        result = result.sort_index(ascending=False).head(periods)
        return result

    def get_indicator_for_tickers(
        self,
        tickers: list[str],
        indicator_name: str,
        periods: int = 1,
    ) -> pd.DataFrame:
        """Consulta um indicador específico para múltiplos tickers.

        Returns:
            DataFrame com index=ticker, columns=periods.
        """
        if not tickers:
            return pd.DataFrame()

        placeholders = ", ".join(["?"] * len(tickers))
        query = f"""
            SELECT ticker, period, value FROM fundamentals
            WHERE ticker IN ({placeholders}) AND indicator = ?
            ORDER BY period DESC
        """
        params = list(tickers) + [indicator_name]

        with self._get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)

        if df.empty:
            return pd.DataFrame()

        result = df.pivot(index="ticker", columns="period", values="value")
        # Limita a N períodos mais recentes
        if result.shape[1] > periods:
            result = result.iloc[:, :periods]
        return result

    def get_statement(
        self,
        ticker: str,
        period: str,
        statement_type: str,
    ) -> Optional[dict]:
        """Recupera demonstração financeira completa."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT data FROM financial_statements WHERE ticker = ? AND period = ? AND statement_type = ?",
                (ticker, period, statement_type),
            )
            row = cursor.fetchone()
            return json.loads(row[0]) if row else None

    def get_available_tickers(self) -> list[str]:
        """Retorna tickers com dados fundamentalistas disponíveis."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT DISTINCT ticker FROM fundamentals ORDER BY ticker"
            )
            return [row[0] for row in cursor.fetchall()]

    def count_records(self, ticker: Optional[str] = None) -> int:
        """Conta registros no lake."""
        query = "SELECT COUNT(*) FROM fundamentals"
        params: list = []
        if ticker:
            query += " WHERE ticker = ?"
            params.append(ticker)

        with self._get_connection() as conn:
            return conn.execute(query, params).fetchone()[0]

    def export_to_parquet(
        self, output_path: Path, tickers: Optional[list[str]] = None
    ) -> Path:
        """Exporta dados para Parquet."""
        query = "SELECT * FROM fundamentals"
        params: list = []
        if tickers:
            placeholders = ", ".join(["?"] * len(tickers))
            query += f" WHERE ticker IN ({placeholders})"
            params = list(tickers)
        query += " ORDER BY ticker, period"

        with self._get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output_path, index=False, engine="pyarrow")
        logger.info(
            f"FundamentalsLake: exportado {len(df)} registros para {output_path}"
        )
        return output_path
