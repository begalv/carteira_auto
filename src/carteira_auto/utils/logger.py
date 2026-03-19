"""Sistema de logging modular seguindo melhores práticas."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

from carteira_auto.config.settings import settings


class ErrorFilter(logging.Filter):
    """Filtro para logs de erro (ERROR e CRITICAL)."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= logging.ERROR


class InfoFilter(logging.Filter):
    """Filtro para logs de informação (DEBUG, INFO, WARNING)."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < logging.ERROR


def setup_logging() -> None:
    """Configura o sistema de logging globalmente.

    Esta função deve ser chamada uma vez no início da aplicação.
    """
    # Remove handlers existentes do root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # Configura o nível do root logger
    root_logger.setLevel(logging.WARNING)

    # Configura handlers baseados nas configurações
    handlers = []

    # Handler do console (Rich)
    if settings.logging.LOG_CONSOLE_ENABLED:
        console_handler = _create_console_handler()
        handlers.append(console_handler)

    # Handler de arquivo principal
    if settings.logging.LOG_FILE_ENABLED and settings.logging.LOG_FILE:
        file_handler = _create_file_handler(
            settings.logging.LOG_FILE,
            level=logging.DEBUG if settings.DEBUG else logging.INFO,
            filter_class=InfoFilter if settings.logging.LOG_SEPARATE_ERRORS else None,
        )
        handlers.append(file_handler)

    # Handler de arquivo de erros (separado)
    if (
        settings.logging.LOG_FILE_ENABLED
        and settings.logging.LOG_SEPARATE_ERRORS
        and settings.logging.ERROR_LOG_FILE
    ):
        error_handler = _create_file_handler(
            settings.logging.ERROR_LOG_FILE,
            level=logging.ERROR,
            filter_class=ErrorFilter,
        )
        handlers.append(error_handler)

    # Aplica handlers ao root logger
    for handler in handlers:
        root_logger.addHandler(handler)


def _create_console_handler() -> logging.Handler:
    """Cria handler do console com Rich."""
    # Tema customizado para rich
    custom_theme = Theme(
        {
            "info": "cyan",
            "warning": "yellow",
            "error": "red",
            "critical": "bold red",
            "success": "green",
            "debug": "dim blue",
        }
    )

    console = Console(theme=custom_theme, stderr=True)

    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_level=True,
        show_path=True,
        markup=True,
        rich_tracebacks=True,
        tracebacks_show_locals=settings.DEBUG,
        level=getattr(logging, settings.logging.LOG_LEVEL),
    )

    # Formatter customizado para console
    formatter = logging.Formatter(
        fmt="%(name)s: %(message)s",
        datefmt=settings.logging.LOG_DATE_FORMAT,
    )
    rich_handler.setFormatter(formatter)

    return rich_handler


def _create_file_handler(
    log_file: Path, level: int = logging.INFO, filter_class: Optional[type] = None
) -> logging.Handler:
    """Cria handler de arquivo com rotação."""
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=settings.logging.LOG_MAX_SIZE,
        backupCount=5,
        encoding="utf-8",
    )

    file_handler.setLevel(level)

    # Aplica filtro se especificado
    if filter_class:
        file_handler.addFilter(filter_class())

    # Formatter para arquivo
    formatter = logging.Formatter(
        fmt=settings.logging.LOG_FORMAT,
        datefmt=settings.logging.LOG_DATE_FORMAT,
    )
    file_handler.setFormatter(formatter)

    return file_handler


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Factory function para obter logger configurado.

    Args:
        name: Nome do logger. Se None, retorna o root logger.
              Recomenda-se usar __name__ em cada módulo.

    Returns:
        Logger configurado.

    Exemplo de uso:
        ```python
        # Em cada módulo
        from carteira_auto.utils.logger import get_logger

        logger = get_logger(__name__)
        logger.info("Mensagem informativa")
        ```
    """
    logger_name = name or "carteira_auto"
    logger = logging.getLogger(logger_name)

    # Herda configuração do root logger
    logger.propagate = True

    # Define nível específico se for DEBUG
    if settings.DEBUG:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(getattr(logging, settings.logging.LOG_LEVEL))

    return logger


def initialize_logging(force: bool = False) -> None:
    """Inicializa o sistema de logging.

    Args:
        force: Se True, reconfigura mesmo se já inicializado
    """
    root_logger = logging.getLogger()
    if not force and root_logger.handlers:
        return  # Já inicializado

    setup_logging()
