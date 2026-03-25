"""Interface de linha de comando."""

import argparse
import sys
from pathlib import Path

from carteira_auto import __version__
from carteira_auto.config import settings
from carteira_auto.utils import get_logger

logger = get_logger(__name__)


# ============================================================================
# COMANDOS
# ============================================================================


def run_pipeline(args: argparse.Namespace) -> None:
    """Comando: executa um pipeline via DAG engine."""
    from carteira_auto.core.registry import (
        create_engine,
        get_terminal_node,
    )

    source = Path(args.source) if hasattr(args, "source") and args.source else None
    output = Path(args.output) if hasattr(args, "output") and args.output else None

    try:
        terminal = get_terminal_node(args.pipeline)
        dag_engine = create_engine(source_path=source, output_path=output)

        if args.dry_run:
            plan = dag_engine.dry_run(terminal)
            print("Plano de execução:")
            for i, name in enumerate(plan, 1):
                print(f"  {i}. {name}")
            return

        dag_engine.run(terminal)

    except KeyError as e:
        logger.error(str(e))
        sys.exit(1)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Erro inesperado: {e}", exc_info=True)
        sys.exit(1)


def list_pipelines_cmd(args: argparse.Namespace) -> None:
    """Comando: lista pipelines disponíveis."""
    from carteira_auto.core.registry import list_pipelines

    pipelines = list_pipelines()
    print("Pipelines disponíveis:")
    max_name = max(len(name) for name in pipelines)
    for name, desc in sorted(pipelines.items()):
        print(f"  {name:<{max_name}}  {desc}")


def dashboard_cmd(args: argparse.Namespace) -> None:
    """Comando: abre o dashboard Streamlit."""
    import subprocess

    from carteira_auto.config import settings

    app_path = settings.paths.ROOT_DIR / "dashboards" / "app.py"
    if not app_path.exists():
        logger.error(f"Dashboard não encontrado: {app_path}")
        sys.exit(1)

    print(f"Abrindo dashboard: {app_path}")
    subprocess.run(["streamlit", "run", str(app_path)], check=True)


def ingest_cmd(args: argparse.Namespace) -> None:
    """Comando: ingere dados no DataLake."""
    from carteira_auto.core.engine import PipelineContext
    from carteira_auto.core.nodes.ingest_nodes import (
        IngestFundamentalsNode,
        IngestMacroNode,
        IngestNewsNode,
        IngestPricesNode,
    )
    from carteira_auto.data.lake import DataLake

    mode = args.mode if hasattr(args, "mode") else "daily"
    lake = DataLake(settings.paths.LAKE_DIR)
    ctx = PipelineContext()
    ctx["data_lake"] = lake

    try:
        # Ingestão de preços
        prices_node = IngestPricesNode(mode=mode)
        ctx = prices_node.run(ctx)

        # Ingestão macro
        macro_node = IngestMacroNode()
        ctx = macro_node.run(ctx)

        # Ingestão de fundamentos
        fundamentals_node = IngestFundamentalsNode()
        ctx = fundamentals_node.run(ctx)

        # Ingestão de notícias
        news_node = IngestNewsNode()
        ctx = news_node.run(ctx)

        # Resumo
        summary = lake.summary()
        print("\nDataLake atualizado:")
        print(
            f"  Preços: {summary['prices']['records']} registros, {summary['prices']['tickers']} tickers"
        )
        print(
            f"  Macro: {summary['macro']['records']} registros, {summary['macro']['indicators']} indicadores"
        )
        print(f"  Fundamentos: {summary['fundamentals']['records']} registros")
        print(f"  Notícias: {summary['news']['records']} artigos")

    except Exception as e:
        logger.error(f"Erro na ingestão: {e}", exc_info=True)
        sys.exit(1)


def update_prices(args: argparse.Namespace) -> None:
    """Comando backward-compatible: carteira update-prices."""
    args.pipeline = "update-excel-portfolio-prices"
    args.dry_run = False
    run_pipeline(args)


# ============================================================================
# PARSER
# ============================================================================


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

    # --- run <pipeline> ---
    run_parser = subparsers.add_parser(
        "run",
        help="Executa um pipeline via DAG engine.",
    )
    run_parser.add_argument(
        "pipeline",
        help="Nome do pipeline a executar.",
    )
    run_parser.add_argument(
        "-s",
        "--source",
        help=f"Planilha de origem (default: {settings.paths.PORTFOLIO_FILE})",
    )
    run_parser.add_argument(
        "-o",
        "--output",
        help=(
            f"Planilha de saída (default: "
            f"{settings.paths.PORTFOLIOS_DIR}/Carteira_YYYY-MM-DD.xlsx)"
        ),
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra plano de execução sem executar.",
    )
    run_parser.set_defaults(func=run_pipeline)

    # --- list ---
    list_parser = subparsers.add_parser(
        "list",
        help="Lista pipelines disponíveis.",
    )
    list_parser.set_defaults(func=list_pipelines_cmd)

    # --- dashboard ---
    dash_parser = subparsers.add_parser(
        "dashboard",
        help="Abre o dashboard Streamlit.",
    )
    dash_parser.set_defaults(func=dashboard_cmd)

    # --- ingest ---
    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Ingere dados no DataLake (preços + macro + fundamentos + notícias).",
    )
    ingest_parser.add_argument(
        "--mode",
        choices=["daily", "full"],
        default="daily",
        help="Modo de ingestão: daily (últimos dias) ou full (backfill histórico).",
    )
    ingest_parser.set_defaults(func=ingest_cmd)

    # --- update-prices (backward-compatible alias) ---
    sp = subparsers.add_parser(
        "update-prices",
        help="[Alias] Atualiza preços da carteira via Yahoo Finance.",
    )
    sp.add_argument(
        "-s",
        "--source",
        help=f"Planilha de origem (default: {settings.paths.PORTFOLIO_FILE})",
    )
    sp.add_argument(
        "-o",
        "--output",
        help=(
            f"Planilha de saída (default: "
            f"{settings.paths.PORTFOLIOS_DIR}/Carteira_YYYY-MM-DD.xlsx)"
        ),
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
