"""Testes unitários para o CLI (carteira_auto.cli.commands).

Testa o parser de argumentos, os comandos run/list/ingest e o entrypoint main().
Todos os acessos a pipeline/engine são mockados.
"""

import argparse
from unittest.mock import MagicMock, patch

import pytest


class TestBuildParser:
    """Testes para build_parser()."""

    def test_retorna_parser_valido(self):
        """build_parser() retorna um ArgumentParser configurado."""
        from carteira_auto.cli.commands import build_parser

        parser = build_parser()
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog == "carteira"

    def test_parse_run_com_dry_run(self):
        """Parsing de 'run pipeline_name --dry-run' funciona corretamente."""
        from carteira_auto.cli.commands import build_parser

        parser = build_parser()
        args = parser.parse_args(["run", "meu_pipeline", "--dry-run"])

        assert args.command == "run"
        assert args.pipeline == "meu_pipeline"
        assert args.dry_run is True

    def test_parse_run_sem_dry_run(self):
        """Parsing de 'run pipeline_name' sem --dry-run."""
        from carteira_auto.cli.commands import build_parser

        parser = build_parser()
        args = parser.parse_args(["run", "meu_pipeline"])

        assert args.command == "run"
        assert args.pipeline == "meu_pipeline"
        assert args.dry_run is False

    def test_parse_run_com_source_e_output(self):
        """Parsing de 'run pipeline -s origem.xlsx -o saida.xlsx'."""
        from carteira_auto.cli.commands import build_parser

        parser = build_parser()
        args = parser.parse_args(
            ["run", "meu_pipeline", "-s", "origem.xlsx", "-o", "saida.xlsx"]
        )

        assert args.source == "origem.xlsx"
        assert args.output == "saida.xlsx"

    def test_parse_list(self):
        """Parsing de 'list' funciona corretamente."""
        from carteira_auto.cli.commands import build_parser

        parser = build_parser()
        args = parser.parse_args(["list"])

        assert args.command == "list"

    def test_parse_ingest_com_mode(self):
        """Parsing de 'ingest --mode daily' funciona corretamente."""
        from carteira_auto.cli.commands import build_parser

        parser = build_parser()
        args = parser.parse_args(["ingest", "--mode", "daily"])

        assert args.command == "ingest"
        assert args.mode == "daily"

    def test_parse_ingest_mode_full(self):
        """Parsing de 'ingest --mode full' funciona corretamente."""
        from carteira_auto.cli.commands import build_parser

        parser = build_parser()
        args = parser.parse_args(["ingest", "--mode", "full"])

        assert args.mode == "full"

    def test_parse_ingest_default_mode(self):
        """Parsing de 'ingest' sem --mode usa 'daily' como padrão."""
        from carteira_auto.cli.commands import build_parser

        parser = build_parser()
        args = parser.parse_args(["ingest"])

        assert args.mode == "daily"

    def test_parse_sem_comando(self):
        """Parsing sem nenhum comando resulta em command=None."""
        from carteira_auto.cli.commands import build_parser

        parser = build_parser()
        args = parser.parse_args([])

        assert args.command is None


class TestRunPipeline:
    """Testes para run_pipeline()."""

    @patch("carteira_auto.cli.commands.get_logger")
    def test_dry_run_imprime_plano(self, mock_get_logger, capsys):
        """run_pipeline com dry_run=True imprime o plano de execução."""
        from carteira_auto.cli.commands import run_pipeline

        mock_engine = MagicMock()
        mock_engine.dry_run.return_value = ["LoadPortfolio", "FetchPrices", "Export"]

        with patch("carteira_auto.cli.commands.get_logger", return_value=MagicMock()):
            # Precisamos fazer o patch dentro do escopo do import lazy
            with patch.dict(
                "sys.modules",
                {},
            ):
                with (
                    patch(
                        "carteira_auto.core.registry.get_terminal_node",
                        return_value="Export",
                    ),
                    patch(
                        "carteira_auto.core.registry.create_engine",
                        return_value=mock_engine,
                    ),
                ):
                    args = argparse.Namespace(
                        pipeline="test_pipeline",
                        dry_run=True,
                        source=None,
                        output=None,
                    )
                    run_pipeline(args)

        captured = capsys.readouterr()
        assert "Plano de execução:" in captured.out
        assert "LoadPortfolio" in captured.out
        assert "FetchPrices" in captured.out
        assert "Export" in captured.out

    @patch("carteira_auto.cli.commands.get_logger")
    def test_run_executa_pipeline(self, mock_get_logger):
        """run_pipeline sem dry_run executa o pipeline via dag_engine.run()."""
        from carteira_auto.cli.commands import run_pipeline

        mock_engine = MagicMock()

        with (
            patch(
                "carteira_auto.core.registry.get_terminal_node",
                return_value="Export",
            ),
            patch(
                "carteira_auto.core.registry.create_engine",
                return_value=mock_engine,
            ),
        ):
            args = argparse.Namespace(
                pipeline="test_pipeline",
                dry_run=False,
                source=None,
                output=None,
            )
            run_pipeline(args)

        mock_engine.run.assert_called_once_with("Export")

    @patch("carteira_auto.cli.commands.get_logger")
    def test_run_key_error_sai_com_codigo_1(self, mock_get_logger):
        """run_pipeline sai com sys.exit(1) quando pipeline não existe."""
        from carteira_auto.cli.commands import run_pipeline

        with (
            patch(
                "carteira_auto.core.registry.get_terminal_node",
                side_effect=KeyError("Pipeline não encontrado"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            args = argparse.Namespace(
                pipeline="inexistente",
                dry_run=False,
                source=None,
                output=None,
            )
            run_pipeline(args)

        assert exc_info.value.code == 1


class TestListPipelinesCmd:
    """Testes para list_pipelines_cmd()."""

    def test_lista_pipelines_disponiveis(self, capsys):
        """list_pipelines_cmd imprime a lista de pipelines."""
        from carteira_auto.cli.commands import list_pipelines_cmd

        mock_pipelines = {
            "update-prices": "Atualiza preços via Yahoo Finance",
            "full-analysis": "Análise completa da carteira",
        }

        with patch(
            "carteira_auto.core.registry.list_pipelines",
            return_value=mock_pipelines,
        ):
            args = argparse.Namespace()
            list_pipelines_cmd(args)

        captured = capsys.readouterr()
        assert "Pipelines disponíveis:" in captured.out
        assert "update-prices" in captured.out
        assert "full-analysis" in captured.out


class TestMain:
    """Testes para main()."""

    def test_main_sem_args_sai_com_zero(self):
        """main() sem argumentos imprime help e sai com código 0."""
        from carteira_auto.cli.commands import main

        with patch("sys.argv", ["carteira"]), pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0

    def test_main_com_comando_list(self):
        """main() com 'list' executa list_pipelines_cmd."""
        from carteira_auto.cli.commands import main

        mock_pipelines = {"test": "Pipeline de teste"}

        with (
            patch("sys.argv", ["carteira", "list"]),
            patch(
                "carteira_auto.core.registry.list_pipelines",
                return_value=mock_pipelines,
            ),
        ):
            main()
