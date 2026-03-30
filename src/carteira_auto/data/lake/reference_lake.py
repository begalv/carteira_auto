"""ReferenceLake — persistência de dados de referência em SQLite.

Armazena dados estruturados não-temporais ou de baixa frequência:
- Composição de índices (IBOV, IFIX, IDIV, SMLL)
- Expectativas Focus do BCB (projeções de Selic, IPCA, PIB)
- Targets de analistas e upgrades/downgrades
- Taxas de crédito por banco e modalidade
- Classificação CNAE
- Mapeamento ticker → CNPJ
- Participação acionária (major holders)
- Cadastro de fundos e FIIs (CVM)
- Composição de carteiras de fundos (CDA)
- Cadastro de intermediários (corretoras/distribuidoras)
- Registro de ativos por tipo (ações, FIIs, BDRs, ETFs)
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from carteira_auto.utils.logger import get_logger

logger = get_logger(__name__)

REFERENCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS index_compositions (
    index_code TEXT NOT NULL,
    ticker TEXT NOT NULL,
    weight REAL,
    date TEXT NOT NULL,
    source TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (index_code, ticker, date)
);
CREATE INDEX IF NOT EXISTS idx_comp_index ON index_compositions(index_code);
CREATE INDEX IF NOT EXISTS idx_comp_date ON index_compositions(date);

CREATE TABLE IF NOT EXISTS focus_expectations (
    indicator TEXT NOT NULL,
    reference_date TEXT NOT NULL,
    target_period TEXT NOT NULL,
    median REAL,
    mean REAL,
    min_value REAL,
    max_value REAL,
    respondents INTEGER,
    source TEXT NOT NULL DEFAULT 'bcb',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (indicator, reference_date, target_period)
);
CREATE INDEX IF NOT EXISTS idx_focus_indicator ON focus_expectations(indicator);
CREATE INDEX IF NOT EXISTS idx_focus_date ON focus_expectations(reference_date);

CREATE TABLE IF NOT EXISTS analyst_targets (
    ticker TEXT NOT NULL,
    target_high REAL,
    target_low REAL,
    target_mean REAL,
    target_median REAL,
    recommendation TEXT,
    num_analysts INTEGER,
    source TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (ticker, source)
);

CREATE TABLE IF NOT EXISTS upgrades_downgrades (
    ticker TEXT NOT NULL,
    date TEXT NOT NULL,
    firm TEXT,
    to_grade TEXT,
    from_grade TEXT,
    action TEXT,
    source TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (ticker, date, firm)
);
CREATE INDEX IF NOT EXISTS idx_upgrades_ticker ON upgrades_downgrades(ticker);

CREATE TABLE IF NOT EXISTS lending_rates (
    modality TEXT NOT NULL,
    bank TEXT NOT NULL DEFAULT '',
    rate REAL NOT NULL,
    date TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'bcb',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (modality, bank, date)
);
CREATE INDEX IF NOT EXISTS idx_lending_date ON lending_rates(date);

CREATE TABLE IF NOT EXISTS cnae_classifications (
    code TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    section TEXT,
    division TEXT,
    level TEXT NOT NULL DEFAULT 'class'
);

CREATE TABLE IF NOT EXISTS ticker_cnpj_map (
    ticker TEXT PRIMARY KEY,
    cnpj TEXT NOT NULL,
    company_name TEXT,
    source TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cnpj ON ticker_cnpj_map(cnpj);

CREATE TABLE IF NOT EXISTS major_holders (
    ticker TEXT NOT NULL,
    insiders_pct REAL,
    institutions_pct REAL,
    institution_count INTEGER,
    top_holders TEXT,
    source TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (ticker, source)
);

CREATE TABLE IF NOT EXISTS fund_registry (
    cnpj TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    fund_type TEXT,
    manager TEXT,
    administrator TEXT,
    inception_date TEXT,
    situation TEXT,
    source TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fund_type ON fund_registry(fund_type);
CREATE INDEX IF NOT EXISTS idx_fund_situation ON fund_registry(situation);

CREATE TABLE IF NOT EXISTS fund_portfolios (
    cnpj TEXT NOT NULL,
    ref_date TEXT NOT NULL,
    asset TEXT NOT NULL,
    asset_type TEXT,
    weight REAL,
    value REAL,
    source TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (cnpj, ref_date, asset)
);
CREATE INDEX IF NOT EXISTS idx_fp_cnpj ON fund_portfolios(cnpj);
CREATE INDEX IF NOT EXISTS idx_fp_date ON fund_portfolios(ref_date);

CREATE TABLE IF NOT EXISTS intermediaries (
    cnpj TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    intermediary_type TEXT,
    situation TEXT,
    source TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_intermediary_type ON intermediaries(intermediary_type);

CREATE TABLE IF NOT EXISTS asset_registry (
    ticker TEXT PRIMARY KEY,
    name TEXT,
    asset_type TEXT NOT NULL,
    sector TEXT,
    segment TEXT,
    source TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_asset_type ON asset_registry(asset_type);
CREATE INDEX IF NOT EXISTS idx_asset_sector ON asset_registry(sector);
"""


class ReferenceLake:
    """Persistência de dados de referência em SQLite.

    Armazena dados estruturados que não são séries temporais puras
    (como composição de índices, targets de analistas, etc.).

    Uso:
        lake = ReferenceLake(Path("data/lake/reference.db"))
        lake.store_index_composition("IBOV", df, source="tradingcomdados")
        ibov = lake.get_index_composition("IBOV")
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
            conn.executescript(REFERENCE_SCHEMA)

    # ================================================================
    # COMPOSIÇÃO DE ÍNDICES
    # ================================================================

    def store_index_composition(
        self,
        index_code: str,
        df: pd.DataFrame,
        source: str,
        ref_date: str | None = None,
    ) -> int:
        """Persiste composição de um índice.

        Args:
            index_code: Código do índice (ex: "IBOV", "IFIX").
            df: DataFrame com colunas [ticker, weight] (weight opcional).
            source: Fonte dos dados (ex: "tradingcomdados", "ddm").
            ref_date: Data de referência. Se None, usa hoje.

        Returns:
            Número de registros inseridos/atualizados.
        """
        if df.empty:
            return 0

        now = datetime.now().isoformat()
        ref_date = ref_date or datetime.now().strftime("%Y-%m-%d")

        rows = []
        for _, row in df.iterrows():
            ticker = str(row.get("ticker", row.get("Ticker", "")))
            weight = float(row.get("weight", row.get("Weight", 0.0)) or 0.0)
            if ticker:
                rows.append((index_code, ticker, weight, ref_date, source, now))

        if not rows:
            return 0

        with self._get_connection() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO index_compositions "
                "(index_code, ticker, weight, date, source, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )

        logger.debug(f"ReferenceLake: {len(rows)} tickers de {index_code} ({source})")
        return len(rows)

    def get_index_composition(
        self,
        index_code: str,
        ref_date: str | None = None,
    ) -> pd.DataFrame:
        """Retorna composição de um índice.

        Args:
            index_code: Código do índice.
            ref_date: Data de referência. Se None, retorna a mais recente.

        Returns:
            DataFrame com colunas [ticker, weight, date, source].
        """
        with self._get_connection() as conn:
            if ref_date:
                df = pd.read_sql_query(
                    "SELECT ticker, weight, date, source FROM index_compositions "
                    "WHERE index_code = ? AND date = ? ORDER BY weight DESC",
                    conn,
                    params=(index_code, ref_date),
                )
            else:
                # Busca a data mais recente
                df = pd.read_sql_query(
                    "SELECT ticker, weight, date, source FROM index_compositions "
                    "WHERE index_code = ? AND date = ("
                    "  SELECT MAX(date) FROM index_compositions WHERE index_code = ?"
                    ") ORDER BY weight DESC",
                    conn,
                    params=(index_code, index_code),
                )
        return df

    def get_available_indexes(self) -> list[str]:
        """Retorna lista de índices disponíveis no lake."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT DISTINCT index_code FROM index_compositions ORDER BY index_code"
            )
            return [row[0] for row in cursor.fetchall()]

    # ================================================================
    # EXPECTATIVAS FOCUS
    # ================================================================

    def store_focus_expectations(
        self,
        indicator: str,
        data: list[dict] | pd.DataFrame,
        source: str = "bcb",
    ) -> int:
        """Persiste expectativas Focus do BCB.

        Args:
            indicator: Nome do indicador (ex: "selic", "ipca", "pib").
            data: Lista de dicts ou DataFrame com campos:
                  reference_date, target_period, median, mean, min_value, max_value, respondents
            source: Fonte dos dados.

        Returns:
            Número de registros inseridos/atualizados.
        """
        if isinstance(data, pd.DataFrame):
            if data.empty:
                return 0
            records = data.to_dict("records")
        elif isinstance(data, list):
            records = data
        else:
            return 0

        if not records:
            return 0

        now = datetime.now().isoformat()
        rows = []
        for rec in records:
            rows.append(
                (
                    indicator,
                    str(rec.get("reference_date", rec.get("Data", ""))),
                    str(rec.get("target_period", rec.get("DataReferencia", ""))),
                    rec.get("median", rec.get("Mediana")),
                    rec.get("mean", rec.get("Media")),
                    rec.get("min_value", rec.get("Minimo")),
                    rec.get("max_value", rec.get("Maximo")),
                    rec.get("respondents", rec.get("numeroRespondentes")),
                    source,
                    now,
                )
            )

        with self._get_connection() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO focus_expectations "
                "(indicator, reference_date, target_period, median, mean, "
                "min_value, max_value, respondents, source, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )

        logger.debug(
            f"ReferenceLake: {len(rows)} expectativas Focus de '{indicator}' ({source})"
        )
        return len(rows)

    def get_focus_expectations(
        self,
        indicator: str,
        limit: int = 100,
    ) -> pd.DataFrame:
        """Retorna expectativas Focus para um indicador.

        Returns:
            DataFrame com colunas [reference_date, target_period, median, mean,
            min_value, max_value, respondents, source].
        """
        with self._get_connection() as conn:
            return pd.read_sql_query(
                "SELECT reference_date, target_period, median, mean, "
                "min_value, max_value, respondents, source "
                "FROM focus_expectations WHERE indicator = ? "
                "ORDER BY reference_date DESC LIMIT ?",
                conn,
                params=(indicator, limit),
            )

    # ================================================================
    # TARGETS DE ANALISTAS
    # ================================================================

    def store_analyst_targets(
        self,
        ticker: str,
        targets: dict,
        source: str = "yahoo",
    ) -> int:
        """Persiste targets de preço de analistas.

        Args:
            ticker: Ticker do ativo.
            targets: Dict com target_high, target_low, target_mean,
                     target_median, recommendation, num_analysts.
            source: Fonte dos dados.

        Returns:
            1 se inserido, 0 se dados vazios.
        """
        if not targets:
            return 0

        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO analyst_targets "
                "(ticker, target_high, target_low, target_mean, target_median, "
                "recommendation, num_analysts, source, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    ticker,
                    targets.get("target_high", targets.get("targetHighPrice")),
                    targets.get("target_low", targets.get("targetLowPrice")),
                    targets.get("target_mean", targets.get("targetMeanPrice")),
                    targets.get("target_median", targets.get("targetMedianPrice")),
                    targets.get("recommendation", targets.get("recommendationKey")),
                    targets.get("num_analysts", targets.get("numberOfAnalystOpinions")),
                    source,
                    now,
                ),
            )
        return 1

    def get_analyst_targets(self, ticker: str) -> dict | None:
        """Retorna targets de analistas para um ticker."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT target_high, target_low, target_mean, target_median, "
                "recommendation, num_analysts, source, updated_at "
                "FROM analyst_targets WHERE ticker = ?",
                (ticker,),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "target_high": row[0],
                    "target_low": row[1],
                    "target_mean": row[2],
                    "target_median": row[3],
                    "recommendation": row[4],
                    "num_analysts": row[5],
                    "source": row[6],
                    "updated_at": row[7],
                }
        return None

    # ================================================================
    # UPGRADES / DOWNGRADES
    # ================================================================

    def store_upgrades_downgrades(
        self,
        ticker: str,
        df: pd.DataFrame,
        source: str = "yahoo",
    ) -> int:
        """Persiste histórico de upgrades/downgrades de analistas.

        Args:
            ticker: Ticker do ativo.
            df: DataFrame com colunas [date, firm, to_grade, from_grade, action].
            source: Fonte dos dados.

        Returns:
            Número de registros inseridos/atualizados.
        """
        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            return 0

        now = datetime.now().isoformat()
        rows = []
        for _, row in df.iterrows():
            rows.append(
                (
                    ticker,
                    str(row.get("date", row.get("GradeDate", ""))),
                    str(row.get("firm", row.get("Firm", ""))),
                    str(row.get("to_grade", row.get("ToGrade", ""))),
                    str(row.get("from_grade", row.get("FromGrade", ""))),
                    str(row.get("action", row.get("Action", ""))),
                    source,
                    now,
                )
            )

        with self._get_connection() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO upgrades_downgrades "
                "(ticker, date, firm, to_grade, from_grade, action, source, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )

        return len(rows)

    # ================================================================
    # TAXAS DE CRÉDITO
    # ================================================================

    def store_lending_rates(
        self,
        data: list[dict] | pd.DataFrame,
        source: str = "bcb",
    ) -> int:
        """Persiste taxas de crédito por modalidade e banco.

        Args:
            data: Lista de dicts ou DataFrame com campos:
                  modality, bank, rate, date.
            source: Fonte dos dados.

        Returns:
            Número de registros inseridos/atualizados.
        """
        if isinstance(data, pd.DataFrame):
            if data.empty:
                return 0
            records = data.to_dict("records")
        elif isinstance(data, list):
            records = data
        else:
            return 0

        if not records:
            return 0

        now = datetime.now().isoformat()
        rows = []
        for rec in records:
            rows.append(
                (
                    str(rec.get("modality", "")),
                    str(rec.get("bank", "")),
                    float(rec.get("rate", 0.0)),
                    str(rec.get("date", "")),
                    source,
                    now,
                )
            )

        with self._get_connection() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO lending_rates "
                "(modality, bank, rate, date, source, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )

        return len(rows)

    # ================================================================
    # CNAE
    # ================================================================

    def store_cnae(self, classifications: list[dict]) -> int:
        """Persiste classificações CNAE.

        Args:
            classifications: Lista de dicts com campos:
                             code, description, section, division, level.

        Returns:
            Número de registros inseridos/atualizados.
        """
        if not classifications:
            return 0

        rows = []
        for cls in classifications:
            rows.append(
                (
                    str(cls.get("code", "")),
                    str(cls.get("description", cls.get("descricao", ""))),
                    cls.get("section", cls.get("secao")),
                    cls.get("division", cls.get("divisao")),
                    str(cls.get("level", "class")),
                )
            )

        with self._get_connection() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO cnae_classifications "
                "(code, description, section, division, level) "
                "VALUES (?, ?, ?, ?, ?)",
                rows,
            )

        return len(rows)

    # ================================================================
    # TICKER → CNPJ
    # ================================================================

    def store_ticker_cnpj(
        self,
        mapping: dict[str, dict],
        source: str,
    ) -> int:
        """Persiste mapeamento ticker → CNPJ.

        Args:
            mapping: Dict {ticker: {"cnpj": "...", "company_name": "..."}}
            source: Fonte dos dados ("ddm" ou "cvm").

        Returns:
            Número de registros inseridos/atualizados.
        """
        if not mapping:
            return 0

        now = datetime.now().isoformat()
        rows = []
        for ticker, info in mapping.items():
            cnpj = info if isinstance(info, str) else info.get("cnpj", "")
            name = "" if isinstance(info, str) else info.get("company_name", "")
            if cnpj:
                rows.append((ticker, cnpj, name, source, now))

        with self._get_connection() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO ticker_cnpj_map "
                "(ticker, cnpj, company_name, source, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                rows,
            )

        return len(rows)

    def get_ticker_cnpj(self, ticker: str) -> str | None:
        """Retorna CNPJ de um ticker."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT cnpj FROM ticker_cnpj_map WHERE ticker = ?",
                (ticker,),
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def get_all_ticker_cnpj(self) -> dict[str, str]:
        """Retorna todo o mapeamento ticker → CNPJ."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT ticker, cnpj FROM ticker_cnpj_map")
            return {row[0]: row[1] for row in cursor.fetchall()}

    # ================================================================
    # MAJOR HOLDERS
    # ================================================================

    def store_major_holders(
        self,
        ticker: str,
        holders: dict,
        source: str = "yahoo",
    ) -> int:
        """Persiste participação acionária de um ticker.

        Args:
            ticker: Ticker do ativo.
            holders: Dict com insiders_pct, institutions_pct, institution_count,
                     top_holders (lista de dicts ou string JSON).
            source: Fonte dos dados.

        Returns:
            1 se inserido, 0 se dados vazios.
        """
        if not holders:
            return 0

        top = holders.get("top_holders")
        if isinstance(top, list):
            top = json.dumps(top)

        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO major_holders "
                "(ticker, insiders_pct, institutions_pct, institution_count, "
                "top_holders, source, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    ticker,
                    holders.get("insiders_pct"),
                    holders.get("institutions_pct"),
                    holders.get("institution_count"),
                    top,
                    source,
                    now,
                ),
            )
        return 1

    def get_major_holders(self, ticker: str) -> dict | None:
        """Retorna participação acionária de um ticker."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT insiders_pct, institutions_pct, institution_count, "
                "top_holders, source, updated_at "
                "FROM major_holders WHERE ticker = ?",
                (ticker,),
            )
            row = cursor.fetchone()
            if row:
                top = row[3]
                if top:
                    try:
                        top = json.loads(top)
                    except (json.JSONDecodeError, TypeError):
                        pass
                return {
                    "insiders_pct": row[0],
                    "institutions_pct": row[1],
                    "institution_count": row[2],
                    "top_holders": top,
                    "source": row[4],
                    "updated_at": row[5],
                }
        return None

    # ================================================================
    # CADASTRO DE FUNDOS
    # ================================================================

    def store_fund_registry(
        self,
        funds: list[dict] | pd.DataFrame,
        source: str = "cvm",
    ) -> int:
        """Persiste cadastro de fundos e FIIs.

        Args:
            funds: Lista de dicts ou DataFrame com campos:
                   cnpj, name, fund_type, manager, administrator,
                   inception_date, situation.
            source: Fonte dos dados.

        Returns:
            Número de registros inseridos/atualizados.
        """
        if isinstance(funds, pd.DataFrame):
            if funds.empty:
                return 0
            records = funds.to_dict("records")
        elif isinstance(funds, list):
            records = funds
        else:
            return 0

        if not records:
            return 0

        now = datetime.now().isoformat()
        rows = []
        for rec in records:
            cnpj = str(rec.get("cnpj", rec.get("CNPJ_FUNDO", "")))
            name = str(rec.get("name", rec.get("DENOM_SOCIAL", "")))
            if cnpj and name:
                rows.append(
                    (
                        cnpj,
                        name,
                        rec.get("fund_type", rec.get("TP_FUNDO")),
                        rec.get("manager", rec.get("NM_GESTOR")),
                        rec.get("administrator", rec.get("NM_ADMIN")),
                        rec.get("inception_date", rec.get("DT_CONST")),
                        rec.get("situation", rec.get("SIT")),
                        source,
                        now,
                    )
                )

        with self._get_connection() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO fund_registry "
                "(cnpj, name, fund_type, manager, administrator, "
                "inception_date, situation, source, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )

        logger.debug(f"ReferenceLake: {len(rows)} fundos registrados ({source})")
        return len(rows)

    def get_fund_registry(
        self,
        fund_type: str | None = None,
        situation: str = "EM FUNCIONAMENTO NORMAL",
    ) -> pd.DataFrame:
        """Retorna cadastro de fundos com filtros opcionais.

        Args:
            fund_type: Tipo de fundo (ex: "FIA", "FII"). None = todos.
            situation: Situação do fundo. None = todos.

        Returns:
            DataFrame com o cadastro de fundos.
        """
        conditions = []
        params: list = []
        if fund_type:
            conditions.append("fund_type = ?")
            params.append(fund_type)
        if situation:
            conditions.append("situation = ?")
            params.append(situation)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self._get_connection() as conn:
            return pd.read_sql_query(
                f"SELECT * FROM fund_registry {where} ORDER BY name",
                conn,
                params=params,
            )

    # ================================================================
    # CARTEIRAS DE FUNDOS (CDA)
    # ================================================================

    def store_fund_portfolios(
        self,
        cnpj: str,
        df: pd.DataFrame,
        source: str = "cvm",
        ref_date: str | None = None,
    ) -> int:
        """Persiste composição de carteira de um fundo (CDA).

        Args:
            cnpj: CNPJ do fundo.
            df: DataFrame com colunas [asset, asset_type, weight, value].
            source: Fonte dos dados.
            ref_date: Data de referência. Se None, usa hoje.

        Returns:
            Número de registros inseridos/atualizados.
        """
        if df.empty:
            return 0

        now = datetime.now().isoformat()
        ref_date = ref_date or datetime.now().strftime("%Y-%m")

        rows = []
        for _, row in df.iterrows():
            asset = str(row.get("asset", row.get("NM_ATIVO", row.get("CD_ATIVO", ""))))
            if asset:
                rows.append(
                    (
                        cnpj,
                        ref_date,
                        asset,
                        row.get("asset_type", row.get("TP_ATIVO")),
                        row.get("weight"),
                        row.get("value", row.get("VL_MERC_POS_FINAL")),
                        source,
                        now,
                    )
                )

        if not rows:
            return 0

        with self._get_connection() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO fund_portfolios "
                "(cnpj, ref_date, asset, asset_type, weight, value, source, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )

        return len(rows)

    def get_fund_portfolio(
        self,
        cnpj: str,
        ref_date: str | None = None,
    ) -> pd.DataFrame:
        """Retorna composição da carteira de um fundo.

        Args:
            cnpj: CNPJ do fundo.
            ref_date: Data de referência. Se None, retorna a mais recente.

        Returns:
            DataFrame com [asset, asset_type, weight, value, ref_date, source].
        """
        with self._get_connection() as conn:
            if ref_date:
                return pd.read_sql_query(
                    "SELECT asset, asset_type, weight, value, ref_date, source "
                    "FROM fund_portfolios WHERE cnpj = ? AND ref_date = ? "
                    "ORDER BY value DESC",
                    conn,
                    params=(cnpj, ref_date),
                )
            return pd.read_sql_query(
                "SELECT asset, asset_type, weight, value, ref_date, source "
                "FROM fund_portfolios WHERE cnpj = ? "
                "AND ref_date = (SELECT MAX(ref_date) FROM fund_portfolios WHERE cnpj = ?) "
                "ORDER BY value DESC",
                conn,
                params=(cnpj, cnpj),
            )

    # ================================================================
    # INTERMEDIÁRIOS (CORRETORAS / DISTRIBUIDORAS)
    # ================================================================

    def store_intermediaries(
        self,
        intermediaries: list[dict] | pd.DataFrame,
        source: str = "cvm",
    ) -> int:
        """Persiste cadastro de intermediários (corretoras e distribuidoras).

        Args:
            intermediaries: Lista de dicts ou DataFrame com campos:
                            cnpj, name, intermediary_type, situation.
            source: Fonte dos dados.

        Returns:
            Número de registros inseridos/atualizados.
        """
        if isinstance(intermediaries, pd.DataFrame):
            if intermediaries.empty:
                return 0
            records = intermediaries.to_dict("records")
        elif isinstance(intermediaries, list):
            records = intermediaries
        else:
            return 0

        if not records:
            return 0

        now = datetime.now().isoformat()
        rows = []
        for rec in records:
            cnpj = str(rec.get("cnpj", ""))
            name = str(rec.get("name", ""))
            if cnpj and name:
                rows.append(
                    (
                        cnpj,
                        name,
                        rec.get("intermediary_type"),
                        rec.get("situation"),
                        source,
                        now,
                    )
                )

        with self._get_connection() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO intermediaries "
                "(cnpj, name, intermediary_type, situation, source, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )

        return len(rows)

    # ================================================================
    # REGISTRO DE ATIVOS (LISTAS POR TIPO)
    # ================================================================

    def store_asset_registry(
        self,
        assets: list[dict] | pd.DataFrame,
        asset_type: str,
        source: str = "tradingcomdados",
    ) -> int:
        """Persiste lista de ativos de um tipo (ações, FIIs, BDRs, ETFs).

        Args:
            assets: Lista de dicts ou DataFrame com campos:
                    ticker, name, sector, segment.
            asset_type: Tipo de ativo ("stock", "fii", "bdr", "etf").
            source: Fonte dos dados.

        Returns:
            Número de registros inseridos/atualizados.
        """
        if isinstance(assets, pd.DataFrame):
            if assets.empty:
                return 0
            records = assets.to_dict("records")
        elif isinstance(assets, list):
            records = assets
        else:
            return 0

        if not records:
            return 0

        now = datetime.now().isoformat()
        rows = []
        for rec in records:
            ticker = str(rec.get("ticker", rec.get("Ticker", rec.get("Papel", ""))))
            if ticker:
                rows.append(
                    (
                        ticker,
                        rec.get("name", rec.get("Nome", rec.get("Empresa"))),
                        asset_type,
                        rec.get("sector", rec.get("Setor")),
                        rec.get("segment", rec.get("Segmento")),
                        source,
                        now,
                    )
                )

        with self._get_connection() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO asset_registry "
                "(ticker, name, asset_type, sector, segment, source, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )

        logger.debug(
            f"ReferenceLake: {len(rows)} ativos do tipo '{asset_type}' ({source})"
        )
        return len(rows)

    def get_asset_registry(
        self,
        asset_type: str | None = None,
    ) -> pd.DataFrame:
        """Retorna registro de ativos com filtro opcional por tipo.

        Args:
            asset_type: "stock", "fii", "bdr", "etf" ou None para todos.

        Returns:
            DataFrame com [ticker, name, asset_type, sector, segment, source].
        """
        with self._get_connection() as conn:
            if asset_type:
                return pd.read_sql_query(
                    "SELECT ticker, name, asset_type, sector, segment, source "
                    "FROM asset_registry WHERE asset_type = ? ORDER BY ticker",
                    conn,
                    params=(asset_type,),
                )
            return pd.read_sql_query(
                "SELECT ticker, name, asset_type, sector, segment, source "
                "FROM asset_registry ORDER BY asset_type, ticker",
                conn,
            )

    # ================================================================
    # INFORMAÇÕES
    # ================================================================

    def count_records(self) -> dict[str, int]:
        """Retorna contagem de registros por tabela."""
        tables = [
            "index_compositions",
            "focus_expectations",
            "analyst_targets",
            "upgrades_downgrades",
            "lending_rates",
            "cnae_classifications",
            "ticker_cnpj_map",
            "major_holders",
            "fund_registry",
            "fund_portfolios",
            "intermediaries",
            "asset_registry",
        ]
        counts = {}
        with self._get_connection() as conn:
            for table in tables:
                cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cursor.fetchone()[0]
        return counts

    def export_to_parquet(self, output_path: Path) -> Path:
        """Exporta todas as tabelas para Parquet.

        Na prática, exporta apenas as tabelas com dados significativos
        (index_compositions e focus_expectations).
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            df = pd.read_sql_query("SELECT * FROM index_compositions", conn)
            if not df.empty:
                idx_path = output_path.with_name("reference_indexes.parquet")
                df.to_parquet(idx_path, index=False)

            df = pd.read_sql_query("SELECT * FROM focus_expectations", conn)
            if not df.empty:
                focus_path = output_path.with_name("reference_focus.parquet")
                df.to_parquet(focus_path, index=False)

        logger.debug(f"ReferenceLake exportado para {output_path.parent}")
        return output_path
