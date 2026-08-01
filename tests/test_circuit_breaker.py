import time
from web_search_mcp.circuit_breaker import CircuitBreaker, CircuitState


def test_circuit_breaker_transitions():
    cb = CircuitBreaker(name="test", failure_threshold=2, cooldown_seconds=0.1)
    assert cb.allow_execution() is True
    assert cb.state == CircuitState.CLOSED

    # Record 1 failure -> still closed
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    assert cb.allow_execution() is True

    # Record 2nd failure -> trips open
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.allow_execution() is False

    # Wait for cooldown
    time.sleep(0.15)
    assert cb.allow_execution() is True
    assert cb.state == CircuitState.HALF_OPEN

    # Record success -> resets to closed
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.allow_execution() is True
