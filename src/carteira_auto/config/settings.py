"""Configurações globais da aplicação."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()


@dataclass
class PathsConfig:
    """Configurações de caminhos."""

    # Diretórios base
    ROOT_DIR: Path = Path(__file__).parent.parent.parent.parent
    SRC_DIR: Path = ROOT_DIR / "src"
    DATA_DIR: Path = ROOT_DIR / "data"

    # Subdiretórios
    RAW_DATA_DIR: Path = DATA_DIR / "raw"
    PROCESSED_DATA_DIR: Path = DATA_DIR / "processed"
    OUTPUTS_DIR: Path = DATA_DIR / "outputs"
    TEMPLATES_DIR: Path = DATA_DIR / "templates"

    def ensure_directories(self) -> None:
        """Garante que todos os diretórios necessários existam."""
        directories = [
            self.RAW_DATA_DIR,
            self.PROCESSED_DATA_DIR,
            self.OUTPUTS_DIR,
            self.OUTPUTS_DIR / "portfolios",
            self.OUTPUTS_DIR / "reports",
            self.OUTPUTS_DIR / "logs",
            self.TEMPLATES_DIR,
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def get_excel_template_path(self, template_name: str) -> Path:
        """Retorna caminho para arquivo de template."""
        return self.TEMPLATES_DIR / template_name + ".xlsx"

    def get_log_path(self, log_name: str = "carteira_auto") -> Path:
        """Retorna caminho para arquivo de log."""
        return self.OUTPUTS_DIR / "logs" / f"{log_name}.log"


@dataclass
class FetcherConfig:
    """Configurações dos fetchers."""

    # Yahoo Finance
    YAHOO_TIMEOUT: int = 30
    YAHOO_RETRIES: int = 3

    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 3600  # 1 hora

    @property
    def requests_headers(self) -> dict[str, str]:
        """Headers para requisições ao Yahoo Finance."""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        }


@dataclass
class PortfolioConfig:
    """Configurações da carteira."""

    # Arredondamento
    DECIMAL_PLACES: int = 4
    CURRENCY_DECIMAL_PLACES: int = 2

    # Rebalanceamento
    REBALANCE_THRESHOLD: float = 0.05  # 5% de diferença
    MIN_TRADE_VALUE: float = 100.0  # Valor mínimo por operação

    # Impostos
    TAX_RATE_STOCKS: float = 0.15  # 15% para ações
    TAX_RATE_FII: float = 0.20  # 20% para FIIs
    TAX_EXEMPTION: float = 20000.0  # Isenção mensal

    # Metas
    TARGET_ALLOCATIONS: dict[str, float] = field(
        default_factory=lambda: {
            "Caixa": 0.25,
            "FI-Infra": 0.05,
            "Ações": 0.30,
            "FIIs": 0.15,
            "Fiagros": 0.05,
            "Internacional": 0.10,
            "Cripto": 0.05,
            "Commodities": 0.05,
        }
    )


@dataclass
class LoggingConfig:
    """Configurações de logging."""

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

    LOG_FILE: Optional[Path] = None

    # Rotação de logs
    LOG_ROTATION: str = "1 day"
    LOG_RETENTION: str = "30 days"
    LOG_MAX_SIZE: int = (10 * 1024 * 1024,)  # 10MB


@dataclass
class Settings:
    """Configurações globais."""

    # Ambiente
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # Configurações
    paths: PathsConfig = field(default_factory=PathsConfig)
    fetcher: FetcherConfig = field(default_factory=FetcherConfig)
    portfolio: PortfolioConfig = field(default_factory=PortfolioConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    # Segurança
    API_KEYS: dict[str, Optional[str]] = field(
        default_factory=lambda: {
            "ddm": os.getenv("DADOS_MERCADO_API_KEY"),
            "deepseek": os.getenv("DEEPSEEK_API_KEY"),
        }
    )

    def __post_init__(self):
        """Inicialização pós-criação."""

        # Garante que os diretórios existam
        self.paths.ensure_directories()
        # Configura o caminho do arquivo de log
        self.logging.LOG_FILE = self.paths.get_log_file("carteira_auto")

    @property
    def is_production(self) -> bool:
        """Verifica se está em produção."""
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Verifica se está em desenvolvimento."""
        return self.ENVIRONMENT.lower() == "development"


# Instância global das configurações
settings = Settings()
