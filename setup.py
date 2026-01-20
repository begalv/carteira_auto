#!/usr/bin/env python
"""Instalação do pacote carteira-investimentos."""

from setuptools import setup, find_packages

# Leitura do README.md
with open("README.md", "r", encoding="utf-8") as fl:
    long_description = fl.read()

# Leitura das dependências
with open("requirements.txt", "r", encoding="utf-8") as fl:
    requirements = [line.strip() for line in fl if line.strip() and not line.startswith("#")]

setup(
    name="carteira_auto",
    version="0.1.0",
    author="Bernardo Galvão",
    author_email="bgalvaods@gmail.com",
    description="Sistema de automação e análise de carteiras de investimentos",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/begalv/carteira_auto",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Office/Business :: Financial :: Investment",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.11.0",
            "pytest-asyncio>=0.21.0",
            "pytest-xdist>=3.3.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
            "pre-commit>=3.3.0",
            "ipython>=8.14.0",
            "jupyter>=1.0.0",
            "jupyterlab>=4.0.0",
            "ipdb>=0.13.0",
            "isort>=5.12.0",
        ],
        "dashboard": [
            "streamlit>=1.28.0",
            "plotly>=5.18.0",
            "dash>=2.14.0",
        ],
        "api": [
            "fastapi>=0.104.0",
            "uvicorn[standard]>=0.24.0",
            "pydantic>=2.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "carteira=carteira_auto.cli.commands:main",
            "carteira-update=carteira_auto.scripts.update_all_prices:main",
        ],
    },
    include_package_data=True,
    package_data={
        "carteira_auto": [
            "data/*.json",
            "data/*.yaml",
            "templates/*.j2",
        ],
    },
)