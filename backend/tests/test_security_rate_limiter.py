from datetime import datetime, timezone


def test_memory_rate_limiter_is_scoped_by_user():
    from security.rate_limiter import FixedWindowRateLimiter, InMemorySecurityStore, RateLimitPolicy

    now = lambda: datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)
    limiter = FixedWindowRateLimiter(
        store=InMemorySecurityStore(now=now),
        now=now,
    )
    policy = RateLimitPolicy(name="lookup_minute", limit=2, window_seconds=60)

    assert limiter.check("user:user_a:lookup", policy).allowed is True
    assert limiter.check("user:user_a:lookup", policy).allowed is True
    denied = limiter.check("user:user_a:lookup", policy)
    assert denied.allowed is False
    assert denied.retry_after_seconds == 60

    assert limiter.check("user:user_b:lookup", policy).allowed is True


def test_memory_security_store_lock_blocks_duplicate_until_released():
    from security.rate_limiter import InMemorySecurityStore

    store = InMemorySecurityStore(now=lambda: datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc))

    assert store.acquire_lock("user:user_a:agent_trigger", ttl_seconds=300) is True
    assert store.acquire_lock("user:user_a:agent_trigger", ttl_seconds=300) is False
    assert store.acquire_lock("user:user_b:agent_trigger", ttl_seconds=300) is True

    store.release_lock("user:user_a:agent_trigger")

    assert store.acquire_lock("user:user_a:agent_trigger", ttl_seconds=300) is True


def test_rate_limit_response_has_stable_shape():
    from security.rate_limiter import rate_limit_exceeded

    response = rate_limit_exceeded(retry_after_seconds=17)

    assert response.status_code == 429
    assert response.body == b'{"detail":"Rate limit exceeded","retry_after_seconds":17}'
