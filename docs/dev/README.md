# Documentação Claude Code — carteira_auto v0.2.1

Artefatos de referência para desenvolvimento com Claude Code.
Atualizados ao final de cada fase/sprint.

## Inventário

| Arquivo | Propósito | Quando consultar |
|---------|-----------|-----------------|
| `ARCHITECTURE.md` | Mapa compacto: módulos, exports, ctx keys, pipelines, testes | Antes de criar qualquer arquivo novo |
| `PATTERNS.md` | 9 templates canônicos (fetcher, analyzer, strategy, result, validação) | Ao implementar novos componentes |
| `DEPENDENCY_GRAPH.mermaid` | Grafo de dependências entre módulos | Antes de adicionar imports (previne ciclos) |

**Nota:** A governança completa de sprints fica em `CLAUDE.md` na raiz do repositório
(carregado automaticamente pelo Claude Code). O plano arquitetural fica em
`docs/system/plano_implementacao_carteira_auto.md`.

## Estado atual — Fase 2 Sprint 1

### Novo (Sprint 0 + Sprint 1)
- **ARCHITECTURE.md** atualizado para v0.2.1 com 3 novos analyzers (currency, commodity, fiscal),
  3 ctx keys, 3 pipelines CLI, 3 arquivos de teste
- **DEPENDENCY_GRAPH.mermaid** atualizado com novos nodes e conexões BCB/FRED/Yahoo → analyzers
- Códigos SGS fiscais corrigidos: 13762 (dívida/PIB), 5727 (juros/PIB)

### Decisões arquiteturais incorporadas (Hardening)
- Result type `Ok[T] | Err[T]` como padrão de error handling
- Validação Pydantic estrita com `field_validator`
- Per-node error handling no DAGEngine
- Imutabilidade via `model_copy()` em vez de mutação in-place
- Error tracking parcial em analyzers via `ctx["_errors"]`

## Manutenção

| Artefato | Quando atualizar |
|----------|-----------------|
| `ARCHITECTURE.md` | Final de cada fase (novos módulos, chaves ctx, testes) |
| `PATTERNS.md` | Se padrões mudarem ou novos patterns surgirem |
| `DEPENDENCY_GRAPH.mermaid` | Final de cada fase |
| `CLAUDE.md` (raiz) | A cada fase concluída (status, lembretes novos) |
| Plano de implementação | A cada fase concluída (progresso, decisões) |

## Próximos sprints (Fase 2)

Restam 6 analyzers: FundamentalAnalyzer, YieldCurveAnalyzer, GlobalMacroAnalyzer,
CorrelationAnalyzer, DividendAnalyzer, PersonalFinanceAnalyzer.
