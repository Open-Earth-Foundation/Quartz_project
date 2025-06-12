import asyncio
import logging
from typing import Optional, Callable, TypeVar, Tuple, Type, Any
from functools import wraps
import random
# import time # Not strictly used in the function itself, but often related. Can be omitted if not needed.

# Assuming config and AgentState are accessible from this new location
# If they are in the parent 'agents' directory:
import config
from agent_state import AgentState # If AgentState is in the root of 'agents' or adjusted path

# Import httpx exceptions if available, otherwise use a generic exception for HTTP_EXCEPTIONS
try:
    import httpx
    HTTP_EXCEPTIONS_TUPLE = (httpx.HTTPStatusError, httpx.RequestError)
except ImportError:
    HTTP_EXCEPTIONS_TUPLE = (Exception,) # Fallback to generic Exception if httpx is not installed

logger = logging.getLogger(__name__)

# Constants for the retry decorator (can be overridden by decorator arguments)
DEFAULT_MAX_API_RETRIES = getattr(config, 'DEFAULT_MAX_API_RETRIES', 3)
DEFAULT_INITIAL_BACKOFF_SECONDS = getattr(config, 'DEFAULT_INITIAL_BACKOFF_SECONDS', 5)
DEFAULT_MAX_BACKOFF_SECONDS = getattr(config, 'DEFAULT_MAX_BACKOFF_SECONDS', 60)
MAX_CONCURRENT_API_CALLS = getattr(config, 'MAX_CONCURRENT_API_CALLS', 3) # Default to 3

# Global semaphore for limiting concurrency of decorated functions
API_CALL_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_API_CALLS)

T = TypeVar('T')

def retry_with_backoff(
    max_retries: int = DEFAULT_MAX_API_RETRIES,
    initial_backoff: float = DEFAULT_INITIAL_BACKOFF_SECONDS,
    max_backoff: float = DEFAULT_MAX_BACKOFF_SECONDS,
    jitter_factor: float = 0.1,
    catch_exceptions: Tuple[Type[BaseException], ...] = HTTP_EXCEPTIONS_TUPLE
):
    """
    Decorator to retry an async function with exponential backoff and jitter.
    It also uses the global API_CALL_SEMAPHORE to limit concurrency.
    Optionally updates AgentState for 429 errors if 'state' is passed as a kwarg to the decorated function.
    """
    def decorator(func: Callable[..., asyncio.Future[T]]) -> Callable[..., asyncio.Future[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            state: Optional[AgentState] = kwargs.get('state')
            current_retries = 0
            current_backoff = initial_backoff

            while current_retries <= max_retries:
                try:
                    async with API_CALL_SEMAPHORE:
                        pre_call_jitter = random.uniform(0, getattr(config, 'PRE_CALL_JITTER_MAX_SECONDS', 0.5))
                        await asyncio.sleep(pre_call_jitter)
                        logger.debug(f"Semaphore acquired for {func.__name__}. Jittered by {pre_call_jitter:.2f}s. Retries left: {max_retries - current_retries}")
                        return await func(*args, **kwargs)
                except catch_exceptions as e:
                    status_code = None
                    if isinstance(e, httpx.HTTPStatusError):
                        status_code = e.response.status_code
                        if status_code == 429 and state:
                            service_name = "unknown_service"
                            func_name_lower = func.__name__.lower()
                            if "firecrawl" in func_name_lower: service_name = "firecrawl"
                            elif "google" in func_name_lower: service_name = "google"
                            elif "openrouter" in func_name_lower or "llm" in func_name_lower: service_name = "openrouter"
                            
                            counter_name = f"{service_name}_429_events"
                            current_429_count = getattr(state, counter_name, 0)
                            setattr(state, counter_name, current_429_count + 1)
                            logger.info(f"Incremented {counter_name} in AgentState to {current_429_count + 1}.")
                                
                    logger.warning(
                        f"Call to {func.__name__} failed (Attempt {current_retries + 1}/{max_retries + 1}) "
                        f"with status {status_code if status_code else 'N/A'}: {e}"
                    )
                    
                    current_retries += 1
                    if current_retries > max_retries:
                        logger.error(f"Max retries reached for {func.__name__}. Giving up.")
                        if state and hasattr(state, 'api_calls_failed'):
                            state.api_calls_failed = getattr(state, 'api_calls_failed', 0) + 1
                        raise

                    sleep_time = current_backoff + random.uniform(-jitter_factor * current_backoff, jitter_factor * current_backoff)
                    sleep_time = min(sleep_time, max_backoff)
                    
                    logger.info(f"Retrying {func.__name__} in {sleep_time:.2f} seconds...")
                    await asyncio.sleep(sleep_time)
                    current_backoff = min(current_backoff * 2, max_backoff)
                except Exception as e:
                    logger.error(f"Unexpected error during {func.__name__} attempt {current_retries + 1}: {e}", exc_info=True)
                    if state and hasattr(state, 'api_calls_failed'):
                        state.api_calls_failed = getattr(state, 'api_calls_failed', 0) + 1
                    raise
        return wrapper
    return decorator
