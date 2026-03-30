"""Conteúdos e constantes estáticas da aplicação."""


class Constants:
    # ============================================================================
    # CONFIGURAÇÕES DE MERCADO
    # ============================================================================

    MARKET_SESSIONS: dict[str, tuple[str, str]] = {
        "B3": ("10:00", "17:00"),  # Horário de pregão B3
        "NYSE": ("09:30", "16:00"),  # Horário Eastern Time
        "CRYPTO": ("00:00", "23:59"),  # Mercado 24/7
    }

    # ============================================================================
    # COLUNAS DA PLANILHA REAL
    # ============================================================================

    CARTEIRA_SHEET_NAMES: dict[str, str] = {
        "carteira": "Carteira",
        "resumo": "Rentabilidade Carteira",
        "vendas": "Vendas",
    }

    CARTEIRA_COLUMNS: list[str] = [
        "Ticker",
        "Nome do Ativo / Gestora",
        "Classe",
        "Setor",
        "Subsetor",
        "Segmento",
        "% Meta",
        "Valor Meta",
        "% Atual",
        "% Inicial",
        "Posição Atual",
        "Preço Posição",
        "Valorização",
        "Valorização (%)",
        "Proventos Recebidos",
        "Diferença",
        "Rentabilidade",
        "Rentabilidade Proporcional a Carteira",
        "Preço Atual",
        "Preço Médio",
        "N Cotas Atual",
    ]

    # Índices de coluna (1-based, para uso com openpyxl)
    CARTEIRA_TICKER_COL: int = CARTEIRA_COLUMNS.index("Ticker") + 1
    CARTEIRA_PRECO_ATUAL_COL: int = CARTEIRA_COLUMNS.index("Preço Atual") + 1

    CARTEIRA_FIELD_MAP: dict[str, str] = {
        "Ticker": "ticker",
        "Nome do Ativo / Gestora": "nome",
        "Classe": "classe",
        "Setor": "setor",
        "Subsetor": "subsetor",
        "Segmento": "segmento",
        "% Meta": "pct_meta",
        "Valor Meta": "valor_meta",
        "% Atual": "pct_atual",
        "% Inicial": "pct_inicial",
        "Posição Atual": "posicao_atual",
        "Preço Posição": "preco_posicao",
        "Valorização": "valorizacao",
        "Valorização (%)": "valorizacao_pct",
        "Proventos Recebidos": "proventos_recebidos",
        "Diferença": "diferenca",
        "Rentabilidade": "rentabilidade",
        "Rentabilidade Proporcional a Carteira": "rentabilidade_proporcional",
        "Preço Atual": "preco_atual",
        "Preço Médio": "preco_medio",
        "N Cotas Atual": "n_cotas_atual",
    }

    VENDAS_COLUMNS: list[str] = [
        "Categoria",
        "Ticker",
        "Nome do Ativo / Gestora",
        "Classe",
        "Setor",
        "Valor da Venda",
        "Preço Posição",
        "Valorização",
        "Proventos Recebidos",
        "Diferença",
        "Rentabilidade individual",
        "Preço na Venda",
        "Preço Médio de Compra",
        "N Cotas Vendidas",
        "Mês",
    ]

    VENDAS_FIELD_MAP: dict[str, str] = {
        "Categoria": "categoria",
        "Ticker": "ticker",
        "Nome do Ativo / Gestora": "nome",
        "Classe": "classe",
        "Setor": "setor",
        "Valor da Venda": "valor_venda",
        "Preço Posição": "preco_posicao",
        "Valorização": "valorizacao",
        "Proventos Recebidos": "proventos_recebidos",
        "Diferença": "diferenca",
        "Rentabilidade individual": "rentabilidade_individual",
        "Preço na Venda": "preco_na_venda",
        "Preço Médio de Compra": "preco_medio_compra",
        "N Cotas Vendidas": "n_cotas_vendidas",
        "Mês": "mes",
    }

    # Tickers que não têm dados no Yahoo Finance (Tesouro Direto, etc.)
    NON_YAHOO_TICKERS: set[str] = {"LFT", "NTNB", "NTNF", "LTN"}

    # ============================================================================
    # BCB — SÉRIES DO SGS (Sistema Gerenciador de Séries Temporais)
    # ============================================================================

    BCB_SERIES_CODES: dict[str, int] = {
        # ---- Taxas de juros e rendimento ----
        "selic": 432,  # Taxa Selic (meta) — % a.a.
        "cdi": 12,  # Taxa CDI — % a.d.
        "cdi_anualizado": 4389,  # CDI taxa anualizada — % a.a.
        "tr": 226,  # Taxa Referencial — % a.m.
        "poupanca": 25,  # Rendimento poupança — % a.m.
        # ---- Inflação ----
        "ipca": 433,  # IPCA — variação mensal %
        "igpm": 189,  # IGP-M — variação mensal %
        "inpc": 188,  # INPC — variação mensal %
        # ---- Câmbio ----
        "ptax_compra": 10813,  # PTAX USD compra — R$
        "ptax_venda": 1,  # PTAX USD venda — R$
        "taxa_cambio_real": 11752,  # Taxa de câmbio real efetiva (IPCA) — índice
        # ---- Fiscal ----
        "divida_bruta_pib": 13762,  # Dívida Bruta do Governo Geral / PIB — %
        "divida_liquida_pib": 4503,  # Dívida Líquida do Setor Público / PIB — %
        "resultado_primario_pib": 5793,  # Resultado Primário acum. 12m / PIB — %
        "resultado_nominal": 4649,  # Resultado Nominal acum. 12m — R$ milhões
        "juros_nominais_pib": 5727,  # Juros Nominais acum. 12m / PIB — %
        # ---- Atividade econômica ----
        "ibc_br": 24364,  # Índice de Atividade Econômica do BCB — índice
        "confianca_empresario": 7344,  # Índice de confiança empresarial — índice
        # ---- Mercado e risco ----
        "ibovespa_bcb": 7,  # Índice Bovespa (fechamento) — pontos
        "ouro_bmf": 4,  # Cotação ouro BM&F — R$/g
        "embi_brasil": 40940,  # EMBI+ Brasil (risco-país) — pontos base
        # ---- Crédito ----
        "credito_pib": 20539,  # Crédito total ao setor privado / PIB — %
        "inadimplencia_pf": 21085,  # Taxa de inadimplência PF — %
        # ---- Agregados monetários ----
        "m1": 27789,  # Base monetária M1 — R$ milhões
        "m2": 27810,  # Base monetária M2 — R$ milhões
        "m4": 27815,  # Base monetária M4 — R$ milhões
        # ---- Setor externo ----
        "balanca_comercial": 22707,  # Saldo balança comercial mensal — US$ milhões
        "reservas_internacionais": 3546,  # Reservas internacionais (liquidez) — US$ milhões
    }

    # ============================================================================
    # IBGE — TABELAS DO SIDRA
    # ============================================================================

    IBGE_TABLE_IDS: dict[str, int] = {
        # ---- Inflação ----
        "ipca": 1737,  # IPCA — variação mensal (série histórica)
        "ipca_nova": 7060,  # IPCA — série 2020+ por grupos
        "ipca_subitens": 1419,  # IPCA — por subitens
        "ipca15": 7062,  # IPCA-15 (prévia) — variação mensal
        "ipca_grupos": 7113,  # IPCA — variação e peso por grupos
        # ---- PIB ----
        "pib_trimestral": 5932,  # PIB trimestral — taxa de variação (%)
        "pib_dessazonalizado": 1621,  # PIB dessazonalizado — índice
        "pib_nominal": 5938,  # PIB preços correntes — R$ milhões
        # ---- Emprego ----
        "pnad_desocupacao": 6381,  # PNAD — taxa de desocupação (%)
        "pnad_rendimento": 6022,  # PNAD — rendimento médio real (R$)
        "pnad_subutilizacao": 4093,  # PNAD — taxa de subutilização (%)
        # ---- Atividade econômica setorial ----
        "pim_pf": 8888,  # PIM-PF — produção industrial mensal (índice)
        "pmc": 8881,  # PMC — comércio varejista mensal (índice)
        "pms": 8162,  # PMS — serviços mensal (índice)
        # ---- Construção ----
        "sinapi": 2296,  # SINAPI — custo da construção civil (índice)
    }

    # ============================================================================
    # FRED — SÉRIES ECONÔMICAS DOS EUA
    # ============================================================================

    FRED_SERIES: dict[str, dict[str, str]] = {
        # ---- Taxas de juros (existentes) ----
        "DFF": {"name": "Federal Funds Rate", "unit": "%", "freq": "daily"},
        "DGS2": {"name": "Treasury 2Y Yield", "unit": "%", "freq": "daily"},
        "DGS10": {"name": "Treasury 10Y Yield", "unit": "%", "freq": "daily"},
        "DGS30": {"name": "Treasury 30Y Yield", "unit": "%", "freq": "daily"},
        "T10Y2Y": {"name": "10Y-2Y Yield Spread", "unit": "%", "freq": "daily"},
        "VIXCLS": {"name": "VIX Volatility Index", "unit": "index", "freq": "daily"},
        "CPIAUCSL": {
            "name": "CPI All Urban Consumers",
            "unit": "index",
            "freq": "monthly",
        },
        "DEXBZUS": {"name": "BRL/USD Exchange Rate", "unit": "R$/US$", "freq": "daily"},
        "UNRATE": {"name": "US Unemployment Rate", "unit": "%", "freq": "monthly"},
        "A191RL1Q225SBEA": {
            "name": "US Real GDP Growth",
            "unit": "%",
            "freq": "quarterly",
        },
        "BAMLH0A0HYM2": {"name": "High Yield Spread", "unit": "%", "freq": "daily"},
        "T10YIE": {"name": "10Y Breakeven Inflation", "unit": "%", "freq": "daily"},
        # ---- Novas séries ----
        "FEDFUNDS": {"name": "Effective Fed Funds Rate", "unit": "%", "freq": "daily"},
        "DGS1": {"name": "Treasury 1Y Yield", "unit": "%", "freq": "daily"},
        "DGS5": {"name": "Treasury 5Y Yield", "unit": "%", "freq": "daily"},
        "DGS7": {"name": "Treasury 7Y Yield", "unit": "%", "freq": "daily"},
        "DGS20": {"name": "Treasury 20Y Yield", "unit": "%", "freq": "daily"},
        "DTWEXBGS": {
            "name": "Trade Weighted Dollar Index",
            "unit": "index",
            "freq": "daily",
        },
        "TEDRATE": {"name": "TED Spread", "unit": "%", "freq": "daily"},
        "MORTGAGE30US": {
            "name": "30-Year Mortgage Rate",
            "unit": "%",
            "freq": "weekly",
        },
        "UMCSENT": {
            "name": "Michigan Consumer Sentiment",
            "unit": "index",
            "freq": "monthly",
        },
        "PERMIT": {"name": "Building Permits", "unit": "thousands", "freq": "monthly"},
        "M2SL": {"name": "M2 Money Supply", "unit": "USD billions", "freq": "monthly"},
        "WALCL": {"name": "Fed Total Assets", "unit": "USD millions", "freq": "weekly"},
        "GFDEBTN": {
            "name": "US Federal Debt Total",
            "unit": "USD millions",
            "freq": "quarterly",
        },
        "DCOILWTICO": {
            "name": "WTI Crude Oil Price",
            "unit": "USD/barrel",
            "freq": "daily",
        },
        "GOLDAMGBD228NLBM": {
            "name": "Gold London Fix",
            "unit": "USD/oz",
            "freq": "daily",
        },
        "DPRIME": {"name": "Prime Rate", "unit": "%", "freq": "daily"},
        "BOPGSTB": {
            "name": "US Trade Balance",
            "unit": "USD millions",
            "freq": "monthly",
        },
        "PAYEMS": {"name": "Nonfarm Payrolls", "unit": "thousands", "freq": "monthly"},
        "CSUSHPISA": {
            "name": "Case-Shiller Home Price Index",
            "unit": "index",
            "freq": "monthly",
        },
    }

    # ============================================================================
    # ÍNDICES DE MERCADO — COMPOSIÇÃO A RASTREAR
    # ============================================================================

    INDEX_CODES: list[str] = [
        "IBOV",  # Ibovespa
        "IFIX",  # Índice de Fundos Imobiliários
        "IDIV",  # Índice Dividendos
        "SMLL",  # Small Cap
        "IBXX",  # IBrX-100
        "BDRX",  # BDRs
    ]

    REPORT_SECTIONS: list[str] = [
        "resumo_executivo",
        "alocacao_por_categoria",
        "alocacao_por_ativo",
        "performance",
        "recomendacoes_rebalanceamento",
        "riscos_e_alertas",
        "projecoes",
    ]

    # ============================================================================
    # VALIDAÇÕES
    # ============================================================================

    VALID_TICKER_PATTERNS: dict[str, str] = {
        # AÇÕES B3: 4 letras + unidade (3,4,5,6,7)
        "B3_STOCK": r"^[A-Z]{4}[34567]$",
        # FUNDOS IMOBILIÁRIOS: 4 letras + 11
        "B3_FII": r"^[A-Z]{4}11$",
        # ETFs: 4 letras + (11 ou 39)
        "B3_ETF": r"^[A-Z]{4}(11|39)$",
        # BDRs: 4 letras + 34
        "B3_BDR": r"^[A-Z]{4}34$",
        # ÍNDICES: ^ com 2 dígitos
        "B3_INDEX": r"^\^[A-Z]{2}$",  # ^BVSP, ^IFIX
        # ── Formatos Yahoo Finance ──────────────────────────────────────────
        # Ações B3 com sufixo .SA: PETR4.SA, VALE3.SA, HGLG11.SA
        "YAHOO_BR": r"^[A-Z]{4}[34567]\.SA$",
        "YAHOO_BR_FII": r"^[A-Z]{4}11\.SA$",
        "YAHOO_BR_ETF": r"^[A-Z]{4}(11|39)\.SA$",
        "YAHOO_BR_BDR": r"^[A-Z]{4}34\.SA$",
        # Índices globais: ^GSPC, ^BVSP, ^FTSE, ^DJI, ^IXIC
        "YAHOO_INDEX": r"^\^[A-Z]{2,6}$",
        # Crypto: BTC-USD, ETH-USD, SOL-USD
        "YAHOO_CRYPTO": r"^[A-Z]{2,5}-[A-Z]{2,4}$",
        # Futuros: CL=F (petróleo), GC=F (ouro), ES=F (S&P)
        "YAHOO_FUTURES": r"^[A-Z]{1,3}=F$",
        # Pares cambiais spot: BRL=X, EUR=X, USDBRL=X, EURUSD=X
        "YAHOO_CURRENCY": r"^[A-Z]{2,6}=X$",
        # Tickers especiais Yahoo: DX-Y.NYB (Dollar Index), etc.
        "YAHOO_SPECIAL": r"^[A-Z0-9]{1,5}-[A-Z0-9]{1,5}\.[A-Z]{2,5}$",
        # Índices BR no Yahoo com sufixo .SA sem dígito: IFIX.SA, IBOV.SA
        "YAHOO_BR_INDEX": r"^[A-Z]{3,6}\.SA$",
    }


constants = Constants()
