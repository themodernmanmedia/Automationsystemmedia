"""Retry with exponential backoff for flaky I/O (APIs, renders)."""
from __future__ import annotations

import functools
import time
from typing import Callable, TypeVar

from .logging_setup import get_logger

T = TypeVar("T")
log = get_logger("retry")


class PermanentError(Exception):
    """Raise to abort retrying (bad credentials, invalid input...)."""


def retry(
    attempts: int = 3,
    backoff: float = 2.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    sleep: Callable[[float], None] = time.sleep,
):
    if attempts < 1:
        raise ValueError("attempts must be >= 1")

    def deco(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs) -> T:
            for i in range(1, attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except PermanentError:
                    raise
                except exceptions as exc:
                    if i == attempts:
                        log.error("%s failed after %d attempts: %s", fn.__name__, attempts, exc)
                        raise
                    delay = backoff * (2 ** (i - 1))
                    log.warning("%s attempt %d/%d failed (%s); retrying in %.1fs",
                                fn.__name__, i, attempts, exc, delay)
                    sleep(delay)
            raise AssertionError("unreachable")

        return wrapper

    return deco
