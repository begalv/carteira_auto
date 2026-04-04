# Inventário de Dívida Técnica — carteira_auto

> **Gerado em:** 2026-04-04 (Sprint 1, Bloco A)
> **Método:** Auditoria completa de `src/`, `tests/`, CI/CD.
> **Próxima revisão:** Sprint 2
> **Regra:** Todo item deve ser rastreável por `arquivo:linha`.

---

## Sumário

| Categoria | Alta | Média | Baixa | Total |
|-----------|------|-------|-------|-------|
| Resource management | 2 | 3 | — | 5 |
| Error handling | — | 4 | 3 | 7 |
| Validação de entrada | — | 5 | 2 | 7 |
| Data integrity | — | 4 | 1 | 5 |
| Compatibilidade | 1 | — | — | 1 |
| Consistência | 1 | 1 | 2 | 4 |
| CI/CD e testes | 1 | 3 | — | 4 |
| Magic numbers | — | — | 10 | 10 |
| Código não utilizado | — | — | 4 | 4 |
| Cobertura de testes | — | 7 | 11 | 18 |
| **Total** | **5** | **27** | **33** | **65** |

---

## 1. Resource Management

| # | Sev | Arquivo | Linha | Problema |
|---|-----|---------|-------|----------|
| 1.1 | ALTA | `data/fetchers/tesouro_fetcher.py` | 121 | `self._session = requests.Session()` — session criada sem `__del__` nem context manager. Acumula conexões abertas. |
| 1.2 | ALTA | `data/fetchers/cvm_fetcher.py` | 84 | `self._session = requests.Session()` — mesmo padrão: session sem cleanup. |
| 1.3 | MÉDIA | `data/fetchers/fred_fetcher.py` | 413 | `requests.get(url, ...)` — cada chamada cria conexão nova em vez de reusar session. |
| 1.4 | MÉDIA | `data/fetchers/ddm_fetcher.py` | 620 | `requests.get(url, ...)` — mesmo padrão: sem connection pooling. |
| 1.5 | MÉDIA | `data/fetchers/bcb/_focus.py` | 875 | `ThreadPoolExecutor` — usa `with` block (OK), mas exceções internas não discriminam tipo (ver 2.3). |

**Sugestão global:** Adicionar `__enter__`/`__exit__` nos fetchers com session, e `self._session = requests.Session()` nos que usam `requests.get()` direto.
**Sprint:** Fetcher Sprint C

---

## 2. Error Handling

| # | Sev | Arquivo | Linha | Problema |
|---|-----|---------|-------|----------|
| 2.1 | MÉDIA | `analyzers/commodity_analyzer.py` | 116 | `except Exception: pass` — exceção engolida sem logging no cálculo de cycle_signal. |
| 2.2 | MÉDIA | `core/nodes/ingest_nodes.py` | 512 | `return None` — `_normalize_ddm_list()` retorna None sem logar motivo (lista vazia). |
| 2.3 | MÉDIA | `core/nodes/ingest_nodes.py` | 533 | `return None` — segundo return None sem log (campos date/value ausentes). |
| 2.4 | MÉDIA | `data/fetchers/ibge_fetcher.py` | 890 | Fallback sidrapy→HTTP loga warning mas perde o traceback da exceção original. |
| 2.5 | BAIXA | `analyzers/commodity_analyzer.py` | 159 | `pass` isolado em branch de error handler — implementação incompleta. |
| 2.6 | BAIXA | `data/lake/reference_lake.py` | 708 | `pass` isolado em branch de error handler. |
| 2.7 | BAIXA | `core/nodes/ingest_nodes.py` | 669 | `pass` isolado em branch de error handler. |

**Sprint:** 2.1 → Épico 0; 2.2–2.3 → Sprint D; 2.4 → Sprint C; 2.5–2.7 → postergar.

---

## 3. Validação de Entrada

| # | Sev | Arquivo | Linha | Problema |
|---|-----|---------|-------|----------|
| 3.1 | MÉDIA | `data/fetchers/cvm_fetcher.py` | 261 | `get_dfp(cnpj: str, ...)` — aceita qualquer string sem validar formato CNPJ. |
| 3.2 | MÉDIA | `data/fetchers/bcb/_ptax.py` | 33 | `get_ptax_currency(currency_code: str, ...)` — aceita qualquer string sem validar contra moedas suportadas. |
| 3.3 | MÉDIA | `data/fetchers/bcb/_taxajuros.py` | 36 | `get_lending_rates(modality: str, ...)` — aceita string livre, retorna DataFrame vazio silenciosamente se inválida. |
| 3.4 | MÉDIA | `data/fetchers/fred_fetcher.py` | 101 | `if not self._api_key: logger.warning(...)` — key ausente gera só warning, falha com PermissionError na primeira chamada. |
| 3.5 | MÉDIA | `data/fetchers/ddm_fetcher.py` | 77 | `if not self._api_key: logger.warning(...)` — mesmo padrão: warning no init, erro na chamada. |
| 3.6 | BAIXA | `core/nodes/portfolio_nodes.py` | 89 | `ctx["portfolio"]` — acesso direto sem `.get()`. DAG garante existência, mas KeyError sem contexto se falhar. |
| 3.7 | BAIXA | `data/fetchers/cvm_fetcher.py` | 110 | `encoding="latin-1"` hardcoded. Também na linha 426. |

**Sprint:** 3.1–3.5 → Sprint C; 3.6–3.7 → postergar.

---

## 4. Data Integrity

| # | Sev | Arquivo | Linha | Problema |
|---|-----|---------|-------|----------|
| 4.1 | MÉDIA | `data/fetchers/tesouro_fetcher.py` | 230 | `str.contains("NTN-B Principal", na=False)` — matching por string exata, sem normalização (strip/upper). |
| 4.2 | MÉDIA | `data/fetchers/tesouro_fetcher.py` | 352 | `_fetch_csv()` filtra colunas disponíveis sem logar quais estão ausentes. |
| 4.3 | MÉDIA | `data/fetchers/bcb/_taxajuros.py` | 156 | `.collect()` — OData pode retornar resultado paginado incompleto sem aviso. Também linhas 173, 195, 248. |
| 4.4 | MÉDIA | `core/nodes/ingest_nodes.py` | 494 | `group[unit_field].iloc[0]` — sem `group.empty` check antes de `iloc[0]`. |
| 4.5 | BAIXA | `analyzers/market_analyzer.py` | 73 | `closes.iloc[-1] / closes.iloc[0]` — sem check de divisão por zero. Também linhas 86, 108, 122, 135. |

**Sprint:** 4.1–4.3 → Sprint C; 4.4 → Sprint D; 4.5 → postergar.

---

## 5. Compatibilidade

| # | Sev | Arquivo | Linha | Problema |
|---|-----|---------|-------|----------|
| 5.1 | ALTA | `utils/decorators.py` | 92 | `signal.alarm(seconds)` — POSIX-only, crash em Windows. Projeto macOS-only por ora, documentar limitação. |

**Sprint:** Postergar (projeto pessoal, macOS).

---

## 6. Consistência

| # | Sev | Arquivo | Linha | Problema |
|---|-----|---------|-------|----------|
| 6.1 | ALTA | `data/fetchers/yahoo_fetcher.py` | 115 vs 142 | Retorno inconsistente: linha 115 retorna `pd.DataFrame()`, linha 142 retorna `None`. Cada fetcher trata respostas vazias de forma diferente. |
| 6.2 | MÉDIA | `analyzers/risk_analyzer.py` | 98 | Error key `"analyze_risk._calculate_risk"` — formato `node._method`. Outros analyzers (commodity:119, macro:160) usam `"node.partial"`. Inconsistente. |
| 6.3 | BAIXA | `analyzers/risk_analyzer.py` | 102 | `tickers: list, columns` — type hints sem parâmetro de tipo. Deveria ser `list[str]`, `pd.Index`. |
| 6.4 | BAIXA | `utils/decorators.py` | 267 | `hashlib.md5(str(key_data).encode())` — MD5 para cache key. Funcional, mas pode triggar alertas de segurança. |

**Sprint:** 6.1 → Sprint C (convenção); 6.2–6.4 → postergar.

---

## 7. CI/CD e Testes

| # | Sev | Arquivo | Linha | Problema |
|---|-----|---------|-------|----------|
| 7.1 | ALTA | `.github/workflows/ci.yml` | 39 | `continue-on-error: true` — falhas de mypy não bloqueiam CI. |
| 7.2 | MÉDIA | `tests/unit/test_decorators.py` | 125 | `time.sleep(5)` — teste de timeout com sleep real. Também linha 298: `time.sleep(1.1)`. Testes lentos e flaky. |
| 7.3 | MÉDIA | `.pre-commit-config.yaml` | 20 | `rev: v0.15.7` — ruff pinado, pode divergir do pyproject.toml. |
| 7.4 | MÉDIA | `pyproject.toml` | 188 | `markers = ["unit: ...", ...]` — marker `@pytest.mark.unit` definido mas nunca aplicado nos testes. |

**Sprint:** 7.1 → Épico 0; 7.2–7.4 → Sprint 1 Bloco D.

---

## 8. Magic Numbers

| # | Arquivo | Linha | Valor | Significado | Nome sugerido |
|---|---------|-------|-------|-------------|---------------|
| 8.1 | `core/nodes/ingest_nodes.py` | 191 | `20` | Batch size preços | `BATCH_SIZE_PRICES` |
| 8.2 | `analyzers/risk_analyzer.py` | 78 | `252` | Dias pregão/ano | `TRADING_DAYS_PER_YEAR` |
| 8.3 | `analyzers/risk_analyzer.py` | 67 | `20` | Rows mín. vol. | `MIN_ROWS_VOLATILITY` |
| 8.4 | `analyzers/commodity_analyzer.py` | 94 | `21` | 1 mês (dias úteis) | `PERIOD_1M_DAYS` |
| 8.5 | `analyzers/commodity_analyzer.py` | 95 | `63` | 3 meses (dias úteis) | `PERIOD_3M_DAYS` |
| 8.6 | `analyzers/commodity_analyzer.py` | 96 | `252` | 12 meses (dias úteis) | `PERIOD_12M_DAYS` |
| 8.7 | `analyzers/commodity_analyzer.py` | 223 | `1.20` | Threshold ciclo | `CYCLE_SIGNAL_THRESHOLD` |
| 8.8 | `analyzers/fiscal_analyzer.py` | 62 | `2*365` | Lookback 2 anos | `LOOKBACK_2Y_DAYS` |
| 8.9 | `analyzers/macro_analyzer.py` | 69 | `365` | Lookback 1 ano | `LOOKBACK_1Y_DAYS` |
| 8.10 | `analyzers/market_analyzer.py` | 93 | `5*365` | Lookback 5 anos | `LOOKBACK_5Y_DAYS` |

Todos severidade BAIXA. **Sprint:** Épico 0 — padronização de constants.

---

## 9. Código Não Utilizado

| # | Sev | Arquivo | Linha | Problema |
|---|-----|---------|-------|----------|
| 9.1 | BAIXA | `utils/decorators.py` | 108 | `def fallback(...)` — decorator definido, 0 usos. Planejado para Sprint D (IngestNodes). |
| 9.2 | BAIXA | `utils/decorators.py` | 171 | `def validate_positive_value(...)` — 0 usos. Planejado para Fase 3 (Strategies). |
| 9.3 | BAIXA | `utils/decorators.py` | 191 | `def validate_allocation_sum(...)` — 0 usos. Planejado para Fase 3 (Rebalancer). |
| 9.4 | BAIXA | `data/exporters/report_generator.py` | 1 | Arquivo vazio (0 linhas). Placeholder sem implementação. |

**Sprint:** 9.1 → Sprint D; 9.2–9.3 → Fase 3; 9.4 → remover ou implementar.

---

## 10. Cobertura de Testes — Módulos Sem Teste Dedicado

Módulos em `src/carteira_auto/` sem arquivo `test_*.py` correspondente.
Rastreável pelo `class` ou `def` principal de cada módulo.

### Prioridade MÉDIA (módulos com lógica de negócio)

| # | Módulo | Linhas | Ponto de entrada |
|---|--------|--------|------------------|
| 10.1 | `analyzers/risk_analyzer.py` | 206 | `class RiskAnalyzer(Node):` linha 19 |
| 10.2 | `analyzers/portfolio_analyzer.py` | 121 | `class PortfolioAnalyzer(Node):` linha 18 |
| 10.3 | `analyzers/macro_analyzer.py` | 201 | `class MacroAnalyzer(Node):` linha 18 |
| 10.4 | `analyzers/market_analyzer.py` | 187 | `class MarketAnalyzer(Node):` linha 24 |
| 10.5 | `analyzers/rebalancer.py` | 168 | `class Rebalancer(Node):` linha 19 |
| 10.6 | `data/loaders/excel_loader.py` | 199 | `class ExcelLoader:` linha 15 |
| 10.7 | `core/nodes/storage_nodes.py` | 83 | `class SaveSnapshotNode(Node):` linha 9 |

### Prioridade BAIXA (módulos auxiliares, alertas, exporters)

| # | Módulo | Linhas | Ponto de entrada |
|---|--------|--------|------------------|
| 10.8 | `data/exporters/excel_exporter.py` | 168 | `class ExcelExporter:` linha 12 |
| 10.9 | `data/storage/snapshot_store.py` | 140 | `class SnapshotStore:` linha 14 |
| 10.10 | `core/nodes/alert_nodes.py` | 49 | `class EvaluateAlertsNode(Node):` linha 9 |
| 10.11 | `core/pipelines/update_excel_prices.py` | 81 | Módulo pipeline sem teste dedicado |
| 10.12 | `alerts/engine.py` | 153 | `class AlertEngine:` linha 31 |
| 10.13 | `alerts/channels.py` | 62 | `class ConsoleChannel(AlertChannel):` linha 28 |
| 10.14 | `alerts/rules.py` | 42 | Módulo importado via `alerts/engine.py` (AlertRule linha 12) |
| 10.15 | `utils/logger.py` | 183 | `def setup_logging():` linha 28 |
| 10.16 | `analyzers/economic_sector_analyzer.py` | 60 | `class EconomicSectorAnalyzer(Node):` linha 15 |
| 10.17 | `analyzers/market_sector_analyzer.py` | 61 | `class MarketSectorAnalyzer(Node):` linha 15 |
| 10.18 | `data/exporters/report_generator.py` | 0 | Arquivo vazio (ver 9.4). |

**Total:** 2.164 linhas de código sem cobertura de testes dedicada.
**Sprint:** 10.1–10.7 → Sprint 1 Bloco D / Sprint 2; 10.8–10.18 → Sprint 3+.

---

## 11. Falsos Positivos Investigados

| Arquivo | Linha | Investigação | Resultado |
|---------|-------|-------------|-----------|
| `ingest_nodes.py` | 200 | `except Exception` em batch | **OK** — `logger.warning()` presente |
| `risk_analyzer.py` | 67 | `np.percentile()` sem validação | **OK** — `len < 20` validado |
| `fiscal_analyzer.py` | 161 | `return None` sem logging | **OK** — validação de entrada |
| `tesouro_fetcher.py` | 144 | Missing `.empty` check | **OK** — operações seguras |
| `yahoo_fetcher.py` | 122 | Empty DataFrame return | **OK** — `exc_info=True` |
| `commodity_analyzer.py` | 64 | Condicional suspeita | **OK** — ternário intencional |
| `core/engine.py` | 56 | Union type handling | **OK** — design intencional |
| `bcb/_focus.py` | 875 | ThreadPoolExecutor sem cleanup | **OK** — usa `with` block |
| `bcb/_ptax.py` | 198 | ThreadPoolExecutor sem cleanup | **OK** — usa `with` block |

---

## 12. Próximos Passos

| Sprint | Itens |
|--------|-------|
| Sprint 1 Bloco D | 7.2, 7.4, cobertura 10.1–10.7 |
| Fetcher Sprint C | 1.1–1.4, 2.4, 3.1–3.5, 4.1–4.3, 6.1 |
| Fetcher Sprint D | 2.2–2.3, 4.4, 9.1 |
| Épico 0 restante | 2.1, 7.1, magic numbers (8.1–8.10) |
| Fase 3 | 9.2–9.3 |
| Sprint 2+ | Cobertura 10.8–10.18 |
