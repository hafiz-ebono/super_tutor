"""
Retry utility for LLM agent calls.

Uses tenacity for exponential backoff on transient provider errors (429, 502, 503).
Auth errors (401) and bad-request errors (400) are NOT retried.

Usage:
    result = run_with_retry(agent.run, input_text)
    result = run_with_retry(agent.run, input_text, max_attempts=settings.agent_max_retries)
"""
import logging
from typing import Any, Callable

from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential

logger = logging.getLogger("super_tutor.retry")

# Keywords that indicate a retryable transient error
_RETRYABLE_KEYWORDS = [
    "429",
    "rate limit",
    "rate_limit",
    "temporarily",
    "503",
    "502",
    "provider returned error",
    "overloaded",
]

# Keywords that indicate a non-retryable error — checked first
_NON_RETRYABLE_KEYWORDS = ["401", "403", "400", "invalid api key", "bad request"]


def is_retryable(exc: BaseException) -> bool:
    """Return True if the exception represents a transient provider error worth retrying."""
    msg = str(exc).lower()
    if any(k in msg for k in _NON_RETRYABLE_KEYWORDS):
        return False
    return any(k in msg for k in _RETRYABLE_KEYWORDS)


def run_with_retry(
    fn: Callable[..., Any],
    *args: Any,
    max_attempts: int = 3,
    **kwargs: Any,
) -> Any:
    """
    Run a synchronous callable with tenacity retry + optional fallback model.

    Retries on transient errors (429, 502, 503) with exponential backoff
    (1s min, 8s max). Does NOT retry auth or bad-request errors.

    Falls back to get_fallback_model() after all retries are exhausted, if configured.
    The fallback attempt is made ONCE with no additional retry.

    Args:
        fn: Synchronous callable, typically agent.run
        *args: Positional arguments forwarded to fn
        max_attempts: Number of attempts (default 3, configurable via AGENT_MAX_RETRIES)
        **kwargs: Keyword arguments forwarded to fn

    Raises:
        The last exception if all retries (and optional fallback) are exhausted.
    """
    last_exc: BaseException | None = None

    for attempt in Retrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception(is_retryable),
        reraise=True,
    ):
        with attempt:
            attempt_number = attempt.retry_state.attempt_number
            if attempt_number > 1:
                logger.warning(
                    "Retry attempt %d/%d for %s",
                    attempt_number,
                    max_attempts,
                    getattr(fn, "__name__", repr(fn)),
                )
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                raise

    # All primary attempts exhausted — try fallback model once if available
    from app.agents.model_factory import get_fallback_model  # lazy import avoids circular
    fallback_model = get_fallback_model()
    if fallback_model is not None:
        logger.warning(
            "Primary model exhausted retries — trying fallback model once: %s",
            getattr(fallback_model, "id", repr(fallback_model)),
        )
        # fn is agent.run — the agent holds model reference; we need the parent agent
        # Fallback only works when fn is a bound method of an Agent instance with .model attr
        agent = getattr(fn, "__self__", None)
        if agent is not None and hasattr(agent, "model"):
            original_model = agent.model
            try:
                agent.model = fallback_model
                return fn(*args, **kwargs)
            except Exception as fallback_exc:
                logger.error("Fallback model also failed: %s", fallback_exc)
                raise fallback_exc
            finally:
                agent.model = original_model  # always restore

    raise last_exc if last_exc is not None else RuntimeError("run_with_retry: no result")
