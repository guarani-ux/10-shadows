import time
import threading
from typing import Optional


class TokenBucketRateLimiter:
    """
    Thread-safe Token Bucket Rate Limiter.
    Operates using monotonic timestamps and atomic token consumption.
    """

    def __init__(self, capacity: float, refill_rate: float):
        if capacity <= 0:
            raise ValueError("Capacity must be strictly positive.")
        if refill_rate <= 0:
            raise ValueError("Refill rate must be strictly positive.")

        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self.tokens = float(capacity)
        self.last_refill_time = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        """Refill tokens based on elapsed monotonic time."""
        now = time.monotonic()
        elapsed = now - self.last_refill_time
        if elapsed > 0:
            added_tokens = elapsed * self.refill_rate
            self.tokens = min(self.capacity, self.tokens + added_tokens)
            self.last_refill_time = now

    def allow(self, tokens: float = 1.0) -> bool:
        """
        Attempts to consume tokens from the bucket.
        Returns True if tokens were consumed, False if rate limited.
        """
        if tokens <= 0:
            return True

        with self._lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def get_available_tokens(self) -> float:
        """Returns the current number of available tokens in the bucket."""
        with self._lock:
            self._refill()
            return self.tokens
