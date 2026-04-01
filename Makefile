.PHONY: help test test-all test-cov lint format format-check typecheck check install-dev clean clean-worktrees

export PYTHONPATH := src

help: ## Mostra os targets disponíveis
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

test: ## Testes rápidos (unit, sem slow/integration)
	pytest -m "not slow and not integration" --tb=short -q

test-all: ## Todos os testes (incluindo slow e integration)
	pytest --tb=short

test-cov: ## Testes com relatório de cobertura HTML
	pytest -m "not slow" --cov=src/carteira_auto --cov-report=term-missing --cov-report=html --tb=short

lint: ## Verifica erros de código (ruff)
	ruff check src/ tests/

format: ## Auto-formata código (black + ruff fix)
	black src/ tests/
	ruff check --fix src/ tests/

format-check: ## Verifica formatação sem alterar (black --check)
	black --check src/ tests/

typecheck: ## Verificação de tipos (mypy)
	mypy src/carteira_auto/ --ignore-missing-imports

check: lint format-check test ## CI local completo (lint + format + test)

install-dev: ## Setup de desenvolvimento
	pip install -e ".[dev]"
	pre-commit install

clean: ## Remove artefatos de build e teste
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage coverage.xml

clean-worktrees: ## Limpa worktrees órfãos
	git worktree prune
	@echo "Worktrees ativos:"
	@git worktree list
	@echo ""
	@if [ -d .claude/worktrees ]; then \
		orphans=$$(ls -d .claude/worktrees/*/ 2>/dev/null | while read d; do \
			[ ! -f "$$d/.git" ] && echo "$$d"; \
		done); \
		if [ -n "$$orphans" ]; then \
			echo "Diretórios órfãos encontrados:"; \
			echo "$$orphans"; \
		else \
			echo "Nenhum diretório órfão."; \
		fi \
	fi
