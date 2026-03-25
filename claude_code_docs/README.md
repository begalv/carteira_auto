# Pacote de Documentação — carteira_auto

## Instruções de instalação

Copie os arquivos abaixo para o repositório `carteira_auto` respeitando
a estrutura de diretórios. Todos os paths são relativos à raiz do repo.

### Estrutura a criar

```
carteira_auto/                         ← raiz do repositório
├── CLAUDE.md                          ← SUBSTITUIR o existente
├── .claudeignore                      ← NOVO
├── .claude/
│   ├── settings.json                  ← NOVO
│   └── commands/
│       ├── new-fetcher.md             ← NOVO
│       ├── new-analyzer.md            ← NOVO
│       ├── new-strategy.md            ← NOVO
│       ├── sprint-review.md           ← NOVO
│       └── audit-phase.md             ← NOVO
└── docs/
    ├── plano_implementacao_carteira_auto.md  ← NOVO
    ├── ARCHITECTURE.md                ← NOVO
    ├── PATTERNS.md                    ← NOVO
    ├── DEPENDENCY_GRAPH.mermaid       ← NOVO
    └── adr/
        ├── 001-dag-engine-kahn-algorithm.md         ← NOVO
        ├── 002-strategy-not-a-node.md               ← NOVO
        ├── 003-sqlite-over-postgres.md              ← NOVO
        ├── 004-layered-as-default-composition.md    ← NOVO
        ├── 005-optimization-config-in-config-module.md ← NOVO
        └── 006-ai-never-executes.md                 ← NOVO
```

### Comandos para copiar (ajuste os paths de origem)

```bash
# Na raiz do repositório carteira_auto:

# Criar diretórios
mkdir -p docs/adr .claude/commands

# Copiar arquivos raiz
cp /path/to/CLAUDE.md ./CLAUDE.md
cp /path/to/.claudeignore ./.claudeignore

# Copiar docs
cp /path/to/plano_implementacao_carteira_auto.md docs/
cp /path/to/ARCHITECTURE.md docs/
cp /path/to/PATTERNS.md docs/
cp /path/to/DEPENDENCY_GRAPH.mermaid docs/

# Copiar ADRs
cp /path/to/adr/*.md docs/adr/

# Copiar Claude Code config
cp /path/to/settings.json .claude/
cp /path/to/commands/*.md .claude/commands/

# Commit
git add -A
git commit -m "docs: add complete documentation package for Claude Code co-development

- CLAUDE.md: governance protocol for sprint-based development
- docs/plano_implementacao_carteira_auto.md: 2200-line architectural plan (8 layers, 8 phases)
- docs/ARCHITECTURE.md: compact code map (modules, exports, ctx keys, paths)
- docs/PATTERNS.md: canonical code templates (fetcher, analyzer, strategy, node, model, publisher)
- docs/DEPENDENCY_GRAPH.mermaid: module dependency graph
- docs/adr/: 6 Architecture Decision Records
- .claude/commands/: 5 reusable slash commands (new-fetcher, new-analyzer, new-strategy, sprint-review, audit-phase)
- .claude/settings.json: safe permissions for Claude Code
- .claudeignore: exclude irrelevant files from Claude Code context"
```

### Diagrama de arquitetura (SVGs opcionais)

Os dois diagramas SVG podem ser colocados em `docs/diagrams/` para referência visual:
- `carteira_auto_complete_layer_flow.svg` — Fluxo das 8 camadas
- `carteira_auto_orchestration_feedback.svg` — Loops de feedback e orquestração

## Inventário completo dos artefatos

| # | Arquivo | Linhas | Propósito | Impacto no Claude Code |
|---|---------|--------|-----------|----------------------|
| 1 | `CLAUDE.md` | ~240 | Governança de sprints, protocolo de revisão, infra existente | Lido automaticamente em toda sessão — define o comportamento |
| 2 | `docs/plano_implementacao_carteira_auto.md` | ~2200 | Source of truth: 8 camadas, estratégias, optimizer, AI, publishers | Referência sob demanda — consultado por fase |
| 3 | `docs/ARCHITECTURE.md` | ~120 | Mapa compacto: módulos, exports, ctx keys, pipelines, paths | Elimina ~50% da redescoberta de código por sessão |
| 4 | `docs/PATTERNS.md` | ~200 | Templates canônicos com checklists | Few-shot prompting implícito — consistência de código |
| 5 | `docs/adr/001-006` | ~15 cada | Decisões e razões (DAG, Strategy≠Node, SQLite, Layered, Config, AI) | Impede reversão de decisões já tomadas |
| 6 | `docs/DEPENDENCY_GRAPH.mermaid` | ~60 | Grafo de quem importa quem | Previne imports circulares |
| 7 | `.claudeignore` | ~25 | Exclui .venv, __pycache__, data/, logs do contexto | Reduz ruído, economiza tokens |
| 8 | `.claude/settings.json` | ~25 | Permite pytest/ruff/pip, bloqueia rm -rf/git push | Segurança em modo autônomo |
| 9 | `.claude/commands/` | ~20 cada | 5 workflows reutilizáveis (new-*, sprint-review, audit-phase) | Padroniza operações recorrentes |
| 10 | `*.svg` (2 diagramas) | — | Visualização da arquitetura de camadas e orquestração | Referência visual humana |

## Manutenção

| Artefato | Quando atualizar | Quem |
|----------|-----------------|------|
| ARCHITECTURE.md | Final de cada fase (novos módulos, chaves ctx) | Claude Code + revisão humana |
| PATTERNS.md | Se padrões mudarem significativamente | Humano |
| ADRs | Nunca editar existentes; criar novo ADR se decisão mudar | Humano |
| DEPENDENCY_GRAPH.mermaid | Final de cada fase | Claude Code |
| CLAUDE.md | Raramente (se protocolo de sprints mudar) | Humano |
| Plano de implementação | Se escopo mudar (novas features, repriorizações) | Humano via Claude.ai |
