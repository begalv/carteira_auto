# Próximo Sprint — Continuação dos Fetchers

> Prompt de instrução para uma nova sessão do Claude Code retomar o
> desenvolvimento do sistema `carteira_auto`. Copie o conteúdo deste
> arquivo como mensagem inicial na nova sessão.

---

## Prompt

```
Leia o CLAUDE.md na raiz do projeto e os seguintes documentos:
- docs/system/plano_implementacao_carteira_auto.md (seção "Fetcher Maximization Sprint")
- docs/dev/ARCHITECTURE.md (mapa completo do código)
- docs/dev/PATTERNS.md (templates de fetchers e analyzers)
- docs/dev/DEVOPS.md (fluxo de CI/CD e como commitar/criar PRs)

Estado atual:
- Fetcher Sprint A: CONCLUÍDA (deps, constants, FetchWithFallback, ReferenceLake)
- Fetcher Sprint B: CONCLUÍDA (BCBFetcher 6 mixins incl. MercadoImobiliário, IBGEFetcher +analfabetismo +fix D3N/D4N, FREDFetcher +11 methods + FRED_SERIES unificada)
- Fetcher Sprint C: Pendente (Yahoo, DDM, Tesouro, CVM + TradingComDadosFetcher)
- Fetcher Sprint D: Pendente (IngestNodes com fallback, testes integração, docs)
- CI/CD: GitHub Actions configurado (lint, format, test). Makefile disponível.
- Testes: 697 passando (unit), 1 falha pré-existente (CVM 404). mypy com continue-on-error.
- pandas pinado em <3.0 por incompatibilidade com testes.

Retome o desenvolvimento a partir do Fetcher Sprint C.
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

### O que já foi feito nos Fetcher Sprints

**Sprint A (CONCLUÍDA):**
- Dependências: python-bcb, sidrapy, tradingcomdados
- Constants expandidos: BCB 57 séries SGS, IBGE 17 tabelas SIDRA, FRED 38 séries, 6 índices B3
- `fetch_with_fallback()` helper para fallback entre fetchers
- ReferenceLake com 12 tabelas de referência

**Sprint B (CONCLUÍDA):**
- B.1: BCBFetcher expandido (python-bcb SGS, Expectativas Focus, PTAX, TaxaJuros)
- B.2: IBGEFetcher expandido (sidrapy, CNAE, Países)
- B.3: FREDFetcher expandido (23 convenience methods, FRED_SERIES unificada em constants.py)
- B.4: Auditoria e fechamento — bcb_fetcher.py deletado (módulo bcb/ é definitivo),
  BCBMercadoImobiliarioMixin (14 métodos imobiliários), fix D3N/D4N IBGE,
  get_analfabetismo(), @cache_result em get_sidra_table/get_cnae_search,
  129 testes BCB + 55 testes FRED (total: 697)

**Sprint C (PENDENTE):**
- Yahoo: histórico de dividendos, splits, financials
- DDM: expansão de screening
- Tesouro: taxas indicativas via CKAN
- CVM: fundos, demonstrações
- TradingComDadosFetcher: novo fetcher

**Sprint D (PENDENTE):**
- IngestNodes com fallback hierárquico
- Testes de integração completos
- Documentação final dos fetchers

### Decisões técnicas importantes

- `FetchWithFallback` orquestra ENTRE fetchers (IngestNodes). `@fallback` opera DENTRO de um fetcher.
- Códigos SGS validados: dívida bruta/PIB = 13762, juros nominais/PIB = 5727.
- `economic.py` mantém `Optional[date]` (UP007/UP045 ignorados) por conflito Pydantic.
- pandas pinado `<3.0` — pandas 3.x quebra mocks do test_fiscal_analyzer.
- Testes de integração marcados com `@pytest.mark.integration` (excluídos do CI de PR).
