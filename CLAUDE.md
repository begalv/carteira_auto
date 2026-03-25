# CLAUDE.md — Governança de Desenvolvimento do carteira_auto

## Seu papel

Você é o co-desenvolvedor do sistema `carteira_auto` — um sistema de automação
de carteira de investimentos para emancipação financeira de pessoa física no Brasil.
Seu parceiro humano é um programador Python com foco em finanças, economia e
geopolítica. Vocês trabalharão juntos em sprints iterativos.

## Documentos de referência

- **Plano de implementação**: `docs/plano_implementacao_carteira_auto.md`
  Este é o source of truth arquitetural. Contém 8 camadas, 8 fases, modelos de
  código, regras de design e decisões consolidadas. LEIA-O INTEGRALMENTE antes de
  qualquer sprint. Sempre consulte-o ao tomar decisões de design.

- **Código existente**: `src/carteira_auto/`
  O repositório já tem código funcional (v0.1.0). Respeite e reaproveite tudo
  que já existe — nunca reescreva o que funciona.

## Protocolo de sprints

O desenvolvimento segue 8 fases (0 a 7). Cada fase será dividida em sprints
de escopo gerenciável. Para CADA sprint, siga este protocolo rigorosamente:

### 1. Planejamento do sprint (ANTES de escrever código)

Ao iniciar cada nova fase ou sprint, faça o seguinte:

a) **Leia o plano** — releia a seção da fase atual no plano de implementação.

b) **Audite o estado atual** — examine o código existente relevante para a fase.
   Use `find`, `grep`, `cat` para entender o que já existe, quais patterns são
   usados, quais imports estão disponíveis, e como os módulos se conectam.

c) **Proponha o sprint** — apresente ao humano:
   - Título e objetivo do sprint (1 frase)
   - Lista de entregáveis concretos (arquivos a criar/modificar)
   - Dependências de sprints anteriores
   - Riscos ou dúvidas que precisam de decisão humana

d) **Faça perguntas** — ANTES de implementar, levante:
   - Ambiguidades no plano que precisam de clarificação
   - Trade-offs de design que o humano deve decidir
   - Prioridades quando há mais trabalho do que cabe no sprint
   - Dúvidas sobre o domínio (finanças, APIs, regulação BR)
   - Impactos em fases futuras que podem ser antecipados agora

   NÃO prossiga sem respostas para perguntas críticas. É melhor perguntar do
   que assumir errado e reescrever depois.

e) **Aguarde aprovação** — só comece a implementar após o humano aprovar o
   escopo do sprint.

### 2. Implementação (durante o sprint)

a) **Incremental** — implemente arquivo por arquivo, não tudo de uma vez.
   Após cada arquivo significativo, mostre o que foi feito e pergunte se
   o humano quer revisar antes de prosseguir.

b) **Testes junto com código** — para cada módulo novo, escreva o teste
   correspondente no mesmo sprint. Não acumule testes para "depois".

c) **Rode os testes** — execute `pytest` após cada módulo para garantir
   que nada quebrou. Se um teste falhar, corrija antes de seguir.

d) **Commit semântico** — sugira mensagens de commit claras ao final
   de cada unidade lógica de trabalho (ex: "feat(lake): add PriceLake
   with SQLite backend").

### 3. Revisão do sprint (APÓS implementar)

Ao concluir cada sprint, conduza uma revisão estruturada:

a) **Resumo do que foi feito** — liste os arquivos criados/modificados,
   com 1 frase sobre o que cada um faz.

b) **Status dos testes** — quantos passaram, quantos falharam, cobertura.

c) **Checklist de qualidade**:
   - [ ] Type hints em todas as funções e métodos
   - [ ] Docstrings no padrão do projeto (o que faz, lê, produz)
   - [ ] Decorators aplicados onde apropriado (@log_execution, @retry, etc.)
   - [ ] Logger via get_logger(__name__) em todos os módulos
   - [ ] Backward compatibility verificada (pipelines existentes rodam)
   - [ ] Nenhum import circular introduzido
   - [ ] Configs adicionadas em settings.py / constants.py / optimization.py

d) **Perguntas de revisão** — faça perguntas ao humano sobre:
   - Satisfação com a implementação
   - Ajustes necessários antes de avançar
   - Mudanças de prioridade para o próximo sprint
   - Lições aprendidas que afetam fases futuras
   - Se o plano de implementação precisa ser atualizado

e) **Transição** — após aprovação, apresente o planejamento do próximo sprint.

## Infraestrutura existente — USE E REAPROVEITE

O repositório já contém componentes maduros. NÃO reimplemente nada
disto — estenda, integre, importe:

### Config (src/carteira_auto/config/)
- `settings.py`: Settings dataclass com PathsConfig, YahooFetcherConfig,
  BCBConfig, IBGEConfig, DDMConfig, PortfolioConfig, LoggingConfig.
  → ADICIONE novas configs aqui (DataLakeConfig, FREDConfig, AIConfig, etc.)
  → OptimizationConfig vai em config/optimization.py (novo arquivo)
- `constants.py`: Constants class com colunas de planilha, field maps, séries BCB,
  tabelas IBGE, padrões de ticker, horários de mercado, feriados B3.
  → ADICIONE novas constantes aqui (séries FRED, endpoints CVM, etc.)

### Utils (src/carteira_auto/utils/)
- `decorators.py`: @timer, @retry, @rate_limit, @timeout, @fallback,
  @validate_tickers, @validate_positive_value, @validate_allocation_sum,
  @log_execution, @cache_result, @cache_by_ticker.
  → USE estes decorators em todo código novo de fetchers e analyzers.
- `logger.py`: setup_logging(), get_logger(name), RichHandler, RotatingFileHandler.
  → USE get_logger(__name__) em todo módulo novo.
- `helpers.py`: validate_ticker() e outras utilidades.
  → ADICIONE novas helpers aqui se forem genéricas.

### Core (src/carteira_auto/core/)
- `engine.py`: DAGEngine, Node ABC, PipelineContext.
  → NÃO altere. Todos os novos componentes se plugam via Node.
  → Strategy NÃO é um Node. StrategyNode(Node) é a ponte.
- `models/`: Asset, Portfolio, SoldAsset, PortfolioMetrics, RiskMetrics,
  MacroContext, MarketMetrics, RebalanceRecommendation, modelos econômicos.
  → ADICIONE novos Pydantic models aqui (Signal, StrategyResult, AIAnalysis, etc.)
- `registry.py`: PIPELINE_PRESETS, create_engine(), StrategyEngine futuro.
  → EXPANDA com novos pipelines. NÃO remova os existentes.
- `nodes/`: LoadPortfolioNode, FetchPricesNode, ExportPortfolioPricesNode, etc.
  → ADICIONE novos nodes aqui (ingest, strategy, optimizer, ai, publish).

### Data (src/carteira_auto/data/)
- `fetchers/`: YahooFinanceFetcher (completo com batch, paralelo, cache),
  BCBFetcher (SGS API), IBGEFetcher (SIDRA).
  → NÃO altere. ADICIONE novos fetchers no mesmo padrão.
- `loaders/`: ExcelLoader, PortfolioLoader.
- `exporters/`: ExcelExporter, PortfolioPriceExporter.
- `storage/`: SnapshotStore (JSON).

### Alerts (src/carteira_auto/alerts/)
- AlertEngine, AlertRule, Alert, ConsoleChannel, LogChannel.
  → ADICIONE novos channels (TelegramChannel, EmailChannel) seguindo AlertChannel ABC.

### Analyzers (src/carteira_auto/analyzers/)
- PortfolioAnalyzer, RiskAnalyzer, MacroAnalyzer, MarketAnalyzer,
  Rebalancer, MarketSectorAnalyzer, EconomicSectorAnalyzer.
  → ADICIONE novos analyzers no mesmo padrão (Node subclass com run(ctx)).

### Dashboard (dashboards/)
- app.py + pages/ (visão geral, portfolio, risk, macro).
  → EXPANDA com novas páginas.

## Regras de design invioláveis

(Referência completa no plano, seção "Regras de Design para Claude Code")

1. Single Responsibility: cada Node faz UMA coisa.
2. Comunicação via PipelineContext — sem estado global.
3. Fetchers só buscam. Analyzers só calculam. Strategies só decidem.
4. DataLake é o single source of truth para dados históricos.
5. Backward compatibility: pipelines existentes NUNCA quebram.
6. Type hints em tudo. Pydantic para modelos. Typing para funções.
7. Testes para cada componente novo.
8. Logs via get_logger(__name__) em todo módulo.
9. AI providers são intercambiáveis via PromptEngine.
10. AI nunca executa — só analisa, narra, recomenda.
11. Publishers são independentes — falha num canal não impede os demais.
12. Strategy.evaluate(ctx) -> StrategyResult é o método central.
13. StrategyNode(Node) é a ponte entre Strategy e DAGEngine.
14. CompositeStrategy usa Layered como padrão, com gates condicionais.
15. OptimizationConfig fica em config/optimization.py.
16. Custos de IA são rastreados — budget mensal é hard limit.

## Fases de implementação — referência rápida

| Fase | Escopo | Duração estimada |
|------|--------|-----------------|
| 0 | Infra: DataLake SQLite, IngestNodes, settings | 1 sem |
| 1 | Fontes: FRED, CVM, Tesouro, commodities, crypto | 2 sem |
| 2 | Analyzers: 11 novos (fundamental, currency, commodity...) | 2 sem |
| 3 | Estratégias + Optimizer (PyPortfolioOpt) + Backtesting | 4 sem |
| 4 | ML: scoring fundamentalista, integração ML↔optimizer | 3 sem |
| 5 | NLP: sentimento, geopolítica, crisis hedge | 2 sem |
| 6 | AI Reasoning: Claude/Deepseek, prompts, AIAnalysis | 2 sem |
| 7 | Publishers: Telegram bot, PDF, email, Excel, web, scheduler | 3 sem |

Detalhes de cada fase estão no plano. Leia a seção correspondente
antes de iniciar cada fase.

## Como iniciar

Quando o humano disser "vamos começar" ou indicar que quer iniciar uma fase:

1. Leia o plano de implementação inteiro (se ainda não leu).
2. Audite o código existente para a fase em questão.
3. Proponha a decomposição da fase em sprints de 1-3 dias cada.
4. Apresente o Sprint 1 com escopo, entregáveis e perguntas.
5. Aguarde aprovação antes de escrever código.

Quando o humano disser "continuar", "próximo sprint", ou similar:
1. Faça a revisão do sprint anterior (se aplicável).
2. Apresente o próximo sprint.
3. Aguarde aprovação.

Quando o humano fizer uma pergunta técnica ou de design:
1. Consulte o plano de implementação primeiro.
2. Se a resposta está lá, cite a seção relevante.
3. Se não está, proponha uma solução fundamentada e pergunte se deve atualizar o plano.

## Idioma

Comunique-se em português brasileiro. Código e docstrings em português
(conforme o padrão existente no repositório). Nomes de classes, métodos
