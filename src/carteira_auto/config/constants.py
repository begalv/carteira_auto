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
        "selic": 432,  # Taxa Selic (meta) — % a.a.
        "cdi": 12,  # Taxa CDI — % a.d.
        "ipca": 433,  # IPCA — variação mensal %
        "ptax_compra": 10813,  # PTAX USD compra — R$
        "ptax_venda": 1,  # PTAX USD venda — R$
        "igpm": 189,  # IGP-M — variação mensal %
        "tr": 226,  # Taxa Referencial — % a.m.
        "inpc": 188,  # INPC — variação mensal %
        "poupanca": 25,  # Rendimento poupança — % a.m.
        # ---- Fiscal ----
        "divida_bruta_pib": 13762,  # Dívida Bruta do Governo Geral / PIB — %
        "divida_liquida_pib": 4503,  # Dívida Líquida do Setor Público / PIB — %
        "resultado_primario_pib": 5793,  # Resultado Primário acum. 12m / PIB — %
        "resultado_nominal": 4649,  # Resultado Nominal acum. 12m — R$ milhões
        "juros_nominais_pib": 5727,  # Juros Nominais acum. 12m / PIB — %
        # ---- Câmbio ----
        "taxa_cambio_real": 11752,  # Taxa de câmbio real efetiva (IPCA) — índice
    }

    # ============================================================================
    # IBGE — TABELAS DO SIDRA
    # ============================================================================

    IBGE_TABLE_IDS: dict[str, int] = {
        "ipca": 1737,  # IPCA — variação mensal
        "ipca_grupos": 7060,  # IPCA por grupos
        "pib_trimestral": 5932,  # PIB trimestral — taxa de variação (%)
        "pnad_desocupacao": 6381,  # PNAD — taxa de desocupação
    }

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
        # Tickers especiais Yahoo: DX-Y.NYB (Dollar Index), etc.
        "YAHOO_SPECIAL": r"^[A-Z0-9]{1,5}-[A-Z0-9]{1,5}\.[A-Z]{2,5}$",
    }


constants = Constants()
