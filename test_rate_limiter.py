import time
import pytest
from rate_limiter import TokenBucketRateLimiter


def test_token_bucket_initial_capacity():
    limiter = TokenBucketRateLimiter(capacity=10.0, refill_rate=2.0)
    assert limiter.get_available_tokens() == 10.0


def test_token_bucket_consumption():
    limiter = TokenBucketRateLimiter(capacity=5.0, refill_rate=1.0)
    assert limiter.allow(3.0) is True
    assert limiter.get_available_tokens() <= 2.1
    assert limiter.allow(3.0) is False  # Only ~2 tokens remain


def test_token_bucket_refill():
    limiter = TokenBucketRateLimiter(capacity=2.0, refill_rate=10.0)
    assert limiter.allow(2.0) is True
    assert limiter.allow(1.0) is False
    # Sleep 0.15s -> should refill 1.5 tokens
    time.sleep(0.15)
    assert limiter.allow(1.0) is True


def test_token_bucket_invalid_params():
    with pytest.raises(ValueError):
        TokenBucketRateLimiter(capacity=0, refill_rate=1.0)
    with pytest.raises(ValueError):
        TokenBucketRateLimiter(capacity=5.0, refill_rate=-1.0)
