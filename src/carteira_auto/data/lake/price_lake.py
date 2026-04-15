"""PriceLake — persistência de preços OHLCV em SQLite.

Armazena preços históricos diários de todos os ativos (ações, FIIs, ETFs,
BDRs, commodities, índices, crypto). Suporta consultas por ticker, período
e fonte, além de exportação para Parquet para pipelines de ML.
"""

import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from carteira_auto.utils.logger import get_logger

logger = get_logger(__name__)

# Schema SQL para tabela de preços
PRICES_SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    ticker TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL NOT NULL,
    adj_close REAL,
    volume INTEGER,
    source TEXT DEFAULT 'yahoo',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_prices_ticker ON prices(ticker);
CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date);
CREATE INDEX IF NOT EXISTS idx_prices_source ON prices(source);
"""


class PriceLake:
    """Persistência de preços OHLCV em SQLite.

    Lê: DataFrames com colunas OHLCV de fetchers.
    Produz: DataFrames filtrados por ticker, período e fonte.

    Uso:
        lake = PriceLake(Path("data/lake/prices.db"))
        lake.store(df, source="yahoo")
        prices = lake.get_prices(["PETR4.SA", "VALE3.SA"], start, end)
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Retorna conexão SQLite com WAL mode para melhor concorrência."""
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> None:
        """Cria tabelas e índices se não existirem."""
        with self._get_connection() as conn:
            conn.executescript(PRICES_SCHEMA)

    def store(self, df: pd.DataFrame, source: str = "yahoo") -> int:
        """Persiste preços no lake (upsert por ticker+date).

        Args:
            df: DataFrame com índice DatetimeIndex e colunas por ticker
                (formato wide do yfinance) OU DataFrame long com colunas
                ticker, date, open, high, low, close, volume.
            source: Identificador da fonte dos dados.

        Returns:
            Número de registros inseridos/atualizados.
        """
        if df.empty:
            logger.warning("DataFrame vazio recebido, nada a persistir")
            return 0

        # Normaliza para formato long
        records = self._normalize_to_records(df, source)

        if not records:
            return 0

        now = datetime.now().isoformat()
        rows = [
            (
                r["ticker"],
                r["date"],
                r.get("open"),
                r.get("high"),
                r.get("low"),
                r["close"],
                r.get("adj_close"),
                r.get("volume"),
                source,
                now,
            )
            for r in records
        ]

        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO prices
                    (ticker, date, open, high, low, close, adj_close, volume, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            count = len(rows)

        logger.info(f"PriceLake: {count} registros persistidos (fonte: {source})")
        return count

    def get_prices(
        self,
        tickers: list[str],
        start: date | None = None,
        end: date | None = None,
        columns: list[str] | None = None,
    ) -> pd.DataFrame:
        """Consulta preços do lake.

        Args:
            tickers: Lista de tickers a consultar.
            start: Data inicial (inclusive). Se None, sem limite inferior.
            end: Data final (inclusive). Se None, sem limite superior.
            columns: Colunas a retornar. Default: ["close"].

        Returns:
            DataFrame com DatetimeIndex e colunas por ticker (formato wide).
            Colunas: MultiIndex (column, ticker) se múltiplas colunas,
            ou Index simples de tickers se coluna única.
        """
        if not tickers:
            return pd.DataFrame()

        cols = columns or ["close"]
        col_list = ", ".join(cols)

        placeholders = ", ".join(["?"] * len(tickers))
        query = f"SELECT ticker, date, {col_list} FROM prices WHERE ticker IN ({placeholders})"
        params: list = list(tickers)

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

        # Pivota para formato wide
        if len(cols) == 1:
            result = df.pivot(index="date", columns="ticker", values=cols[0])
        else:
            result = df.set_index(["date", "ticker"]).unstack("ticker")

        result.index.name = "date"
        return result

    def get_latest_prices(self, tickers: list[str]) -> dict[str, float]:
        """Retorna o último preço de fechamento de cada ticker.

        Args:
            tickers: Lista de tickers.

        Returns:
            Dict {ticker: último_preço_close}.
        """
        if not tickers:
            return {}

        placeholders = ", ".join(["?"] * len(tickers))
        query = f"""
            SELECT ticker, close
            FROM prices
            WHERE ticker IN ({placeholders})
            AND date = (
                SELECT MAX(date) FROM prices p2 WHERE p2.ticker = prices.ticker
            )
        """

        with self._get_connection() as conn:
            cursor = conn.execute(query, tickers)
            return {row[0]: row[1] for row in cursor.fetchall()}

    def get_available_tickers(self) -> list[str]:
        """Retorna lista de tickers disponíveis no lake."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT DISTINCT ticker FROM prices ORDER BY ticker")
            return [row[0] for row in cursor.fetchall()]

    def get_date_range(self, ticker: str) -> tuple[date | None, date | None]:
        """Retorna o range de datas disponível para um ticker."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT MIN(date), MAX(date) FROM prices WHERE ticker = ?",
                (ticker,),
            )
            row = cursor.fetchone()
            if row and row[0] and row[1]:
                return date.fromisoformat(row[0]), date.fromisoformat(row[1])
            return None, None

    def count_records(self, ticker: str | None = None) -> int:
        """Conta registros no lake, opcionalmente filtrado por ticker."""
        query = "SELECT COUNT(*) FROM prices"
        params: list = []
        if ticker:
            query += " WHERE ticker = ?"
            params.append(ticker)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchone()[0]

    def delete_ticker(self, ticker: str) -> int:
        """Remove todos os registros de um ticker."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM prices WHERE ticker = ?", (ticker,))
            count = cursor.rowcount
        logger.info(f"PriceLake: {count} registros removidos para {ticker}")
        return count

    def export_to_parquet(
        self, output_path: Path, tickers: list[str] | None = None
    ) -> Path:
        """Exporta dados do lake para Parquet (otimizado para ML).

        Args:
            output_path: Caminho do arquivo .parquet de saída.
            tickers: Lista de tickers a exportar. Se None, exporta todos.

        Returns:
            Path do arquivo criado.
        """
        query = "SELECT * FROM prices"
        params: list = []
        if tickers:
            placeholders = ", ".join(["?"] * len(tickers))
            query += f" WHERE ticker IN ({placeholders})"
            params = list(tickers)
        query += " ORDER BY ticker, date"

        with self._get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output_path, index=False, engine="pyarrow")
        logger.info(f"PriceLake: exportado {len(df)} registros para {output_path}")
        return output_path

    def _normalize_to_records(self, df: pd.DataFrame, source: str) -> list[dict]:
        """Normaliza DataFrame para lista de dicts no formato do schema.

        Suporta dois formatos de entrada:
        1. Wide (yfinance): DatetimeIndex, colunas = tickers, valores = preços
        2. Long: colunas ticker, date, open, high, low, close, volume
        """
        records = []

        # Formato long (tem coluna 'ticker')
        if "ticker" in df.columns:
            for _, row in df.iterrows():
                record = {
                    "ticker": row["ticker"],
                    "date": self._to_date_str(row.get("date", row.name)),
                    "open": row.get("open"),
                    "high": row.get("high"),
                    "low": row.get("low"),
                    "close": row.get("close", row.get("adj_close")),
                    "adj_close": row.get("adj_close"),
                    "volume": row.get("volume"),
                }
                if record["close"] is not None and pd.notna(record["close"]):
                    records.append(record)
            return records

        # Formato wide (yfinance) — índice é data, colunas são tickers ou MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            # MultiIndex: (metric, ticker) — ex: ("Close", "PETR4.SA")
            for metric_ticker in df.columns:
                metric, ticker = metric_ticker
                col_lower = metric.lower().replace(" ", "_")
                if col_lower not in (
                    "open",
                    "high",
                    "low",
                    "close",
                    "adj_close",
                    "volume",
                ):
                    continue
                for idx, val in df[metric_ticker].items():
                    if pd.notna(val):
                        date_str = self._to_date_str(idx)
                        # Busca registro existente ou cria novo
                        existing = next(
                            (
                                r
                                for r in records
                                if r["ticker"] == ticker and r["date"] == date_str
                            ),
                            None,
                        )
                        if existing is None:
                            existing = {"ticker": ticker, "date": date_str}
                            records.append(existing)
                        existing[col_lower] = val
        else:
            # Colunas simples = tickers, valores = preço de fechamento
            for ticker in df.columns:
                for idx, val in df[ticker].items():
                    if pd.notna(val):
                        records.append(
                            {
                                "ticker": ticker,
                                "date": self._to_date_str(idx),
                                "close": val,
                            }
                        )

        # Filtra registros sem close
        return [r for r in records if r.get("close") is not None]

    @staticmethod
    def _to_date_str(value) -> str:
        """Converte valor para string de data ISO."""
        if isinstance(value, str):
            return value[:10]
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, pd.Timestamp):
            return value.date().isoformat()
        return str(value)[:10]
