import time
from enum import Enum

from web_search_mcp.observability import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_state_change = time.time()

    def allow_execution(self) -> bool:
        now = time.time()
        if self.state == CircuitState.OPEN:
            if now - self.last_state_change > self.cooldown_seconds:
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = now
                logger.info("Circuit breaker entering half-open state for provider %s", self.name)
                return True
            return False
        return True

    def record_success(self) -> None:
        if self.state != CircuitState.CLOSED:
            logger.info(
                "Circuit breaker closed after successful execution for provider %s", self.name
            )
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_state_change = time.time()

    def record_failure(self) -> None:
        self.failure_count += 1
        now = time.time()
        if self.failure_count >= self.failure_threshold or self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.last_state_change = now
            logger.warning(
                "Circuit breaker tripped open for provider %s (failures: %s)",
                self.name,
                self.failure_count,
            )
