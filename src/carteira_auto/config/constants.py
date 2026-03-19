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

    HOLIDAYS_B3: list[str] = [
        "2026-01-01",
        "2026-02-16",
        "2026-02-17",
        "2026-04-02",
        "2026-04-21",
        "2026-05-01",
        "2026-09-07",
        "2026-10-12",
        "2026-11-02",
        "2026-11-15",
        "2026-12-24",
        "2026-12-25",
        "2026-12-31",
    ]

    # ============================================================================
    # COLUNAS E TEMPLATES
    # ============================================================================

    EXCEL_TEMPLATE_COLUMNS: list[str] = [
        "Ticker",
        "Nome",
        "Tipo",
        "Categoria",
        "Quantidade",
        "Preço Médio",
        "Preço Atual",
        "Valor Investido",
        "Valor Atual",
        "Rentabilidade",
        "Percentual Carteira",
        "Meta Alocação",
        "Desvio",
        "Ação",
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
    # MENSAGENS E TEXTOS
    # ============================================================================

    ERROR_MESSAGES: dict[str, str] = {
        "DATA_FETCH_ERROR": "Erro ao buscar dados para o ticker {ticker}",
        "INVALID_TICKER": "Ticker {ticker} não encontrado ou inválido",
        "INSUFFICIENT_DATA": "Dados insuficientes para análise",
        "REBALANCE_THRESHOLD_NOT_MET": "Desvio ({deviation:.2%}) abaixo do threshold ({threshold:.2%})",
    }

    SUCCESS_MESSAGES: dict[str, str] = {
        "DATA_FETCH_SUCCESS": "Dados atualizados com sucesso para {count} ativos",
        "REBALANCE_TRIGGERED": "Rebalanceamento recomendado para {count} ativos",
        "REPORT_GENERATED": "Relatório gerado com sucesso: {filepath}",
    }

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
    }


constants = Constants()
