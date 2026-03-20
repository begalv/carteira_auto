"""Configurações globais da aplicação."""

import os
from dataclasses import dataclass, field
from datetime import date
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

    LOGS_DIR = OUTPUTS_DIR / "logs"
    PORTFOLIOS_DIR = OUTPUTS_DIR / "portfolios"
    REPORTS_DIR = OUTPUTS_DIR / "reports"

    # Planilha principal da carteira
    PORTFOLIO_FILE: Path = RAW_DATA_DIR / "Carteira 2026.xlsx"

    def ensure_directories(self) -> None:
        """Garante que todos os diretórios necessários existam."""
        directories = [
            self.RAW_DATA_DIR,
            self.PROCESSED_DATA_DIR,
            self.OUTPUTS_DIR,
            self.PORTFOLIOS_DIR,
            self.REPORTS_DIR,
            self.LOGS_DIR,
            self.TEMPLATES_DIR,
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def get_portfolio_output_path(self, suffix: str = "") -> Path:
        """Retorna caminho de saída para a planilha atualizada."""
        name = f"Carteira_{date.today().isoformat()}{suffix}.xlsx"
        return self.PORTFOLIOS_DIR / name

    def get_excel_template_path(self, template_name: str) -> Path:
        """Retorna caminho para arquivo de template."""
        return self.TEMPLATES_DIR / template_name + ".xlsx"

    def get_log_path(self, log_name: str = "carteira_auto") -> Path:
        """Retorna caminho para arquivo de log."""
        return self.LOGS_DIR / f"{log_name}.log"


@dataclass
class FetcherConfig:
    """Configurações dos fetchers."""

    # Yahoo Finance
    YAHOO_TIMEOUT: int = 30
    YAHOO_RETRIES: int = 3

    # Rate limiting por minuto
    RATE_LIMIT_REQUESTS: int = 30

    @property
    def requests_headers(self) -> dict[str, str]:
        """Headers para requisições ao Yahoo Finance."""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        }


@dataclass
class BCBConfig:
    """Configurações do fetcher BCB (SGS API)."""

    BASE_URL: str = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
    TIMEOUT: int = 30
    RETRIES: int = 3
    RATE_LIMIT: int = 30  # requests por minuto
    CACHE_TTL: int = 3600  # 1 hora


@dataclass
class IBGEConfig:
    """Configurações do fetcher IBGE (SIDRA API)."""

    BASE_URL: str = "https://apisidra.ibge.gov.br/values"
    TIMEOUT: int = 30
    RETRIES: int = 3
    RATE_LIMIT: int = 30
    CACHE_TTL: int = 7200  # 2 horas (dados mudam pouco)


@dataclass
class DDMConfig:
    """Configurações do fetcher Dados de Mercado."""

    BASE_URL: str = "https://api.dadosdemercado.com.br/v1"
    TIMEOUT: int = 30
    RETRIES: int = 3
    RATE_LIMIT: int = 60
    CACHE_TTL: int = 1800  # 30 minutos


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
            "Renda Fixa": 0.24,
            "Fundos de Investimentos": 0.27,
            "Ações": 0.31,
            "Internacional": 0.18,
        }
    )


@dataclass
class LoggingConfig:
    """Configurações de logging."""

    # Nível de log
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # Formatação
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

    # Estratégia de logging
    LOG_STRATEGY: str = os.getenv("LOG_STRATEGY", "single")
    if LOG_STRATEGY not in ["single", "level"]:
        LOG_STRATEGY = "single"  # Valor padrão

    # Controle de handlers
    LOG_CONSOLE_ENABLED: bool = (
        os.getenv("LOG_CONSOLE_ENABLED", "True").lower() == "true"
    )
    LOG_FILE_ENABLED: bool = os.getenv("LOG_FILE_ENABLED", "True").lower() == "true"
    LOG_SEPARATE_ERRORS: bool = (
        os.getenv("LOG_SEPARATE_ERRORS", "True").lower() == "true"
    )

    LOG_MAX_SIZE: int = 10 * 1024 * 1024  # 10MB

    # Arquivos de log (serão configurados post-init)
    LOG_FILE: Optional[Path] = None
    ERROR_LOG_FILE: Optional[Path] = None


@dataclass
class Settings:
    """Configurações globais."""

    # Ambiente
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # Configurações
    paths: PathsConfig = field(default_factory=PathsConfig)
    fetcher: FetcherConfig = field(default_factory=FetcherConfig)
    bcb: BCBConfig = field(default_factory=BCBConfig)
    ibge: IBGEConfig = field(default_factory=IBGEConfig)
    ddm: DDMConfig = field(default_factory=DDMConfig)
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
        # Configura os caminhos dos arquivos de log
        self._configure_log_paths()

    def _configure_log_paths(self) -> None:
        """Configura os caminhos dos arquivos de log."""
        if self.logging.LOG_FILE_ENABLED:
            if self.logging.LOG_STRATEGY == "single":
                self.logging.LOG_FILE = self.paths.get_log_path("carteira_auto")
                if self.logging.LOG_SEPARATE_ERRORS:
                    self.logging.ERROR_LOG_FILE = self.paths.get_log_path(
                        "carteira_auto_errors"
                    )

            elif self.logging.LOG_STRATEGY == "level":
                self.logging.LOG_FILE = self.paths.get_log_path("carteira_auto_info")
                self.logging.ERROR_LOG_FILE = self.paths.get_log_path(
                    "carteira_auto_errors"
                )

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
