# DevOps e Fluxo de Desenvolvimento — carteira_auto

> Guia prático de como contribuir, testar, e publicar mudanças no projeto.
> Atualizado em abril/2026 após configuração do CI/CD.

---

## Visão geral

```
Código local → make check → git push → PR → GitHub Actions CI → Review → Squash merge → main
```

O `main` é protegido. Toda mudança entra via Pull Request com CI verde.

---

## 1. Setup inicial (uma vez)

```bash
# Clone e instale
git clone https://github.com/begalv/carteira_auto.git
cd carteira_auto
make install-dev   # pip install -e ".[dev]" + pre-commit install

# Verifique
make check         # deve passar: lint + format + 697 testes
```

---

## 2. Makefile — comandos do dia a dia

| Comando | O que faz | Quando usar |
|---------|-----------|-------------|
| `make test` | Testes unitários (~1.5 min) | Após cada módulo editado |
| `make test-all` | Todos os testes (unit + integration + slow) | Antes de release |
| `make test-cov` | Testes + cobertura HTML (`htmlcov/index.html`) | Para inspecionar cobertura |
| `make lint` | Verifica erros de código (ruff) | Durante desenvolvimento |
| `make format` | Auto-formata (black + ruff --fix) | Quando lint falha por formatação |
| `make format-check` | Verifica formatação sem alterar | Parte do `make check` |
| `make typecheck` | Verificação de tipos (mypy) | Opcional, muitos erros pré-existentes |
| `make check` | **CI local completo** (lint + format + test) | **Antes de todo push** |
| `make clean` | Remove caches e artefatos | Quando algo está estranho |
| `make clean-worktrees` | Limpa worktrees órfãs do Claude Code | Após finalizar sessões |

**Regra de ouro:** se `make check` passa local, o CI vai passar no GitHub.

---

## 3. Branches

### Convenção: `<tipo>/<escopo>-<descricao>`

| Tipo | Quando usar | Exemplo |
|------|-------------|---------|
| `feat/` | Nova funcionalidade | `feat/sprintC1-yahoo-ddm-expansion` |
| `fix/` | Correção de bug | `fix/cvm-404-endpoint` |
| `refactor/` | Reestruturação sem mudar comportamento | `refactor/bcb-modular-package` |
| `test/` | Só testes | `test/analyzers-integration` |
| `docs/` | Só documentação | `docs/api-reference` |
| `chore/` | CI, tooling, config, dependências | `chore/update-ruff` |
| `claude/` | Auto-gerado pelo Claude Code (worktrees) | `claude/<nome-aleatorio>` |

### Criar branch para um sprint

```bash
git checkout main
git pull origin main
git checkout -b feat/sprintC1-yahoo-expansion
```

### Limpar após merge

```bash
git checkout main
git pull
git branch -d feat/sprintC1-yahoo-expansion   # local
make clean-worktrees                            # worktrees órfãs
```

---

## 4. Commits

### Formato: `<tipo>(<escopo>): <descrição em português>`

**Tipos:** `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`, `style`

**Escopos:** `bcb`, `ibge`, `fred`, `yahoo`, `cvm`, `tesouro`, `ddm`, `lake`,
`analyzers`, `models`, `config`, `cli`, `core`, `ci`, `deps`, `data`

### Exemplos

```bash
git commit -m "feat(bcb): adiciona endpoint Expectativas Focus"
git commit -m "fix(ibge): corrige parsing CNAE SIDRA"
git commit -m "test(analyzers): cobertura completa FiscalAnalyzer"
git commit -m "chore(ci): atualiza ruff para v0.15.7"
git commit -m "refactor(lake): migra MacroLake para schema v2"
```

### Regras

- Descrição em **português** (padrão do projeto)
- Máximo **72 caracteres** na primeira linha
- Corpo opcional para explicações longas
- Referencie issues: `Closes #42`
- Claude Code adiciona: `Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>`

---

## 5. Pull Requests

### Criar PR

```bash
# Após commits feitos e make check passando
git push -u origin feat/sprintC1-yahoo-expansion
gh pr create --title "feat(data): Sprint C.1 — Yahoo Fetcher expansion" --body "..."
```

O template de PR (`.github/pull_request_template.md`) preenche automaticamente
o formulário com: resumo, sprint/fase, tipo, entregáveis, checklist de qualidade,
testes e notas.

### Merge

- **Squash merge** é o padrão (um commit limpo no main por PR)
- Branches são **auto-deletadas** após merge
- O CI deve estar verde nos 3 required checks: `Lint (ruff)`, `Format (black)`, `Test`
- mypy falha mas não bloqueia (continue-on-error)

---

## 6. GitHub Actions — CI automático

### Em PRs para main (`.github/workflows/ci.yml`)

| Job | O que verifica | Bloqueia merge? |
|-----|---------------|-----------------|
| Lint (ruff) | Erros de código e import ordering | Sim |
| Format (black) | Formatação do código | Sim |
| Type Check (mypy) | Type hints | Não (continue-on-error) |
| Test | pytest em Python 3.12 (unit, sem slow/integration) | Sim |

### Após merge no main (`.github/workflows/main-tests.yml`)

Roda suite completa de testes + relatório de cobertura (codecov).

### Em tags `v*` (`.github/workflows/release.yml`)

Roda testes + cria Release no GitHub com changelog automático.

### Dependabot (`.github/dependabot.yml`)

Toda segunda-feira verifica vulnerabilidades em:
- Dependências Python (pyproject.toml)
- GitHub Actions usadas nos workflows

Abre PRs automáticos que passam pelo CI. **Nunca atualiza nada sozinho** —
você sempre tem a decisão final.

---

## 7. Fluxo completo de um sprint

```
1. PLANEJAR
   Claude propõe sprint → você aprova

2. CRIAR BRANCH
   git checkout main && git pull
   git checkout -b feat/sprintX-descricao

3. IMPLEMENTAR (loop)
   ┌──────────────────────────┐
   │ Editar código            │
   │ make test (verificar)    │
   │ git commit (incremental) │
   │ Repetir para cada módulo │
   └──────────────────────────┘

4. VERIFICAR LOCALMENTE
   make check

5. PUSH + PR
   git push -u origin feat/sprintX-descricao
   gh pr create

6. CI AUTOMÁTICO
   Verde? → Pronto para merge
   Vermelho? → Corrigir e push novamente

7. REVIEW + MERGE
   Squash merge no main

8. CLEANUP
   git checkout main && git pull
   make clean-worktrees
```

---

## 8. Proteção da branch main (Ruleset)

Configurado em GitHub → Settings → Rules:

- **Require a pull request** (sem push direto no main)
- **Require status checks:** Lint (ruff), Format (black), Test
- **Require branches up to date** antes de merge
- **Block force pushes**
- **Restrict deletions**
- **Auto-delete head branches** após merge

---

## 9. Troubleshooting

### `make check` falha com import errors

```bash
# O PYTHONPATH pode estar errado. O Makefile já configura, mas se rodar pytest direto:
PYTHONPATH=src pytest -m "not slow and not integration" --tb=short -q
```

### ruff reclama de Optional no economic.py

O arquivo `economic.py` usa `Optional[date]` em vez de `date | None` porque
o Pydantic não resolve o tipo quando o campo se chama `date` (nome sombra o tipo).
As regras UP007/UP045 estão ignoradas nesse arquivo via `pyproject.toml`.

### Testes falham com pandas 3.x

O pandas está pinado em `<3.0.0` no `pyproject.toml`. O pandas 3.x é mais
estrito com DataFrames e quebra mocks no test_fiscal_analyzer. Migrar para
pandas 3 será um sprint dedicado.

### CI diz "branch not up to date"

```bash
git checkout feat/minha-branch
git pull origin main   # ou: git rebase main
git push
```

### Dependabot PRs não mergam

Se o Dependabot PR diz "not up to date", comente `@dependabot rebase` no PR.
O Dependabot faz rebase automaticamente e o CI roda de novo.

### Worktrees órfãs acumulando

```bash
make clean-worktrees   # prune + lista órfãos
# Se necessário, deletar manualmente:
rm -rf .claude/worktrees/<nome-orfao>
```
