# CLAUDE.md — Governança de Desenvolvimento do carteira_auto

## Seu papel

Você é o co-desenvolvedor do sistema `carteira_auto` — um sistema de automação
de carteira de investimentos para emancipação financeira de pessoa física no Brasil.
Seu parceiro humano é um programador Python com foco em finanças, economia e
geopolítica. Vocês trabalharão juntos em sprints iterativos.

## Estado atual do projeto (v0.2.1 — Fase 2 Sprint 1 concluído)

| Fase | Status | Entregáveis |
|------|--------|-------------|
| 0 | CONCLUÍDA | DataLake SQLite, IngestNodes, settings expandido |
| 1 | CONCLUÍDA | FREDFetcher, CVMFetcher, TesouroDiretoFetcher, DDMFetcher |
| Hardening | CONCLUÍDA | Result type, validação estrita, error handling, 350 testes |
| 2 Sprint 0 | CONCLUÍDA | Validação infraestrutura, correção códigos BCB SGS |
| 2 Sprint 1 | CONCLUÍDA | CurrencyAnalyzer, CommodityAnalyzer, FiscalAnalyzer + 33 testes |
| 2 Sprint 2+ | PRÓXIMA | 6 analyzers restantes (fundamental, yield curve, global macro...) |

**Testes:** 407 passando (unit + integration). 2 falhas pré-existentes (CVM 404, Excel fixture).
**Cobertura:** models, analyzers (10), fetchers, CLI, decorators, E2E pipelines.

## Documentos de referência

- **Plano de implementação**: `docs/plano_implementacao_carteira_auto.md`
  Source of truth arquitetural. Contém 8 camadas, 8 fases, modelos de
  código, regras de design e decisões consolidadas. LEIA-O INTEGRALMENTE
  antes de qualquer sprint. Sempre consulte-o ao tomar decisões de design.

- **Mapa do código**: `claude_code_docs/ARCHITECTURE.md`
  Referência compacta de todos os módulos, exports, chaves do PipelineContext,
  pipelines registradas e paths do sistema. Consulte ANTES de criar qualquer
  arquivo novo para saber o que já existe e como se conecta.

- **Padrões de código**: `claude_code_docs/PATTERNS.md`
  Templates canônicos para novos fetchers, analyzers, strategies, nodes,
  models e publishers. Inclui patterns de error handling e validação Pydantic.

- **Decisões arquiteturais**: `docs/adr/`
  Architecture Decision Records. Documentam o PORQUÊ das decisões.
  Nunca reverta uma decisão documentada em ADR sem aprovação do humano.

- **Grafo de dependências**: `claude_code_docs/DEPENDENCY_GRAPH.mermaid`
  Quem importa quem. Consulte antes de adicionar imports para evitar ciclos.

- **Código existente**: `src/carteira_auto/`
  O repositório tem código funcional (v0.2.0). Respeite e reaproveite tudo
  que já existe — nunca reescreva o que funciona.

## Protocolo de sprints

O desenvolvimento segue 8 fases (0 a 7). Cada fase será dividida em sprints
de escopo gerenciável. Para CADA sprint, siga este protocolo rigorosamente:

### 1. Planejamento do sprint (ANTES de escrever código)

a) **Leia o plano** — releia a seção da fase atual no plano de implementação.

b) **Audite o estado atual** — examine o código existente relevante para a fase.
   Consulte `claude_code_docs/ARCHITECTURE.md` primeiro, depois o código.

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
  BCBConfig, IBGEConfig, DDMConfig, FREDConfig, DataLakeConfig, PortfolioConfig,
  LoggingConfig. PortfolioConfig inclui RISK_FREE_DAILY e MIN_TRADE_VALUE.
  → ADICIONE novas configs aqui (AIConfig, etc.)
  → OptimizationConfig vai em config/optimization.py (novo arquivo)
- `constants.py`: Constants class com colunas de planilha, field maps, séries BCB,
  tabelas IBGE, padrões de ticker, horários de mercado, feriados B3.
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
  RiskMetrics (com is_complete()), MacroContext, MarketMetrics,
  RebalanceRecommendation, AllocationResult (Literal types), modelos econômicos.
  → ADICIONE novos Pydantic models aqui (Signal, StrategyResult, AIAnalysis, etc.)
  → Siga Pattern 9 (validação estrita) para novos models.
- `registry.py`: PIPELINE_PRESETS, create_engine().
  → EXPANDA com novos pipelines. NÃO remova os existentes.
- `nodes/`: LoadPortfolioNode, FetchPricesNode (usa model_copy, sem mutação),
  ExportPortfolioPricesNode, IngestPricesNode, IngestMacroNode, etc.
  → ADICIONE novos nodes aqui (strategy, optimizer, ai, publish).

### Data (src/carteira_auto/data/)
- `fetchers/`: YahooFinanceFetcher, BCBFetcher, IBGEFetcher, FREDFetcher,
  CVMFetcher, TesouroDiretoFetcher, DDMFetcher (7 fetchers completos).
  → NÃO altere. ADICIONE novos fetchers no mesmo padrão (Pattern 1).
- `lake/`: DataLake, PriceLake, MacroLake, FundamentalsLake, NewsLake.
  → DataLake é o single source of truth para dados históricos.
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
| 2 | Analyzers: 9 novos — Sprint 1 concluído (currency, commodity, fiscal) | EM ANDAMENTO |
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

## Como iniciar

Quando o humano disser "vamos começar" ou indicar que quer iniciar uma fase:

1. Leia o plano de implementação (seção da fase).
2. Consulte `claude_code_docs/ARCHITECTURE.md` para o estado atual.
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
