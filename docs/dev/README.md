# Pacote de Documentação — carteira_auto v0.2.0

## Inventário dos artefatos

| # | Arquivo | Propósito | Impacto no Claude Code |
|---|---------|-----------|----------------------|
| 1 | `CLAUDE.md` | Governança de sprints, infra existente, estado atual, lembretes | Lido automaticamente — define comportamento |
| 2 | `docs/plano_implementacao_carteira_auto.md` | Source of truth: 8 camadas, 8 fases, progresso, decisões | Referência por fase |
| 3 | `claude_code_docs/ARCHITECTURE.md` | Mapa compacto: módulos, exports, ctx keys, pipelines, testes | Elimina redescoberta de código |
| 4 | `claude_code_docs/PATTERNS.md` | 9 templates canônicos (fetcher, analyzer, strategy, result, validação) | Few-shot prompting — consistência |
| 5 | `docs/adr/001-006` | Decisões e razões (DAG, Strategy!=Node, SQLite, Layered, Config, AI) | Impede reversão de decisões |
| 6 | `claude_code_docs/DEPENDENCY_GRAPH.mermaid` | Grafo de dependências entre módulos | Previne imports circulares |

## O que mudou desde v0.1.0

### Hardening Sprint (PR #20)
- **ARCHITECTURE.md** atualizado para v0.2.0 com novos módulos (result.py, lake/, 7 fetchers, ingest_nodes), seção de testes
- **PATTERNS.md** expandido com 3 novos patterns: Result type (7), Error tracking parcial (8), Validação Pydantic estrita (9)
- **DEPENDENCY_GRAPH.mermaid** atualizado com result, lake, 4 novos fetchers, ingest_nodes e suas conexões
- **CLAUDE.md** atualizado com estado atual (v0.2.0), lembretes de decisões, regras de error handling
- **Plano de implementação** atualizado com seção "Progresso Atual" e status das fases

### Decisões arquiteturais incorporadas
- Result type `Ok[T] | Err[T]` como padrão de error handling
- Validação Pydantic estrita com `field_validator`
- Per-node error handling no DAGEngine
- Imutabilidade via `model_copy()` em vez de mutação in-place
- Error tracking parcial em analyzers via `ctx["_errors"]`

## Manutenção

| Artefato | Quando atualizar | Quem |
|----------|-----------------|------|
| ARCHITECTURE.md | Final de cada fase (novos módulos, chaves ctx, testes) | Claude Code + revisão humana |
| PATTERNS.md | Se padrões mudarem ou novos patterns surgirem | Humano |
| ADRs | Nunca editar existentes; criar novo ADR se decisão mudar | Humano |
| DEPENDENCY_GRAPH.mermaid | Final de cada fase | Claude Code |
| CLAUDE.md | A cada fase concluída (status, lembretes novos) | Claude Code + revisão humana |
| Plano de implementação | A cada fase concluída (progresso, decisões) | Claude Code + revisão humana |

## Próximos passos

A **Fase 2** (Analyzers Avançados) é a próxima. Consulte o plano de implementação
para os 9 analyzers a criar: FundamentalAnalyzer, CurrencyAnalyzer,
CommodityAnalyzer, YieldCurveAnalyzer, FiscalAnalyzer, GlobalMacroAnalyzer,
CorrelationAnalyzer, DividendAnalyzer, PersonalFinanceAnalyzer.
