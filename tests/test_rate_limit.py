from backend.app.rate_limit import FixedWindowRateLimiter


def test_rate_limiter_rejects_requests_above_limit() -> None:
    limiter = FixedWindowRateLimiter(max_requests=2, window_seconds=60)

    assert limiter.check("client")[0] is True
    assert limiter.check("client")[0] is True
    allowed, retry_after = limiter.check("client")

    assert allowed is False
    assert retry_after >= 1
