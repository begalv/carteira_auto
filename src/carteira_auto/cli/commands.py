"""Interface de linha de comando."""

import argparse
import sys
from pathlib import Path

from carteira_auto import __version__
from carteira_auto.config import settings
from carteira_auto.utils import get_logger

logger = get_logger(__name__)


def update_prices(args: argparse.Namespace) -> None:
    """Comando: atualiza preços da carteira via Yahoo Finance."""
    from carteira_auto.core.pipelines import UpdatePricesPipeline

    source = Path(args.source) if args.source else None
    output = Path(args.output) if args.output else None

    pipeline = UpdatePricesPipeline(source_path=source, output_path=output)

    try:
        result = pipeline.run()
        print(f"Planilha atualizada: {result}")
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Erro inesperado: {e}", exc_info=True)
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    """Constrói o parser de argumentos."""
    parser = argparse.ArgumentParser(
        prog="carteira",
        description="Automação e análise de carteira de investimentos.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Comandos disponíveis")

    # update-prices
    sp = subparsers.add_parser(
        "update-prices",
        help="Atualiza preços atuais da carteira via Yahoo Finance.",
    )
    sp.add_argument(
        "-s",
        "--source",
        help=f"Planilha de origem (default: {settings.paths.PORTFOLIO_FILE})",
    )
    sp.add_argument(
        "-o",
        "--output",
        help=f"Planilha de saída (default: {settings.paths.PORTFOLIOS_DIR}/Carteira_YYYY-MM-DD.xlsx)",
    )
    sp.set_defaults(func=update_prices)

    return parser


def main() -> None:
    """Entrypoint do CLI."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)
