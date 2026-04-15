## Resumo

<!-- Descreva em 1-3 frases o que este PR faz e por quê -->

## Sprint / Fase

<!-- Ex: Fetcher Maximization Sprint B.3, Fase 2 Sprint 2, etc. -->

## Tipo de mudança

- [ ] `feat` — Nova funcionalidade
- [ ] `fix` — Correção de bug
- [ ] `refactor` — Reestruturação sem mudança de comportamento
- [ ] `test` — Adição/correção de testes
- [ ] `docs` — Documentação
- [ ] `chore` — CI, tooling, config

## Entregáveis

<!-- Liste os arquivos criados ou modificados -->

-

## Checklist de qualidade

- [ ] Type hints em todas as funções e métodos
- [ ] Docstrings no padrão do projeto (o que faz, lê, produz)
- [ ] Decorators aplicados onde apropriado (`@log_execution`, `@retry`, etc.)
- [ ] Logger via `get_logger(__name__)` em todos os módulos novos
- [ ] Backward compatibility verificada (pipelines existentes rodam)
- [ ] Nenhum import circular introduzido
- [ ] Error handling: erros parciais em `ctx["_errors"]`, não silenciar exceções
- [ ] Validação Pydantic: campos obrigatórios non-empty, preços >= 0
- [ ] Testes com mocks de fetchers (nunca chamadas reais em unit tests)

## Testes

- **Total**: <!-- ex: 420 -->
- **Novos**: <!-- ex: 13 -->
- **Falhas conhecidas**: <!-- ex: CVM 404 (pré-existente) -->

## Notas

<!-- Observações para o reviewer, trade-offs, dúvidas -->
