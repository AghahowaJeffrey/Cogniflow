import time
import structlog
from redis import Redis
from app.core.config import settings

logger = structlog.get_logger()

class CircuitBreakerOpenError(Exception):
    """Raised when the circuit is open and requests are blocked."""
    pass

class CircuitBreaker:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.redis = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)
        self.failure_key = f"circuit_breaker:failures:{service_name}"
        self.state_key = f"circuit_breaker:state:{service_name}"
        self.threshold = settings.CIRCUIT_BREAKER_THRESHOLD
        self.window = settings.CIRCUIT_BREAKER_WINDOW

    def is_open(self) -> bool:
        """Check if the circuit is currently open."""
        state = self.redis.get(self.state_key)
        return state == "open"

    def record_failure(self):
        """Increment failure count and open circuit if threshold exceeded."""
        failures = self.redis.incr(self.failure_key)
        if failures == 1:
            self.redis.expire(self.failure_key, self.window)
        
        if failures >= self.threshold:
            logger.warning("Circuit breaker opening", service=self.service_name, failures=failures)
            self.redis.set(self.state_key, "open", ex=self.window)

    def record_success(self):
        """Reset failures on success (close circuit)."""
        self.redis.delete(self.failure_key)
        self.redis.delete(self.state_key)

circuit_breaker = CircuitBreaker("llm_provider")
