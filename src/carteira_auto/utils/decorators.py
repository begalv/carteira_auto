import functools
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Callable

# ============================================================================
# PERFORMANCE
# ============================================================================


def timer(func: Callable) -> Callable:
    """Mede tempo de execução de função."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        from carteira_auto.utils.logger import get_logger

        _logger = get_logger(func.__module__)
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        _logger.info(f"{func.__name__} executou em {elapsed:.4f}s")
        return result

    return wrapper


# ============================================================================
# REQUISIÇÕES & FALLBACK
# ============================================================================


def retry(max_attempts: int = 3, delay: float = 1.0):
    """Tenta novamente em caso de falha (crítico para APIs)."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        time.sleep(delay * (2**attempt))  # Exponential backoff
            raise last_exception

        return wrapper

    return decorator


def rate_limit(calls_per_minute: int = 60):
    """Limita taxa de requisições (evita ban de API)."""
    import threading

    def decorator(func: Callable) -> Callable:
        last_called = [0.0]
        lock = threading.Lock()
        min_interval = 60.0 / calls_per_minute

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with lock:
                elapsed = time.time() - last_called[0]
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)
                last_called[0] = time.time()
            return func(*args, **kwargs)

        return wrapper

    return decorator


def timeout(seconds: int = 30):
    """Timeout para operações de rede."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import signal  # funciona só em posix (unix, linux e mac)

            def handler(signum, frame):
                raise TimeoutError(
                    f"Função {func.__name__} excedeu timeout de {seconds}s"
                )

            signal.signal(signal.SIGALRM, handler)
            signal.alarm(seconds)

            try:
                result = func(*args, **kwargs)
                signal.alarm(0)  # Cancela alarme
                return result
            except TimeoutError:
                raise
            finally:
                signal.alarm(0)

        return wrapper

    return decorator


def fallback(fallback_func: Callable):
    """Executa função alternativa em caso de falha."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception:
                return fallback_func(*args, **kwargs)

        return wrapper

    return decorator


# ============================================================================
# VALIDAÇÃO & SEGURANÇA
# ============================================================================


def validate_tickers(func: Callable) -> Callable:
    """Valida se o argumento de ticker é válido.

    Funciona tanto em funções livres quanto em métodos de instância —
    detecta e pula o argumento `self` automaticamente.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        from carteira_auto.utils.helpers import validate_ticker

        # Detecta se é método de instância (primeiro arg não é str/list)
        if args and not isinstance(args[0], (str, list)):
            ticker_input = (
                args[1]
                if len(args) > 1
                else kwargs.get("symbol") or kwargs.get("symbols")
            )
        else:
            ticker_input = (
                args[0] if args else kwargs.get("symbol") or kwargs.get("symbols")
            )

        if ticker_input is None:
            return func(*args, **kwargs)

        # Normaliza entrada para lista
        tickers = [ticker_input] if isinstance(ticker_input, str) else ticker_input

        # Valida cada ticker
        for ticker in tickers:
            if not isinstance(ticker, str):
                raise TypeError(f"Ticker deve ser string, recebido {type(ticker)}")
            is_valid, _ = validate_ticker(ticker)
            if not is_valid:
                raise ValueError(f"Ticker inválido: {ticker}")

        return func(*args, **kwargs)

    return wrapper


def validate_positive_value(func: Callable) -> Callable:
    """Valida que valores financeiros são positivos."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Verifica args
        for arg in args:
            if isinstance(arg, (int, float, Decimal)) and arg < 0:
                raise ValueError(f"Valor negativo não permitido: {arg}")

        # Verifica kwargs
        for key, value in kwargs.items():
            if isinstance(value, (int, float, Decimal)) and value < 0:
                raise ValueError(f"Valor negativo não permitido para {key}: {value}")

        return func(*args, **kwargs)

    return wrapper


def validate_allocation_sum(func: Callable) -> Callable:
    """Valida que soma das alocações é 100%."""

    @functools.wraps(func)
    def wrapper(allocation_dict: dict, *args, **kwargs):
        total = sum(allocation_dict.values())

        if not 0.99 <= total <= 1.01:  # Tolerância de 1%
            raise ValueError(f"Soma das alocações deve ser 100%. Atual: {total:.2%}")

        return func(allocation_dict, *args, **kwargs)

    return wrapper


# ============================================================================
# LOGGING & MONITORAMENTO
# ============================================================================


def log_execution(func: Callable) -> Callable:
    """Loga execução de função."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        from carteira_auto.utils.logger import get_logger

        logger = get_logger(func.__module__)
        logger.debug(f"Executando {func.__name__}")

        try:
            result = func(*args, **kwargs)
            logger.debug(f"{func.__name__} concluída com sucesso")
            return result
        except Exception as e:
            logger.error(f"Erro em {func.__name__}: {e}", exc_info=True)
            raise

    return wrapper


# ============================================================================
# CACHE
# ============================================================================


def cache_result(ttl_seconds: int = 300, max_size: int = 1000):
    def decorator(func):
        cache = {}
        cache_order = []  # Para LRU (Least Recently Used)

        def _cleanup():
            """Remove entradas expiradas e mantém tamanho máximo."""
            now = datetime.now()
            expired_keys = []

            for key, (cached_time, _) in cache.items():
                if now - cached_time > timedelta(seconds=ttl_seconds):
                    expired_keys.append(key)

            for key in expired_keys:
                cache.pop(key, None)
                if key in cache_order:
                    cache_order.remove(key)

            # Remove os mais antigos se exceder tamanho
            while len(cache) > max_size and cache_order:
                oldest = cache_order.pop(0)
                cache.pop(oldest, None)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import hashlib

            # Chave mais eficiente
            key_data = (args, tuple(sorted(kwargs.items())))
            cache_key = hashlib.md5(str(key_data).encode()).hexdigest()

            # Limpa periodicamente (a cada 10 chamadas)
            if len(cache) % 10 == 0:
                _cleanup()

            if cache_key in cache:
                cached_time, result = cache[cache_key]
                if datetime.now() - cached_time < timedelta(seconds=ttl_seconds):
                    # Atualiza LRU
                    if cache_key in cache_order:
                        cache_order.remove(cache_key)
                    cache_order.append(cache_key)
                    return result

            result = func(*args, **kwargs)
            cache[cache_key] = (datetime.now(), result)
            cache_order.append(cache_key)

            return result

        return wrapper

    return decorator


def cache_by_ticker(ttl_seconds: int = 300, max_size: int = 1000):
    """Cache específico para tickers com LRU e limpeza."""

    def decorator(func: Callable) -> Callable:
        cache = {}  # {ticker: (timestamp, result)}
        cache_order = []  # Para LRU (Least Recently Used)

        def _cleanup():
            """Remove entradas expiradas e mantém tamanho máximo."""
            now = datetime.now()
            expired_tickers = []

            # Remove expirados
            for ticker, (cached_time, _) in cache.items():
                if now - cached_time > timedelta(seconds=ttl_seconds):
                    expired_tickers.append(ticker)

            for ticker in expired_tickers:
                cache.pop(ticker, None)
                if ticker in cache_order:
                    cache_order.remove(ticker)

            # Remove os mais antigos se exceder tamanho (LRU)
            while len(cache) > max_size and cache_order:
                oldest_ticker = cache_order.pop(0)
                cache.pop(oldest_ticker, None)

        @functools.wraps(func)
        def wrapper(ticker: str, *args, **kwargs):
            # Limpa periodicamente (a cada 10 chamadas)
            if len(cache) % 10 == 0:
                _cleanup()

            # Verifica cache
            if ticker in cache:
                cached_time, result = cache[ticker]
                if datetime.now() - cached_time < timedelta(seconds=ttl_seconds):
                    # Atualiza LRU (move para o final)
                    cache_order.remove(ticker)
                    cache_order.append(ticker)
                    return result

            # Executa função
            result = func(ticker, *args, **kwargs)

            # Armazena no cache
            cache[ticker] = (datetime.now(), result)
            cache_order.append(ticker)

            return result

        return wrapper

    return decorator
