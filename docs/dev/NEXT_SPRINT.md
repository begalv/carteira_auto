# Próximo Sprint — Épico 0: Estabilização (Sprint 1, Blocos B-D)

> Prompt de instrução para uma nova sessão do Claude Code retomar o
> desenvolvimento do sistema `carteira_auto`. Copie o conteúdo deste
> arquivo como mensagem inicial na nova sessão.

---

## Prompt

```
Leia o CLAUDE.md na raiz do projeto e os seguintes documentos:
- docs/dev/TECH_DEBT_INVENTORY.md (inventário de dívida técnica — 65 itens)
- docs/dev/ARCHITECTURE.md (mapa completo do código)
- docs/dev/DEVOPS.md (fluxo de CI/CD e como commitar/criar PRs)

Estado atual:
- Épico 0 Sprint 1 Bloco A: CONCLUÍDA (baseline limpo, TECH_DEBT_INVENTORY.md)
- Épico 0 Sprint 1 Blocos B-D: PENDENTES (segurança, docs, auditoria de testes)
- Fetcher Sprints A-B: CONCLUÍDAS
- Fetcher Sprints C-D: PENDENTES (aguardando conclusão do Épico 0)
- Testes: 697 passando (632 unit + 65 integration), 0 falhas.
  1 teste flaky: test_fred_fetcher.py::test_sem_api_key_levanta_permission_error
- pandas pinado em <3.0 por incompatibilidade com testes.

Retome o desenvolvimento a partir do Épico 0 Sprint 1 Bloco B (Segurança).
Consulte o SPRINT_LOG.md (seção "Sprint 1 Planning") para os itens SEC-001 a SEC-004.

Siga o protocolo de sprints do CLAUDE.md:
1. Audite o estado atual do código
2. Proponha o sprint com entregáveis concretos
3. Aguarde minha aprovação antes de implementar
4. Use `make check` antes de cada push
5. Crie PRs via `gh pr create` (nunca push direto no main)

Comunique-se em português brasileiro.
```

---

## Contexto para o humano

### O que foi feito no Épico 0 Sprint 1 Bloco A

**Objetivo:** Baseline limpo — zerar falhas, catalogar dívida técnica.

**Entregáveis:**
- Fixtures de teste criadas (`sample_portfolio.xlsx`, `test_config.yaml`)
- Contagem de testes unificada em 6 docs (697 = 632 unit + 65 integration)
- `docs/dev/TECH_DEBT_INVENTORY.md` com 65 itens rastreáveis por arquivo:linha
- Auditoria de decorators (12 decorators: 9 em uso, 3 sem uso com decisão documentada)
- 1 teste flaky identificado (leak de env vars entre testes)

**Decisões registradas:**
- BUG-001 (CVM 404): teste já isolado com @pytest.mark.integration, documentado
- BUG-002 (Excel fixture): premissa original incorreta (nenhum teste falhava),
  fixtures criadas para uso futuro
- DEBT-001: zero TODOs/FIXMEs no código, mas 65 itens reais de dívida técnica
  encontrados por auditoria manual
- 3 decorators sem uso mantidos (uso planejado em fases futuras)

### Próximos blocos do Sprint 1

**Bloco B — Segurança e Higiene** (`sprint-1/security-audit`):
- SEC-001: Validar .env.example completo
- SEC-002: Validar .gitignore
- SEC-003: Auditar git history + remediação
- SEC-004: Validar pre-commit detect-private-key

**Bloco C — Infraestrutura Documental** (`sprint-1/doc-infrastructure`):
- DOC-003: Commitar BACKLOG.md e DOCUMENT_MAP.md
- DOC-002: SPRINT_LOG.md retroativo
- APIDOC-001: Criar pasta docs/api_reference/
- APIDOC-009: Redirect api_reference.md antigo

**Bloco D — Auditoria de Testes** (`sprint-1/test-audit`):
- TAUD-001: Inventário de testes por módulo
- TAUD-004: Auditar marcadores @pytest.mark.integration

### Decisões técnicas importantes

- `FetchWithFallback` orquestra ENTRE fetchers (IngestNodes). `@fallback` opera DENTRO de um fetcher.
- Códigos SGS validados: dívida bruta/PIB = 13762, juros nominais/PIB = 5727.
- `economic.py` mantém `Optional[date]` (UP007/UP045 ignorados) por conflito Pydantic.
- pandas pinado `<3.0` — pandas 3.x quebra mocks do test_fiscal_analyzer.
- Testes de integração marcados com `@pytest.mark.integration` (excluídos do CI de PR).
- mypy com `continue-on-error: true` no CI (item 7.1 do TECH_DEBT_INVENTORY).
