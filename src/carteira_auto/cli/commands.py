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
        engine = create_engine(source_path=source, output_path=output)

        if args.dry_run:
            plan = engine.dry_run(terminal)
            print("Plano de execução:")
            for i, name in enumerate(plan, 1):
                print(f"  {i}. {name}")
            return

        ctx = engine.run(terminal)

        # Output específico por pipeline
        _print_results(ctx)

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


def _print_results(ctx: dict) -> None:
    """Imprime resultados do pipeline no console."""
    if "output_path" in ctx:
        print(f"Planilha atualizada: {ctx['output_path']}")

    if "portfolio_metrics" in ctx:
        m = ctx["portfolio_metrics"]
        print("\n📊 Métricas da carteira:")
        print(f"  Valor total:  R$ {m.total_value:,.2f}")
        print(f"  Custo total:  R$ {m.total_cost:,.2f}")
        print(f"  Retorno:      {m.total_return_pct:.2%}")
        if m.dividend_yield:
            print(f"  Dividend Yield: {m.dividend_yield:.2%}")
        if m.allocations:
            print("\n  Alocação:")
            for a in m.allocations:
                print(
                    f"    {a.asset_class:<25} "
                    f"atual={a.current_pct:.1%}  "
                    f"meta={a.target_pct:.1%}  "
                    f"desvio={a.deviation:+.1%}  "
                    f"[{a.action}]"
                )

    if "macro_context" in ctx:
        mc = ctx["macro_context"]
        print(f"\n🏦 Macro: {mc.summary}")

    if "market_metrics" in ctx:
        mm = ctx["market_metrics"]
        parts = []
        if mm.ibov_return is not None:
            parts.append(f"IBOV {mm.ibov_return:.2%}")
        if mm.ifix_return is not None:
            parts.append(f"IFIX {mm.ifix_return:.2%}")
        if mm.cdi_return is not None:
            parts.append(f"CDI {mm.cdi_return:.2%}")
        if parts:
            print(f"\n📈 Mercado: {', '.join(parts)}")

    if "risk_metrics" in ctx:
        r = ctx["risk_metrics"]
        parts = []
        if r.volatility is not None:
            parts.append(f"Vol={r.volatility:.2%}")
        if r.sharpe_ratio is not None:
            parts.append(f"Sharpe={r.sharpe_ratio:.2f}")
        if r.max_drawdown is not None:
            parts.append(f"MaxDD={r.max_drawdown:.2%}")
        if r.beta is not None:
            parts.append(f"Beta={r.beta:.2f}")
        if parts:
            print(f"\n⚠️  Risco: {', '.join(parts)}")

    if "rebalance_recommendations" in ctx:
        recs = ctx["rebalance_recommendations"]
        if recs:
            print(f"\n🔄 Rebalanceamento ({len(recs)} recomendações):")
            for rec in recs:
                qty = f" ({rec.quantity:.1f} cotas)" if rec.quantity else ""
                print(
                    f"  {rec.action.upper():<8} {rec.ticker:<10} "
                    f"R$ {rec.value:,.2f}{qty}"
                )


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
