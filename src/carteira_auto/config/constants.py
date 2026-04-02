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
        "resumo": "Resumo da Carteira",
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
        "Ticker",
        "Nome do Ativo / Gestora",
        "Classe",
        "Setor",
        "Valor da Venda",
        "Preço Posição",
        "Valorização",
        "Valorização (%)",
        "Proventos Recebidos",
        "Diferença",
        "Rentabilidade",
        "Preço na Venda",
        "Preço Médio de Compra",
        "N Cotas Vendidas",
        "Posição Ativa",
        "Mês",
    ]

    VENDAS_FIELD_MAP: dict[str, str] = {
        "Ticker": "ticker",
        "Nome do Ativo / Gestora": "nome",
        "Classe": "classe",
        "Setor": "setor",
        "Valor da Venda": "valor_venda",
        "Preço Posição": "preco_posicao",
        "Valorização": "valorizacao",
        "Valorização (%)": "valorizacao_pct",
        "Proventos Recebidos": "proventos_recebidos",
        "Diferença": "diferenca",
        "Rentabilidade": "rentabilidade",
        "Preço na Venda": "preco_na_venda",
        "Preço Médio de Compra": "preco_medio_compra",
        "N Cotas Vendidas": "n_cotas_vendidas",
        "Posição Ativa": "posicao_ativa",
        "Mês": "mes",
    }

    # Tickers que não têm dados no Yahoo Finance (Tesouro Direto, etc.)
    NON_YAHOO_TICKERS: set[str] = {"LFT", "NTNB", "NTNF", "LTN"}

    # ============================================================================
    # BCB — FOCUS (Expectativas de Mercado — 13 endpoints OData)
    # ============================================================================

    # Indicadores via bcb.Expectativas → ExpectativasMercadoAnuais
    BCB_FOCUS_INDICATORS_ANUAIS: list[str] = [
        "Selic",
        "IPCA",
        "PIB Total",
        "Câmbio",
        "IGP-M",
        "IGP-DI",
        "IPC-Fipe",
        "Produção industrial",
        "Balança Comercial",
    ]

    # Indicadores via ExpectativaMercadoMensais
    BCB_FOCUS_INDICATORS_MENSAIS: list[str] = [
        "Selic",
        "IPCA",
        "IGP-M",
        "Câmbio",
    ]

    # Indicadores via ExpectativasMercadoTop5Anuais
    BCB_FOCUS_INDICATORS_TOP5_ANUAIS: list[str] = [
        "Selic",
        "IPCA",
        "PIB Total",
        "Câmbio",
        "IGP-M",
    ]

    # Indicadores via ExpectativasMercadoTrimestrais
    BCB_FOCUS_INDICATORS_TRIMESTRAIS: list[str] = [
        "Selic",
        "IPCA",
        "PIB Total",
        "Câmbio",
        "IGP-M",
    ]

    # Indicadores via ExpectativasMercadoTop5Mensais
    BCB_FOCUS_INDICATORS_TOP5_MENSAIS: list[str] = [
        "Selic",
        "IPCA",
        "IGP-M",
        "Câmbio",
    ]

    # Indicadores via ExpectativaMercadoTop5Trimestral
    BCB_FOCUS_INDICATORS_TOP5_TRIMESTRAIS: list[str] = [
        "Selic",
        "IPCA",
        "PIB Total",
        "Câmbio",
        "IGP-M",
    ]

    # ============================================================================
    # BCB — MERCADO IMOBILIÁRIO (indicadores curados de 2134 disponíveis)
    # ============================================================================

    BCB_MERCADO_IMOBILIARIO_INDICATORS: dict[str, str] = {
        # Índices macro (proxy mercado imobiliário)
        "ivg": "indices_ivg",
        "mvg": "indices_mvg",
        # Crédito PF — estoque (endividamento imobiliário)
        "credito_pf_sfh_total": "credito_estoque_carteira_credito_pf_sfh_to",
        "credito_pf_livre_total": "credito_estoque_carteira_credito_pf_livre_to",
        "credito_pf_fgts_total": "credito_estoque_carteira_credito_pf_fgts_to",
        # Inadimplência imobiliária PF
        "inadimplencia_pf_sfh_total": "credito_estoque_inadimplencia_pf_sfh_to",
        "inadimplencia_pf_livre_total": "credito_estoque_inadimplencia_pf_livre_to",
        # Taxa média de crédito imobiliário PF
        "taxa_credito_pf_sfh_total": "credito_contratacao_taxa_pf_sfh_to",
        "taxa_credito_pf_livre_total": "credito_contratacao_taxa_pf_livre_to",
        # Contratações PF (fluxo de crédito novo)
        "contratacao_pf_sfh_total": "credito_contratacao_contratado_pf_sfh_to",
        "contratacao_pf_livre_total": "credito_contratacao_contratado_pf_livre_to",
        # Imóveis por tipo (estoque garantido)
        "imoveis_tipo_apartamento_total": "imoveis_tipo_apartamento_to",
        "imoveis_tipo_casa_total": "imoveis_tipo_casa_to",
        "imoveis_valor_medio_total": "imoveis_valor_medio_to",
    }

    # ============================================================================
    # BCB — PTAX (Cotações de Câmbio)
    # ============================================================================

    # Moedas suportadas nativamente pelo BCB PTAX OData
    # (confirmado empiricamente — demais moedas retornam vazio; fallback é dos IngestNodes)
    BCB_PTAX_SUPPORTED_CURRENCIES: set[str] = {
        "AUD",
        "CAD",
        "CHF",
        "DKK",
        "EUR",
        "GBP",
        "JPY",
        "NOK",
        "SEK",
        "USD",
    }

    # Moedas de interesse — inclui as 10 do BCB + extras via Yahoo Finance
    BCB_PTAX_MAIN_CURRENCIES: list[str] = [
        "USD",
        "EUR",
        "GBP",
        "CHF",
        "JPY",
        "AUD",
        "CAD",
        "CNY",
        "ARS",
        "MXN",
        "DKK",
        "NOK",
        "SEK",
    ]

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
        # ---- Crédito e inadimplência ----
        "credito_pib": 20539,  # Crédito total ao setor privado / PIB — %
        "inadimplencia_pf": 21085,  # Taxa de inadimplência PF — %
        "inadimplencia_pj": 21082,  # Taxa de inadimplência PJ — %
        "inadimplencia_total": 21084,  # Taxa de inadimplência total — %
        "inadimplencia_pf_atraso_15_90": 27663,  # PF atraso 15-90 dias — %
        "inadimplencia_pf_atraso_acima_90": 27664,  # PF atraso >90 dias — %
        "inadimplencia_cartao": 22036,  # Inadimplência cartão de crédito — R$ milhões
        # ---- Agregados monetários ----
        "m1": 27789,  # Base monetária M1 — R$ milhões
        "m2": 27810,  # Base monetária M2 — R$ milhões
        "m4": 27815,  # Base monetária M4 — R$ milhões
        "base_monetaria": 1788,  # Base monetária — saldo fim de período — R$ milhões
        "compulsorios": 1849,  # Recolhimento compulsório total — R$ milhões
        # ---- Setor externo ----
        "balanca_comercial": 22707,  # Saldo balança comercial mensal — US$ milhões
        "reservas_internacionais": 3546,  # Reservas internacionais (liquidez) — US$ milhões
        "conta_corrente": 22701,  # Transações correntes — saldo mensal — US$ milhões
        "ied_liquido": 22704,  # Investimento direto no país — líquido — US$ milhões
        "divida_externa_total": 3547,  # Dívida externa total registrada — US$ milhões
        "fluxo_cambial": 22706,  # Fluxo cambial total — mensal — US$ milhões
        "termos_troca": 27574,  # Índice de termos de troca — export/import — índice
        # ---- Trabalho e renda (contradição capital-trabalho) ----
        "massa_salarial_real": 11777,  # Massa salarial real PNAD — R$ milhões
        "rendimento_medio_real": 24382,  # Rendimento médio real habitual PNAD — R$
        "taxa_desocupacao": 24369,  # Taxa de desocupação PNAD trimestral — %
        "salario_minimo": 1619,  # Salário mínimo vigente — R$
        "caged_saldo": 28763,  # CAGED — saldo de empregos formais — unidades
        "horas_trabalhadas": 28544,  # Horas habitualmente trabalhadas PNAD — horas/semana
        # ---- Expropriação financeira (contradição capital financeiro vs. PF) ----
        "spread_bancario_pf": 20786,  # Spread bancário médio PF total — p.p.
        "custo_credito_pf": 20749,  # Taxa média de juros PF total — % a.a.
        "endividamento_familias": 29037,  # Endividamento famílias/renda 12m — %
        "comprometimento_renda": 29038,  # Comprometimento renda famílias SFN — %
        "icc_fecomercio": 4393,  # Índice de Confiança do Consumidor — índice
        # ---- Preços relativos (contradição valor vs. preço) ----
        "ipca15": 7478,  # IPCA-15 (prévia) — variação mensal %
        "igpdi": 190,  # IGP-DI — variação mensal %
        "nucleo_ipca_ex0": 11427,  # Núcleo IPCA-EX0 (excl. alim+energia) — %
        "expectativa_ipca_12m": 13522,  # Expectativa IPCA 12m Focus mediana — %
        # ---- Concentração e dominância financeira ----
        "selic_real": 4390,  # Selic real ex-ante — % a.a.
        "utilizacao_capacidade": 24352,  # Utilização capacidade instalada FGV/CNI — %
    }

    # ============================================================================
    # IBGE — TABELAS DO SIDRA
    # ============================================================================

    IBGE_TABLE_IDS: dict[str, int] = {
        # ---- Inflação ----
        "ipca": 1737,  # IPCA — variação mensal (série histórica, todas as épocas)
        "ipca_nova": 7060,  # IPCA — série 2020+ por grupos/subitens (c315)
        "ipca_subitens": 1419,  # IPCA — por subitens (jan/2012 a dez/2019)
        "ipca15": 7062,  # IPCA-15 (prévia) — variação mensal (a partir fev/2020)
        # ---- PIB ----
        "pib_trimestral": 5932,  # PIB trimestral — taxa variação % (vs mesmo tri ano ant.)
        "pib_dessazonalizado": 1621,  # PIB série encadeada com ajuste sazonal (base 1995=100)
        "pib_nominal": 5938,  # PIB municipal preços correntes — R$ milhares (anual)
        # ---- Emprego e renda ----
        "pnad_desocupacao": 6381,  # PNAD — taxa de desocupação % (tri. móvel)
        "pnad_rendimento": 6387,  # PNAD — rendimento médio real efetivo (tri. móvel)
        "pnad_subutilizacao": 4093,  # PNAD — mercado de trabalho completo (trimestral)
        "pnad_populacao": 6022,  # PNAD — população total (tri. móvel, mil pessoas)
        "pnad_gini": 7453,  # PNAD — Índice de Gini rendimento habitual (anual)
        # ---- Atividade econômica setorial ----
        "pim_pf": 8888,  # PIM-PF — produção industrial mensal (base 2022=100)
        "pmc": 8881,  # PMC — comércio varejista ampliado mensal (base 2022=100)
        "pms": 8688,  # PMS — serviços mensal (base 2022=100, substitui 8162)
        # ---- Construção ----
        "sinapi": 2296,  # SINAPI — custo construção civil (R$/m² + variação %)
        # ---- Educação ----
        "analfabetismo": 7113,  # PNAD — taxa de analfabetismo 15+ (anual)
    }

    # ============================================================================
    # IBGE — INDICADORES DE PAÍSES (API servicodados)
    # ============================================================================

    # IDs de indicadores disponíveis em /api/v1/paises/{code}/indicadores/{ids}
    # Dados anuais (séries ~1990-2023), valores como strings em US$
    IBGE_COUNTRY_INDICATORS: dict[str, int] = {
        "pib": 77827,  # Total do PIB — US$
        "pib_per_capita": 77823,  # PIB per capita — US$
        "idh": 77831,  # Índice de Desenvolvimento Humano
        "exportacoes": 77825,  # Total de exportações — US$
        "importacoes": 77826,  # Total de importações — US$
        "esperanca_vida": 77830,  # Esperança de vida ao nascer — anos
        "gastos_educacao": 77819,  # Gastos públicos com educação — % do PIB
        "gastos_saude": 77820,  # Gastos públicos com saúde — % do PIB
        "pesquisa_desenvolvimento": 77821,  # Investimentos em P&D — % do PIB
        "populacao_total": 77852,  # População total
        "turistas": 77818,  # Chegada de turistas
    }

    # ============================================================================
    # FRED — SÉRIES ECONÔMICAS DOS EUA
    # ============================================================================

    FRED_SERIES: dict[str, dict[str, str]] = {
        # ---- Juros e política monetária ----
        # Taxa básica de juros dos EUA — referência global para custo de capital
        "DFF": {"nome": "Fed Funds Rate", "unidade": "%", "frequencia": "daily"},
        # Taxa efetiva (agregada) — redundante com DFF, mas útil para validação
        "FEDFUNDS": {
            "nome": "Effective Fed Funds Rate",
            "unidade": "%",
            "frequencia": "daily",
        },
        # Taxa prime — base para crédito corporativo nos EUA
        "DPRIME": {"nome": "Prime Rate", "unidade": "%", "frequencia": "daily"},
        # ---- Curva de Treasuries ----
        # Yields dos títulos do Tesouro americano por vencimento
        "DGS3MO": {"nome": "Treasury 3M", "unidade": "%", "frequencia": "daily"},
        "DGS1": {"nome": "Treasury 1Y", "unidade": "%", "frequencia": "daily"},
        "DGS2": {"nome": "Treasury 2Y", "unidade": "%", "frequencia": "daily"},
        "DGS5": {"nome": "Treasury 5Y", "unidade": "%", "frequencia": "daily"},
        "DGS7": {"nome": "Treasury 7Y", "unidade": "%", "frequencia": "daily"},
        "DGS10": {"nome": "Treasury 10Y", "unidade": "%", "frequencia": "daily"},
        "DGS20": {"nome": "Treasury 20Y", "unidade": "%", "frequencia": "daily"},
        "DGS30": {"nome": "Treasury 30Y", "unidade": "%", "frequencia": "daily"},
        # Spread 10Y-2Y — sinal clássico de recessão quando negativo
        "T10Y2Y": {"nome": "Spread 10Y-2Y", "unidade": "%", "frequencia": "daily"},
        # TIPS 10Y — juros real dos EUA, referência para retorno real global
        "DFII10": {
            "nome": "TIPS 10Y Real Yield",
            "unidade": "%",
            "frequencia": "daily",
        },
        # Breakeven inflação 10Y — expectativa de inflação implícita no mercado
        "T10YIE": {
            "nome": "Breakeven Inflação 10Y",
            "unidade": "%",
            "frequencia": "daily",
        },
        # TED Spread — risco interbancário (Libor-Treasury)
        "TEDRATE": {"nome": "TED Spread", "unidade": "%", "frequencia": "daily"},
        # Hipoteca 30 anos — proxy do mercado imobiliário americano
        "MORTGAGE30US": {
            "nome": "Hipoteca 30 Anos EUA",
            "unidade": "%",
            "frequencia": "weekly",
        },
        # ---- Inflação ----
        # CPI — índice de preços ao consumidor dos EUA (base análise inflação)
        "CPIAUCSL": {
            "nome": "CPI EUA",
            "unidade": "index",
            "frequencia": "monthly",
        },
        # Core PCE — inflação preferida pelo Fed (exclui alimentos e energia)
        "PCEPILFE": {
            "nome": "Core PCE",
            "unidade": "%",
            "frequencia": "monthly",
        },
        # ---- Atividade econômica ----
        # PIB real EUA — crescimento econômico ajustado pela inflação
        "GDPC1": {
            "nome": "PIB EUA Real",
            "unidade": "USD bi",
            "frequencia": "quarterly",
        },
        # PIB nominal EUA — valor corrente da produção
        "GDP": {
            "nome": "PIB EUA Nominal",
            "unidade": "USD bi",
            "frequencia": "quarterly",
        },
        # Desemprego — saúde do mercado de trabalho
        "UNRATE": {
            "nome": "Desemprego EUA",
            "unidade": "%",
            "frequencia": "monthly",
        },
        # Nonfarm Payrolls — criação líquida de empregos (exceto agrícola)
        "PAYEMS": {
            "nome": "Nonfarm Payrolls",
            "unidade": "milhares",
            "frequencia": "monthly",
        },
        # Produção industrial — proxy de atividade manufatureira
        "INDPRO": {
            "nome": "Produção Industrial EUA",
            "unidade": "index",
            "frequencia": "monthly",
        },
        # Sentimento do consumidor Michigan — confiança do consumidor
        "UMCSENT": {
            "nome": "Sentimento Consumidor Michigan",
            "unidade": "index",
            "frequencia": "monthly",
        },
        # Alvarás de construção — indicador antecedente do setor imobiliário
        "PERMIT": {
            "nome": "Alvarás de Construção",
            "unidade": "milhares",
            "frequencia": "monthly",
        },
        # ---- Mercados e risco ----
        # VIX — índice de volatilidade implícita do S&P 500 ("índice do medo")
        "VIXCLS": {"nome": "VIX", "unidade": "index", "frequencia": "daily"},
        # High Yield Spread — apetite a risco (crédito high yield vs Treasury)
        "BAMLH0A0HYM2": {
            "nome": "High Yield Spread",
            "unidade": "bps",
            "frequencia": "daily",
        },
        # ---- Câmbio ----
        # BRL/USD — câmbio crítico para carteira brasileira
        "DEXBZUS": {
            "nome": "BRL/USD",
            "unidade": "R$/USD",
            "frequencia": "daily",
        },
        # EUR/USD — par mais negociado do mundo
        "DEXUSEU": {
            "nome": "EUR/USD",
            "unidade": "EUR/USD",
            "frequencia": "daily",
        },
        # CNY/USD — câmbio China (segunda maior economia)
        "DEXCHUS": {
            "nome": "CNY/USD",
            "unidade": "CNY/USD",
            "frequencia": "daily",
        },
        # Índice do dólar ponderado por comércio — força global do dólar
        "DTWEXBGS": {
            "nome": "Índice do Dólar",
            "unidade": "index",
            "frequencia": "daily",
        },
        # ---- Commodities ----
        # WTI — preço do petróleo (referência global, impacta Petrobras e inflação)
        "DCOILWTICO": {
            "nome": "Petróleo WTI",
            "unidade": "USD/barril",
            "frequencia": "daily",
        },
        # Ouro — ativo de refúgio, hedge contra inflação e risco sistêmico
        "GOLDAMGBD228NLBM": {
            "nome": "Ouro London Fix",
            "unidade": "USD/oz",
            "frequencia": "daily",
        },
        # ---- Monetário e fiscal ----
        # M2 — oferta monetária ampla (liquidez na economia)
        "M2SL": {
            "nome": "M2 Oferta Monetária",
            "unidade": "USD bi",
            "frequencia": "monthly",
        },
        # Balanço do Fed — total de ativos (proxy de QE/QT)
        "WALCL": {
            "nome": "Ativos Totais do Fed",
            "unidade": "USD mi",
            "frequencia": "weekly",
        },
        # Dívida federal — sustentabilidade fiscal dos EUA
        "GFDEBTN": {
            "nome": "Dívida Federal EUA",
            "unidade": "USD mi",
            "frequencia": "quarterly",
        },
        # Balança comercial — saldo de exportações menos importações
        "BOPGSTB": {
            "nome": "Balança Comercial EUA",
            "unidade": "USD mi",
            "frequencia": "monthly",
        },
        # ---- Imobiliário ----
        # Case-Shiller — índice de preços de imóveis nas 20 maiores cidades
        "CSUSHPISA": {
            "nome": "Case-Shiller Preços Imóveis",
            "unidade": "index",
            "frequencia": "monthly",
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
