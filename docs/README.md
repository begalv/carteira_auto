# Documentação — carteira_auto

## Documentação do Sistema (`docs/system/`)

Documentação primária do projeto para desenvolvedores e usuários.

| Documento | Descrição |
|-----------|-----------|
| [plano_implementacao_carteira_auto.md](system/plano_implementacao_carteira_auto.md) | **Source of truth arquitetural.** 8 camadas, 8 fases, modelos de código, regras de design. Leia antes de qualquer sprint. |
| [architecture.md](system/architecture.md) | Visão de alto nível das camadas e componentes do sistema. |
| [developer_guide.md](system/developer_guide.md) | Setup de ambiente, fluxo de trabalho, convenções. |
| [quickstart.md](system/quickstart.md) | Início rápido para rodar os primeiros pipelines. |
| [api_reference.md](system/api_reference.md) | Referência de classes, métodos e interfaces públicas. |

## Documentação Claude Code (`docs/dev/`)

Referência de desenvolvimento para uso do Claude Code durante sprints.
Arquivos compactos e atualizados a cada fase.

| Documento | Descrição |
|-----------|-----------|
| [ARCHITECTURE.md](dev/ARCHITECTURE.md) | Mapa compacto de módulos, exports, ctx keys, pipelines e paths. Consulte antes de criar qualquer arquivo novo. |
| [PATTERNS.md](dev/PATTERNS.md) | Templates canônicos de fetchers, analyzers, nodes, models. |
| [DEPENDENCY_GRAPH.mermaid](dev/DEPENDENCY_GRAPH.mermaid) | Grafo de dependências entre módulos. |
| [README.md](dev/README.md) | Índice da documentação de desenvolvimento. |
