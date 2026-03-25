"""Fixtures compartilhadas para testes do carteira_auto."""

from pathlib import Path

import pytest


@pytest.fixture
def tmp_lake_dir(tmp_path: Path) -> Path:
    """Diretório temporário para DataLake (SQLite in-memory não funciona com Path)."""
    lake_dir = tmp_path / "lake"
    lake_dir.mkdir()
    return lake_dir


@pytest.fixture
def tmp_parquet_dir(tmp_path: Path) -> Path:
    """Diretório temporário para exportação Parquet."""
    parquet_dir = tmp_path / "parquet"
    parquet_dir.mkdir()
    return parquet_dir
