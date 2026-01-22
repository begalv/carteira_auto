"""Sistema de logging personalizado."""

import logging
from logging.handlers import RotatingFileHandler

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

from carteira_auto.config.settings import settings


class CustomLogger:
    """Logger personalizado com suporte a rich."""

    def __init__(self, name: str = "carteira_auto"):
        self.name = name
        self._logger = None
        self._setup_logger()

    def _setup_logger(self) -> None:
        """Configura o logger."""
        # Tema customizado para rich
        custom_theme = Theme(
            {
                "info": "cyan",
                "warning": "yellow",
                "error": "red",
                "critical": "bold red",
                "success": "green",
            }
        )

        # Console rich
        console = Console(theme=custom_theme, stderr=True)

        # Handler do rich
        rich_handler = RichHandler(
            console=console,
            show_time=True,
            show_level=True,
            show_path=True,
            markup=True,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
        )

        # Configuração do logger
        self._logger = logging.getLogger(self.name)
        self._logger.setLevel(getattr(logging, settings.logging.LOG_LEVEL))

        # Remove handlers existentes
        self._logger.handlers.clear()

        # Adiciona handler do rich
        self._logger.addHandler(rich_handler)

        # Adiciona handler de arquivo se configurado
        if settings.logging.LOG_FILE:
            file_handler = RotatingFileHandler(
                settings.logging.LOG_FILE,
                maxBytes=settings.logging.LOG_MAX_SIZE,
                backupCount=5,
                encoding="utf-8",
            )

            file_formatter = logging.Formatter(
                fmt=settings.logging.LOG_FORMAT,
                datefmt=settings.logging.LOG_DATE_FORMAT,
            )

            file_handler.setFormatter(file_formatter)
            self._logger.addHandler(file_handler)

    def info(self, msg: str, *args, **kwargs) -> None:
        """Log nível INFO."""
        self._logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        """Log nível WARNING."""
        self._logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, exc_info: bool = True, **kwargs) -> None:
        """Log nível ERROR."""
        self._logger.error(msg, *args, exc_info=exc_info, **kwargs)

    def critical(self, msg: str, *args, **kwargs) -> None:
        """Log nível CRITICAL."""
        self._logger.critical(msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs) -> None:
        """Log nível DEBUG."""
        self._logger.debug(msg, *args, **kwargs)

    def success(self, msg: str, *args, **kwargs) -> None:
        """Log nível SUCCESS (custom)."""
        self._logger.info(f"[success]✓ {msg}[/success]", *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs) -> None:
        """Log exceção."""
        self._logger.exception(msg, *args, **kwargs)


# Logger global
logger = CustomLogger()
