"""NewsLake — persistência de notícias e scores de sentimento em SQLite.

Armazena headlines financeiras com timestamp, fonte, tickers relacionados
e scores de sentimento para análises de NLP e geopolítica.
"""

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from carteira_auto.utils.logger import get_logger

logger = get_logger(__name__)

NEWS_SCHEMA = """
CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    url TEXT,
    source TEXT NOT NULL,
    published_at TEXT NOT NULL,
    category TEXT,
    tickers TEXT,
    sentiment_score REAL,
    sentiment_label TEXT,
    language TEXT DEFAULT 'pt',
    updated_at TEXT NOT NULL,
    UNIQUE(title, source, published_at)
);

CREATE INDEX IF NOT EXISTS idx_news_published ON news(published_at);
CREATE INDEX IF NOT EXISTS idx_news_source ON news(source);
CREATE INDEX IF NOT EXISTS idx_news_category ON news(category);
CREATE INDEX IF NOT EXISTS idx_news_sentiment ON news(sentiment_score);
"""


class NewsLake:
    """Persistência de notícias e sentimento em SQLite.

    Lê: Headlines de fetchers (NewsAPI, RSS).
    Produz: DataFrames com notícias filtradas e scores de sentimento.

    Uso:
        lake = NewsLake(Path("data/lake/news.db"))
        lake.store(articles, source="newsapi")
        news = lake.get_news(start, end, category="macro")
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
            conn.executescript(NEWS_SCHEMA)

    def store(self, articles: list[dict], source: str) -> int:
        """Persiste lista de artigos/headlines no lake.

        Args:
            articles: Lista de dicts com campos:
                - title (obrigatório)
                - description
                - url
                - published_at (obrigatório, ISO string ou datetime)
                - category
                - tickers (lista de tickers relacionados)
                - sentiment_score (-1.0 a 1.0)
                - sentiment_label ("positive", "negative", "neutral")
                - language
            source: Fonte dos artigos (ex: "newsapi", "rss", "gdelt").

        Returns:
            Número de artigos inseridos.
        """
        if not articles:
            return 0

        now = datetime.now().isoformat()
        rows = []
        for article in articles:
            title = article.get("title")
            published_at = article.get("published_at")
            if not title or not published_at:
                continue

            tickers = article.get("tickers")
            tickers_str = ",".join(tickers) if isinstance(tickers, list) else tickers

            rows.append(
                (
                    title,
                    article.get("description"),
                    article.get("url"),
                    source,
                    self._to_datetime_str(published_at),
                    article.get("category"),
                    tickers_str,
                    article.get("sentiment_score"),
                    article.get("sentiment_label"),
                    article.get("language", "pt"),
                    now,
                )
            )

        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO news
                    (title, description, url, source, published_at, category,
                     tickers, sentiment_score, sentiment_label, language, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            inserted = conn.total_changes

        logger.info(f"NewsLake: {len(rows)} artigos processados da fonte '{source}'")
        return inserted

    def update_sentiment(self, article_id: int, score: float, label: str) -> None:
        """Atualiza score de sentimento de um artigo.

        Args:
            article_id: ID do artigo no lake.
            score: Score de sentimento (-1.0 a 1.0).
            label: Label ("positive", "negative", "neutral").
        """
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE news SET sentiment_score = ?, sentiment_label = ?, updated_at = ? WHERE id = ?",
                (score, label, datetime.now().isoformat(), article_id),
            )

    def get_news(
        self,
        start: Optional[date] = None,
        end: Optional[date] = None,
        category: Optional[str] = None,
        source: Optional[str] = None,
        ticker: Optional[str] = None,
        limit: int = 100,
    ) -> pd.DataFrame:
        """Consulta notícias do lake.

        Args:
            start: Data inicial.
            end: Data final.
            category: Filtro por categoria.
            source: Filtro por fonte.
            ticker: Filtro por ticker mencionado.
            limit: Máximo de resultados.

        Returns:
            DataFrame com notícias ordenadas por data (mais recente primeiro).
        """
        query = "SELECT * FROM news WHERE 1=1"
        params: list = []

        if start:
            query += " AND published_at >= ?"
            params.append(start.isoformat())
        if end:
            query += " AND published_at <= ?"
            params.append(end.isoformat() + "T23:59:59")
        if category:
            query += " AND category = ?"
            params.append(category)
        if source:
            query += " AND source = ?"
            params.append(source)
        if ticker:
            query += " AND tickers LIKE ?"
            params.append(f"%{ticker}%")

        query += " ORDER BY published_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            return pd.read_sql_query(query, conn, params=params)

    def get_sentiment_series(
        self,
        start: Optional[date] = None,
        end: Optional[date] = None,
        category: Optional[str] = None,
    ) -> pd.DataFrame:
        """Retorna série temporal de sentimento agregado diário.

        Returns:
            DataFrame com DatetimeIndex e colunas:
                - mean_sentiment: média diária do score
                - count: número de artigos
                - positive_ratio: proporção de artigos positivos
        """
        query = """
            SELECT
                DATE(published_at) as date,
                AVG(sentiment_score) as mean_sentiment,
                COUNT(*) as count,
                SUM(CASE WHEN sentiment_label = 'positive' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as positive_ratio
            FROM news
            WHERE sentiment_score IS NOT NULL
        """
        params: list = []

        if start:
            query += " AND published_at >= ?"
            params.append(start.isoformat())
        if end:
            query += " AND published_at <= ?"
            params.append(end.isoformat() + "T23:59:59")
        if category:
            query += " AND category = ?"
            params.append(category)

        query += " GROUP BY DATE(published_at) ORDER BY date"

        with self._get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)

        if df.empty:
            return pd.DataFrame(columns=["mean_sentiment", "count", "positive_ratio"])

        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        return df

    def get_unscored_articles(self, limit: int = 50) -> pd.DataFrame:
        """Retorna artigos sem score de sentimento (para processamento NLP).

        Returns:
            DataFrame com artigos que ainda não foram analisados.
        """
        query = """
            SELECT id, title, description, source, published_at, category, tickers
            FROM news
            WHERE sentiment_score IS NULL
            ORDER BY published_at DESC
            LIMIT ?
        """
        with self._get_connection() as conn:
            return pd.read_sql_query(query, conn, params=[limit])

    def count_records(self, source: Optional[str] = None) -> int:
        """Conta artigos no lake."""
        query = "SELECT COUNT(*) FROM news"
        params: list = []
        if source:
            query += " WHERE source = ?"
            params.append(source)

        with self._get_connection() as conn:
            return conn.execute(query, params).fetchone()[0]

    def export_to_parquet(self, output_path: Path) -> Path:
        """Exporta dados para Parquet."""
        with self._get_connection() as conn:
            df = pd.read_sql_query("SELECT * FROM news ORDER BY published_at", conn)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output_path, index=False, engine="pyarrow")
        logger.info(f"NewsLake: exportado {len(df)} artigos para {output_path}")
        return output_path

    @staticmethod
    def _to_datetime_str(value) -> str:
        """Converte valor para string datetime ISO."""
        if isinstance(value, str):
            return value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time()).isoformat()
        return str(value)
