import time

import pytest

from loop_engine.governor import RetryGovernor, TokenBucketRateLimiter


class TestRetryGovernorConstruction:
    def test_valid_construction_defaults(self):
        gov = RetryGovernor(max_attempts=3)
        assert gov.max_attempts == 3
        assert gov.attempts_used == 0
        assert gov.remaining_attempts() == 3
        assert gov.can_retry() is True

    def test_valid_construction_with_initial_attempts(self):
        gov = RetryGovernor(max_attempts=5, attempts_used=2)
        assert gov.max_attempts == 5
        assert gov.attempts_used == 2
        assert gov.remaining_attempts() == 3
        assert gov.can_retry() is True

    def test_valid_construction_at_boundary(self):
        gov = RetryGovernor(max_attempts=4, attempts_used=4)
        assert gov.max_attempts == 4
        assert gov.attempts_used == 4
        assert gov.remaining_attempts() == 0
        assert gov.can_retry() is False

    def test_invalid_max_attempts_zero(self):
        with pytest.raises(ValueError, match="strictly positive"):
            RetryGovernor(max_attempts=0)

    def test_invalid_max_attempts_negative(self):
        with pytest.raises(ValueError, match="strictly positive"):
            RetryGovernor(max_attempts=-5)

    def test_invalid_attempts_used_negative(self):
        with pytest.raises(ValueError, match="non-negative"):
            RetryGovernor(max_attempts=3, attempts_used=-1)

    def test_invalid_attempts_used_exceeding_max(self):
        with pytest.raises(ValueError, match="cannot exceed max_attempts"):
            RetryGovernor(max_attempts=3, attempts_used=4)

    @pytest.mark.parametrize("invalid_val", [None, "3", 3.5, [3], {"a": 1}, True, False])
    def test_type_error_on_invalid_max_attempts_type(self, invalid_val):
        with pytest.raises(TypeError, match="integer"):
            RetryGovernor(max_attempts=invalid_val)

    @pytest.mark.parametrize("invalid_val", [None, "0", 1.5, [1], {"b": 2}, True, False])
    def test_type_error_on_invalid_attempts_used_type(self, invalid_val):
        with pytest.raises(TypeError, match="integer"):
            RetryGovernor(max_attempts=5, attempts_used=invalid_val)


class TestRetryGovernorStateTransitions:
    def test_sequential_record_failure(self):
        gov = RetryGovernor(max_attempts=3)
        assert gov.can_retry() is True
        assert gov.remaining_attempts() == 3
        assert gov.attempts_used == 0

        # Failure 1
        gov.record_failure()
        assert gov.attempts_used == 1
        assert gov.remaining_attempts() == 2
        assert gov.can_retry() is True

        # Failure 2
        gov.record_failure()
        assert gov.attempts_used == 2
        assert gov.remaining_attempts() == 1
        assert gov.can_retry() is True

        # Failure 3 - Reached limit
        gov.record_failure()
        assert gov.attempts_used == 3
        assert gov.remaining_attempts() == 0
        assert gov.can_retry() is False

    def test_record_failure_clamping_at_capacity(self):
        gov = RetryGovernor(max_attempts=2)
        gov.record_failure()
        gov.record_failure()
        assert gov.attempts_used == 2
        assert gov.remaining_attempts() == 0
        assert gov.can_retry() is False

        # Attempting further failures beyond capacity must clamp
        for _ in range(10):
            gov.record_failure()
            assert gov.attempts_used == 2
            assert gov.remaining_attempts() == 0
            assert gov.can_retry() is False

    def test_remaining_attempts_never_negative(self):
        gov = RetryGovernor(max_attempts=1)
        gov.record_failure()
        gov.record_failure()
        gov.record_failure()
        assert gov.remaining_attempts() == 0
        assert gov.remaining_attempts() >= 0

    def test_reset(self):
        gov = RetryGovernor(max_attempts=3, attempts_used=3)
        assert gov.can_retry() is False
        assert gov.remaining_attempts() == 0

        gov.reset()
        assert gov.attempts_used == 0
        assert gov.remaining_attempts() == 3
        assert gov.can_retry() is True


class TestRetryGovernorCourtesyRetryRejection:
    def test_strict_rejection_of_courtesy_retry(self):
        """
        Contradiction Check: When attempts_used == max_attempts, can_retry()
        MUST return False. No extra 'courtesy' retry is permitted.
        """
        gov = RetryGovernor(max_attempts=1)
        assert gov.can_retry() is True
        gov.record_failure()
        # Limit exhausted
        assert gov.can_retry() is False
        assert gov.remaining_attempts() == 0

        # Verify repeated queries consistently reject
        assert gov.can_retry() is False
        assert gov.can_retry() is False

    def test_single_attempt_governor(self):
        gov = RetryGovernor(max_attempts=1)
        assert gov.can_retry() is True
        assert gov.remaining_attempts() == 1
        gov.record_failure()
        assert gov.can_retry() is False
        assert gov.remaining_attempts() == 0
        assert gov.attempts_used == 1


class TestRetryGovernorFailureInjectionAndMutants:
    def test_mutant_off_by_one_allowed(self):
        """
        Catch mutant where can_retry is implemented as `attempts_used <= max_attempts`.
        """
        gov = RetryGovernor(max_attempts=2, attempts_used=2)
        assert gov.can_retry() is False

    def test_mutant_negative_remaining(self):
        """
        Catch mutant where remaining_attempts does not clamp at 0.
        """
        gov = RetryGovernor(max_attempts=2)
        gov.record_failure()
        gov.record_failure()
        gov.record_failure()
        assert gov.remaining_attempts() == 0

    def test_mutant_unbounded_attempts_used(self):
        """
        Catch mutant where record_failure increments unbounded beyond max_attempts.
        """
        gov = RetryGovernor(max_attempts=2)
        for _ in range(5):
            gov.record_failure()
        assert gov.attempts_used == 2

    def test_repr_string(self):
        gov = RetryGovernor(max_attempts=3, attempts_used=1)
        assert repr(gov) == "RetryGovernor(max_attempts=3, attempts_used=1)"


class TestTokenBucketRateLimiter:
    def test_token_bucket_initial_capacity(self):
        limiter = TokenBucketRateLimiter(capacity=10.0, refill_rate=2.0)
        assert limiter.get_available_tokens() == 10.0

    def test_token_bucket_consumption(self):
        limiter = TokenBucketRateLimiter(capacity=5.0, refill_rate=1.0)
        assert limiter.allow(3.0) is True
        assert limiter.get_available_tokens() <= 2.1
        assert limiter.allow(3.0) is False

    def test_token_bucket_refill(self):
        limiter = TokenBucketRateLimiter(capacity=2.0, refill_rate=10.0)
        assert limiter.allow(2.0) is True
        assert limiter.allow(1.0) is False
        time.sleep(0.15)
        assert limiter.allow(1.0) is True

    def test_token_bucket_invalid_params(self):
        with pytest.raises(ValueError):
            TokenBucketRateLimiter(capacity=0, refill_rate=1.0)
        with pytest.raises(ValueError):
            TokenBucketRateLimiter(capacity=5.0, refill_rate=-1.0)
