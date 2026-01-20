"""Configurações globais da aplicação."""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
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
    
    # Arquivos
    TEMPLATE_EXCEL: Path = RAW_DATA_DIR / "Carteira 2026.xlsx"
    
    
    def ensure_directories(self) -> None:
        """Cria todos os diretórios necessários."""
        for dir_path in [
            self.RAW_DATA_DIR,
            self.PROCESSED_DATA_DIR,
            self.OUTPUTS_DIR,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)



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
    def requests_headers(self) -> Dict[str, str]:
        """Headers para requisições ao Yahoo Finance."""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        }



@dataclass
class PortfolioConfig:
    """Configurações da carteira."""
    
    # Moeda padrão
    DEFAULT_CURRENCY: str = "BRL"
    
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
    TARGET_ALLOCATIONS: Dict[str, float] = field(default_factory=lambda: {
        "Renda Fixa": 0.30,
        "Ações": 0.40,
        "FIIs": 0.15,
        "Internacional": 0.10,
        "Cripto": 0.05,
    })



@dataclass
class LoggingConfig:
    """Configurações de logging."""
    
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
    LOG_FILE: Optional[Path] = PathsConfig().OUTPUTS_DIR / "logs" / "app.log"
    
    # Rotação de logs
    LOG_ROTATION: str = "1 day"
    LOG_RETENTION: str = "30 days"
    LOG_MAX_SIZE: str = "10MB"
    
    
    def get_log_config(self) -> Dict[str, Any]:
        """Retorna configuração para logging.dictConfig."""
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": self.LOG_FORMAT,
                    "datefmt": self.LOG_DATE_FORMAT,
                },
                "detailed": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "level": self.LOG_LEVEL,
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "formatter": "detailed",
                    "filename": str(self.LOG_FILE),
                    "maxBytes": 10 * 1024 * 1024,  # 10MB
                    "backupCount": 5,
                    "level": self.LOG_LEVEL,
                },
            },
            "loggers": {
                "carteira_auto": {
                    "handlers": ["console", "file"],
                    "level": self.LOG_LEVEL,
                    "propagate": False,
                },
            },
            "root": {
                "handlers": ["console"],
                "level": "WARNING",
            },
        }



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
    API_KEYS: Dict[str, Optional[str]] = field(default_factory=lambda: {
        "alphavantage": os.getenv("ALPHAVANTAGE_API_KEY"),
        "brapi": os.getenv("BRAPI_API_KEY"),
    })
    
    
    def __post_init__(self):
        """Inicialização pós-criação."""
        # Garante que os diretórios existam
        self.paths.ensure_directories()
        
        # Configura logging
        import logging.config
        logging.config.dictConfig(self.logging.get_log_config())
    
    
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