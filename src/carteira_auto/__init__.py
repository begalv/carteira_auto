"""
carteira_auto - Sistema de automação e análise de carteiras de investimentos
"""

# Submódulos disponíveis para importação
from carteira_auto import analyzers, cli, config, core, data, utils
from carteira_auto.config import settings

utils.logger.setup_logging()

__version__ = "0.1.0"
__author__ = "Bernardo Galvão"
__email__ = "bgalvaods@gmail.com"

# Importações principais
# ...

# Logger global para o pacote
logger = utils.logger.get_logger(__name__)


__all__ = [
    "analyzers",
    "cli",
    "config",
    "core",
    "data",
    "utils",
]

# Log de inicialização do pacote
logger.debug(f"Pacote carteira_auto v{__version__} inicializado")
logger.debug(f"Ambiente: {settings.ENVIRONMENT}, Debug: {settings.DEBUG}")
