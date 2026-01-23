from carteira_auto import constants, logger, settings

if __name__ == "__main__":
    logger.info("Executando carteira_auto como script principal.")
    # Aqui você pode adicionar código para executar quando o módulo for chamado diretamente.
    # Por exemplo, iniciar uma interface de linha de comando (CLI) ou executar uma tarefa específica.
    print(settings.paths.ROOT_DIR)
    print(settings.logging.LOG_LEVEL)
    print(settings.portfolio.TARGET_ALLOCATIONS)
    print(settings.fetcher.YAHOO_TIMEOUT)
    print(constants.MARKET_SESSIONS)
