# CLAUDE.md — Governança de Desenvolvimento do carteira_auto

## Seu papel

Você é o co-desenvolvedor do sistema `carteira_auto` — um sistema de automação
de carteira de investimentos para emancipação financeira de pessoa física no Brasil.
Seu parceiro humano é um programador Python com foco em finanças, economia e
geopolítica. Vocês trabalharão juntos em sprints iterativos.

## Estado atual do projeto (v0.2.1 — Fetcher Maximization Sprint, Fases A-B concluídas)

| Fase | Status | Entregáveis |
|------|--------|-------------|
| 0 | CONCLUÍDA | DataLake SQLite, IngestNodes, settings expandido |
| 1 | CONCLUÍDA | FREDFetcher, CVMFetcher, TesouroDiretoFetcher, DDMFetcher |
| Hardening | CONCLUÍDA | Result type, validação estrita, error handling, 350 testes |
| 2 Sprint 0 | CONCLUÍDA | Validação infraestrutura, correção códigos BCB SGS |
| 2 Sprint 1 | CONCLUÍDA | CurrencyAnalyzer, CommodityAnalyzer, FiscalAnalyzer + 33 testes |
| **Fetcher Sprint A** | **CONCLUÍDA** | Dependências (python-bcb, sidrapy, tradingcomdados), constants expandidos (BCB 57 séries, IBGE 17 tabelas, FRED 38 séries, 6 índices), FetchWithFallback helper, ReferenceLake (12 tabelas), TradingComDadosConfig |
| **Fetcher Sprint B** | **CONCLUÍDA** | BCBFetcher (módulo bcb/ com 6 mixins, 105 métodos, incl. MercadoImobiliário), IBGEFetcher (+get_analfabetismo, fix D3N/D4N, @cache_result), FREDFetcher (+23 convenience methods, FRED_SERIES unificada em constants.py) |
| **Fetcher Sprint C** | Pendente | Expansão Yahoo, DDM, Tesouro, CVM + TradingComDadosFetcher |
| **Fetcher Sprint D** | Pendente | IngestNodes com fallback, testes integração, docs finais |
| 2 Sprint 2+ | Pendente | 6 analyzers restantes (fundamental, yield curve, global macro...) |

**Testes:** 697 passando (unit + integration). 1 falha pré-existente (CVM 404).
**Novos testes Sprint B:** test_bcb_fetcher_v2.py (129), test_fred_fetcher.py (55), test_ibge_fetcher_v2.py (40).
**Cobertura:** models, analyzers (10), fetchers (BCB 129, FRED 55, IBGE 40), CLI, decorators, E2E pipelines, fetch_helpers, reference_lake.

## Documentos de referência

### Documentação do sistema (primária — leia antes de tomar decisões)

- **Plano de implementação**: `docs/system/plano_implementacao_carteira_auto.md`
  Source of truth arquitetural. Contém 8 camadas, 8 fases, modelos de
  código, regras de design e decisões consolidadas. LEIA-O INTEGRALMENTE
  antes de qualquer sprint. Sempre consulte-o ao tomar decisões de design.

- **Arquitetura do sistema**: `docs/system/architecture.md`
  Visão de alto nível das camadas do sistema para desenvolvedores.

- **Guia do desenvolvedor**: `docs/system/developer_guide.md`
  Setup de ambiente, fluxo de trabalho, convenções de código.

### Documentação Claude Code (referência de desenvolvimento — consulte durante sprints)

- **Mapa do código**: `docs/dev/ARCHITECTURE.md`
  Referência compacta de todos os módulos, exports, chaves do PipelineContext,
  pipelines registradas e paths do sistema. Consulte ANTES de criar qualquer
  arquivo novo para saber o que já existe e como se conecta.

- **Padrões de código**: `docs/dev/PATTERNS.md`
  Templates canônicos para novos fetchers, analyzers, strategies, nodes,
  models e publishers. Inclui patterns de error handling e validação Pydantic.

- **Grafo de dependências**: `docs/dev/DEPENDENCY_GRAPH.mermaid`
  Quem importa quem. Consulte antes de adicionar imports para evitar ciclos.

- **DevOps e CI/CD**: `docs/dev/DEVOPS.md`
  Guia completo de como contribuir: branches, commits, PRs, Makefile,
  GitHub Actions, Dependabot, troubleshooting. Leia ao iniciar um sprint.

- **Próximo sprint**: `docs/dev/NEXT_SPRINT.md`
  Prompt de continuação para novas sessões Claude Code. Contém o estado
  atual dos Fetcher Sprints e decisões técnicas pendentes.

- **Código existente**: `src/carteira_auto/`
  O repositório tem código funcional (v0.2.1). Respeite e reaproveite tudo
  que já existe — nunca reescreva o que funciona.

## Protocolo de sprints

O desenvolvimento segue 8 fases (0 a 7). Cada fase será dividida em sprints
de escopo gerenciável. Para CADA sprint, siga este protocolo rigorosamente:

### 1. Planejamento do sprint (ANTES de escrever código)

a) **Leia o plano** — releia a seção da fase atual no plano de implementação.

b) **Audite o estado atual** — examine o código existente relevante para a fase.
   Consulte `docs/dev/ARCHITECTURE.md` primeiro, depois o código.

c) **Proponha o sprint** — apresente ao humano:
   - Título e objetivo do sprint (1 frase)
   - Lista de entregáveis concretos (arquivos a criar/modificar)
   - Dependências de sprints anteriores
   - Riscos ou dúvidas que precisam de decisão humana

d) **Faça perguntas** — ANTES de implementar, levante ambiguidades,
   trade-offs e dúvidas de domínio. NÃO prossiga sem respostas para
   perguntas críticas.

e) **Aguarde aprovação** — só comece a implementar após o humano aprovar.

### 2. Implementação (durante o sprint)

a) **Incremental** — implemente arquivo por arquivo, não tudo de uma vez.
b) **Testes junto com código** — para cada módulo novo, escreva o teste
   correspondente no mesmo sprint.
c) **Rode os testes** — execute `pytest` após cada módulo.
d) **Commit semântico** — sugira mensagens de commit claras.

### 3. Revisão do sprint (APÓS implementar)

a) **Resumo do que foi feito** — arquivos criados/modificados.
b) **Status dos testes** — quantos passaram, quantos falharam.
c) **Checklist de qualidade**:
   - [ ] Type hints em todas as funções e métodos
   - [ ] Docstrings no padrão do projeto (o que faz, lê, produz)
   - [ ] Decorators aplicados onde apropriado (@log_execution, @retry, etc.)
   - [ ] Logger via get_logger(__name__) em todos os módulos
   - [ ] Backward compatibility verificada (pipelines existentes rodam)
   - [ ] Nenhum import circular introduzido
   - [ ] Error handling: erros parciais em ctx["_errors"], não silenciar exceções
   - [ ] Validação Pydantic: campos obrigatórios non-empty, preços >= 0
   - [ ] Testes com mocks de fetchers (nunca chamadas reais em unit tests)
d) **Perguntas de revisão** ao humano.
e) **Transição** — após aprovação, apresente o planejamento do próximo sprint.

## Infraestrutura existente — USE E REAPROVEITE

### Config (src/carteira_auto/config/)
- `settings.py`: Settings dataclass com PathsConfig, YahooFetcherConfig,
  BCBConfig, IBGEConfig, DDMConfig, FREDConfig, TradingComDadosConfig,
  DataLakeConfig, PortfolioConfig, LoggingConfig.
  PortfolioConfig inclui RISK_FREE_DAILY e MIN_TRADE_VALUE.
  → ADICIONE novas configs aqui (AIConfig, etc.)
  → OptimizationConfig vai em config/optimization.py (novo arquivo)
- `constants.py`: Constants class com colunas de planilha, field maps,
  BCB_SERIES_CODES (57 séries SGS), IBGE_TABLE_IDS (17 tabelas SIDRA),
  FRED_SERIES (38 séries, chaves PT: nome/unidade/frequencia), INDEX_CODES (6 índices B3),
  padrões de ticker, horários de mercado, feriados B3.
  → ADICIONE novas constantes aqui.

### Utils (src/carteira_auto/utils/)
- `decorators.py`: @timer, @retry, @rate_limit, @timeout, @fallback,
  @validate_tickers, @validate_positive_value, @validate_allocation_sum,
  @log_execution, @cache_result, @cache_by_ticker.
  → USE estes decorators em todo código novo.
  → @fallback e @validate_* estão disponíveis mas ainda não usados.
- `logger.py`: setup_logging(), get_logger(name).
  → USE get_logger(__name__) em todo módulo novo.
- `helpers.py`: validate_ticker() e outras utilidades.

### Core (src/carteira_auto/core/)
- `engine.py`: DAGEngine(fail_fast), Node ABC, PipelineContext, NodeExecutionError.
  → DAGEngine tem per-node error handling (erros em ctx["_errors"]).
  → Node.__init_subclass__() isola dependencies entre subclasses.
  → PipelineContext.errors e .has_errors para consultar erros.
- `result.py`: Ok[T], Err[T], Result type alias.
  → USE para error handling explícito quando apropriado.
- `models/`: Asset (validação estrita), Portfolio, SoldAsset, PortfolioMetrics,
  RiskMetrics (com is_complete()), MacroContext, MarketMetrics, CurrencyMetrics,
  CommodityMetrics, FiscalMetrics, RebalanceRecommendation, AllocationResult
  (Literal types), modelos econômicos.
  → ADICIONE novos Pydantic models aqui (Signal, StrategyResult, AIAnalysis, etc.)
  → Siga Pattern 9 (validação estrita) para novos models.
- `registry.py`: PIPELINE_PRESETS, create_engine().
  → EXPANDA com novos pipelines. NÃO remova os existentes.
- `nodes/`: LoadPortfolioNode, FetchPricesNode (usa model_copy, sem mutação),
  ExportPortfolioPricesNode, IngestPricesNode, IngestMacroNode, etc.
  → ADICIONE novos nodes aqui (strategy, optimizer, ai, publish).
- `nodes/fetch_helpers.py`: FetchStrategy, FetchResult, fetch_with_fallback().
  → Helper de fallback hierárquico entre fetchers diferentes.
  → Usado nos IngestNodes para orquestrar fontes com rastreamento de proveniência.
  → Veja Pattern 10 em PATTERNS.md.

### Data (src/carteira_auto/data/)
- `fetchers/`: YahooFinanceFetcher, BCBFetcher (módulo bcb/ com 6 mixins),
  IBGEFetcher, FREDFetcher, CVMFetcher, TesouroDiretoFetcher, DDMFetcher (7 fetchers).
  BCBFetcher inclui: SGS, Focus, PTAX, TaxaJuros, MercadoImobiliário (105 métodos).
  FREDFetcher com 23 convenience methods + 4 base methods para 38 séries.
  TradingComDadosFetcher planejado para Sprint C (config pronta em settings.py).
  → EXPANDA os existentes conforme plano do sprint.
  → ADICIONE novos fetchers no mesmo padrão (Pattern 1).
- `lake/`: DataLake (fachada), PriceLake, MacroLake, FundamentalsLake, NewsLake,
  ReferenceLake (12 tabelas: composições, Focus, targets, holders, fundos, ativos).
  → DataLake é o single source of truth para dados históricos.
  → ReferenceLake para dados de referência não-temporais.
- `loaders/`: ExcelLoader, PortfolioLoader.
- `exporters/`: ExcelExporter, PortfolioPriceExporter.
- `storage/`: SnapshotStore (JSON).

### Analyzers (src/carteira_auto/analyzers/)
- PortfolioAnalyzer, RiskAnalyzer, MacroAnalyzer, MarketAnalyzer,
  Rebalancer, MarketSectorAnalyzer, EconomicSectorAnalyzer,
  CurrencyAnalyzer, CommodityAnalyzer, FiscalAnalyzer (10 analyzers).
  → Todos usam error tracking parcial (Pattern 8).
  → ADICIONE novos analyzers no mesmo padrão (Pattern 2).

### Alerts (src/carteira_auto/alerts/)
- AlertEngine, AlertRule, Alert, ConsoleChannel, LogChannel.
  → ADICIONE novos channels seguindo AlertChannel ABC.

### Dashboard (dashboards/)
- app.py + pages/ (visão geral, portfolio, risk, macro).
  → EXPANDA com novas páginas.

## Regras de design invioláveis

1. Single Responsibility: cada Node faz UMA coisa.
2. Comunicação via PipelineContext — sem estado global.
3. Fetchers só buscam. Analyzers só calculam. Strategies só decidem.
4. DataLake é o single source of truth para dados históricos.
5. Backward compatibility: pipelines existentes NUNCA quebram.
6. Type hints em tudo. Pydantic para modelos. Typing para funções.
7. Testes para cada componente novo.
8. Logs via get_logger(__name__) em todo módulo.
9. Error handling explícito: erros parciais em ctx["_errors"], nunca silenciar.
10. Validação estrita: Pydantic field_validator, Literal types para actions.
11. Imutabilidade: usar model_copy() em vez de mutação in-place.
12. AI providers são intercambiáveis via PromptEngine.
13. AI nunca executa — só analisa, narra, recomenda.
14. Publishers são independentes — falha num canal não impede os demais.
15. Strategy.evaluate(ctx) -> StrategyResult é o método central.
16. StrategyNode(Node) é a ponte entre Strategy e DAGEngine.
17. CompositeStrategy usa Layered como padrão, com gates condicionais.
18. OptimizationConfig fica em config/optimization.py.
19. Custos de IA são rastreados — budget mensal é hard limit.

## Fases de implementação — referência rápida

| Fase | Escopo | Status |
|------|--------|--------|
| 0 | Infra: DataLake SQLite, IngestNodes, settings | CONCLUÍDA |
| 1 | Fontes: FRED, CVM, Tesouro, DDM | CONCLUÍDA |
| H | Hardening: Result type, validação, error handling, testes | CONCLUÍDA |
| 2 Sprint 1 | Analyzers: currency, commodity, fiscal | CONCLUÍDA |
| **Fetcher Max A** | **Fundação: deps, constants, FetchWithFallback, ReferenceLake (12 tab)** | **CONCLUÍDA** |
| **Fetcher Max B** | **BCBFetcher (6 mixins + MercadoImobiliário), IBGEFetcher (+analfabetismo), FREDFetcher (+23 convenience methods), auditoria e testes** | **CONCLUÍDA** |
| **Fetcher Max C** | **Expansão Yahoo, DDM, Tesouro, CVM + TradingComDadosFetcher** | Pendente |
| **Fetcher Max D** | **IngestNodes com fallback, testes integração, docs** | Pendente |
| 2 Sprint 2+ | Analyzers restantes (fundamental, yield curve, global macro...) | Pendente |
| 3 | Estratégias + Optimizer (PyPortfolioOpt) + Backtesting | Pendente |
| 4 | ML: scoring fundamentalista, integração ML↔optimizer | Pendente |
| 5 | NLP: sentimento, geopolítica, crisis hedge | Pendente |
| 6 | AI Reasoning: Claude/Deepseek, prompts, AIAnalysis | Pendente |
| 7 | Publishers: Telegram bot, PDF, email, Excel, web, scheduler | Pendente |

Detalhes de cada fase estão no plano. Leia a seção correspondente
antes de iniciar cada fase.

## Lembretes importantes (decisões tomadas)

- **Mock paths**: fetchers importados dentro de `run()` devem ser mockados em
  `carteira_auto.data.fetchers.NomeFetcher`, não no módulo do analyzer.
- **CVM 404**: `test_get_dfp_dre_petrobras` falha com 404 — endpoint CVM removeu
  o arquivo de 2023. Pré-existente, não bloqueia desenvolvimento.
- **ruff UP007**: usar `X | Y` em vez de `Optional[X]` para type annotations.
- **Pre-commit hooks**: black + ruff rodam automaticamente. Sempre corrigir antes
  de commitar.
- **Códigos SGS fiscais validados**: Dívida bruta/PIB = 13762 (NÃO 13621, que
  retorna valor absoluto em R$). Juros nominais/PIB = 5727 (NÃO 4185, que não existe).
- **Novas dependências (Fetcher Sprint)**: python-bcb>=0.3.0, sidrapy>=0.1.0,
  tradingcomdados>=0.4.0 — todas gratuitas, sem API key.
- **FetchWithFallback vs @fallback**: `fetch_with_fallback()` orquestra ENTRE fetchers
  diferentes (usado nos IngestNodes). `@fallback` opera DENTRO de um mesmo fetcher
  (ex: python-bcb → HTTP raw). Não confundir os dois mecanismos.
- **ReferenceLake (12 tabelas)**: dados de referência não-temporais. Todas as tabelas
  com `source` e `updated_at`. Auditoria de cobertura confirmou que TODOS os dados
  dos fetchers expandidos têm destino no DataLake.
- **BCBFetcher é módulo** (Sprint B.4): `bcb_fetcher.py` foi deletado. O BCBFetcher
  agora vive em `data/fetchers/bcb/` como módulo com 6 mixins. Importar sempre
  via `from carteira_auto.data.fetchers.bcb import BCBFetcher`.
- **FRED_SERIES fonte canônica**: `Constants.FRED_SERIES` em `config/constants.py`
  com chaves PT (`nome`, `unidade`, `frequencia`). Não duplicar no fetcher.
- **Rodando testes no worktree**: usar `PYTHONPATH=src python3 -m pytest` para
  garantir que o worktree `src/` tenha prioridade sobre o pacote instalado.

## Workflow de CI/CD

### Convenção de branches: `<tipo>/<escopo>-<descricao>`

| Tipo | Uso | Exemplo |
|------|-----|---------|
| `feat/` | Features de sprint | `feat/sprintC1-yahoo-ddm-expansion` |
| `fix/` | Bug fixes | `fix/cvm-404-endpoint` |
| `refactor/` | Reestruturação | `refactor/lake-schema-v2` |
| `test/` | Só testes | `test/analyzers-coverage` |
| `docs/` | Só documentação | `docs/api-reference` |
| `chore/` | CI, tooling, config | `chore/ci-setup` |
| `claude/` | Auto-gerado pelo Claude Code | `claude/<nome-aleatorio>` |

### Convenção de commits: `<tipo>(<escopo>): <descrição>`

Escopos: `bcb`, `ibge`, `fred`, `yahoo`, `cvm`, `tesouro`, `ddm`, `lake`,
`analyzers`, `models`, `config`, `cli`, `core`, `ci`, `deps`.
Descrição em português. Max 72 caracteres.

### Makefile (atalhos de desenvolvimento)

```bash
make test          # testes rápidos (unit, sem slow/integration)
make test-all      # todos os testes
make test-cov      # testes + cobertura HTML
make lint          # ruff check
make format        # auto-format (black + ruff fix)
make check         # CI local completo (lint + format-check + test)
make install-dev   # setup de desenvolvimento
make clean         # limpa artefatos
make clean-worktrees  # limpa worktrees órfãos
```

### GitHub Actions (CI automático)

- **PR para main**: lint, format, typecheck, testes em Python 3.10/3.11/3.12
- **Merge no main**: suite completa de testes + cobertura
- **Tag v\***: release automático no GitHub
- **Dependabot**: alertas semanais de vulnerabilidades em deps

### Fluxo de sprint padronizado

1. Criar branch: `git checkout -b feat/sprintX-descricao` (ou Claude cria worktree)
2. Implementar incrementalmente com `make test` após cada módulo
3. Antes do push: `make check` (equivale ao CI local)
4. Push + criar PR → CI roda automaticamente
5. Review → squash merge no main → branch auto-deletada
6. Cleanup: `git checkout main && git pull && make clean-worktrees`

### Configurações do GitHub (manuais)

- Branch protection em `main`: require status checks (`lint`, `format`, `test`)
- Auto-delete head branches: ativado
- Squash merge como default
- Require branches to be up to date antes de merge

## Como iniciar

Quando o humano disser "vamos começar" ou indicar que quer iniciar uma fase:

1. Leia o plano de implementação (seção da fase): `docs/system/plano_implementacao_carteira_auto.md`
2. Consulte `docs/dev/ARCHITECTURE.md` para o estado atual do código.
3. Proponha a decomposição da fase em sprints de 1-3 dias cada.
4. Apresente o Sprint 1 com escopo, entregáveis e perguntas.
5. Aguarde aprovação antes de escrever código.

Quando o humano disser "continuar", "próximo sprint", ou similar:
1. Faça a revisão do sprint anterior (se aplicável).
2. Apresente o próximo sprint.
3. Aguarde aprovação.

## Idioma

Comunique-se em português brasileiro. Código e docstrings em português
(conforme o padrão existente no repositório). Nomes de classes, métodos
e variáveis em inglês quando técnicos (Node, Pipeline, Fetcher).
