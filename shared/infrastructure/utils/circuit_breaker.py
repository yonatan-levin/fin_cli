"""
Circuit breaker module.

This module implements the circuit breaker pattern to prevent cascading failures
when external services are unavailable or experiencing issues.
"""
import logging
import time
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar, cast

from fundainsight.domain.exceptions.financial_exceptions import CircuitBreakerOpenError

logger = logging.getLogger(__name__)

# Type variables for function signatures
T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])


class CircuitState(Enum):
    """Enumeration of circuit breaker states."""
    CLOSED = 'CLOSED'  # Normal operation, requests pass through
    OPEN = 'OPEN'      # Failure threshold exceeded, requests fail fast
    HALF_OPEN = 'HALF_OPEN'  # Recovery period, limited requests allowed


class CircuitBreaker:
    """
    Circuit breaker implementation.
    
    The circuit breaker prevents cascading failures by failing fast when
    a service is experiencing issues. It has three states:
    
    - CLOSED: Normal operation, all requests are allowed
    - OPEN: Failure threshold exceeded, all requests fail fast without
      calling the protected function
    - HALF_OPEN: Recovery period, a limited number of requests are allowed
      to test if the service has recovered
      
    Attributes:
        name: Name of the circuit breaker for identification
        failure_threshold: Number of failures before opening the circuit
        recovery_timeout: Time in seconds before trying recovery
        timeout: Timeout for protected function calls in seconds
        failure_count: Current count of consecutive failures
        last_failure_time: Timestamp of the last failure
        state: Current state of the circuit breaker
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        timeout: Optional[float] = None,
    ):
        """
        Initialize the circuit breaker.
        
        Args:
            name: Name of the circuit breaker for identification
            failure_threshold: Number of failures before opening the circuit
            recovery_timeout: Time in seconds before trying recovery
            timeout: Timeout for protected function calls in seconds
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.timeout = timeout
        
        # State tracking
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = CircuitState.CLOSED
        
        logger.info(f"Circuit breaker '{name}' initialized with threshold={failure_threshold}, "
                   f"recovery_timeout={recovery_timeout}s, timeout={timeout}s")
    
    def __call__(self, func: F) -> F:
        """
        Decorator to protect a function with the circuit breaker.
        
        Args:
            func: The function to protect
            
        Returns:
            Decorated function
        """
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return self.call(func, *args, **kwargs)
        
        return cast(F, wrapper)
    
    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """
        Call the protected function, respecting the circuit breaker state.
        
        Args:
            func: The function to call
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            The result of the function call
            
        Raises:
            CircuitBreakerOpenError: When the circuit is open
            Exception: Any exception raised by the protected function
        """
        self._check_state()
        
        try:
            start_time = time.time()
            
            # Call the function, possibly with a timeout
            if self.timeout is not None:
                # Simple implementation - for production use signal/threading based timeouts
                result = func(*args, **kwargs)
                if time.time() - start_time > self.timeout:
                    raise TimeoutError(f"Function call timed out after {self.timeout}s")
            else:
                result = func(*args, **kwargs)
            
            # Success - reset failure count if in half-open state
            if self.state == CircuitState.HALF_OPEN:
                logger.info(f"Circuit breaker '{self.name}' reset to CLOSED state after successful call")
                self.failure_count = 0
                self.state = CircuitState.CLOSED
            
            return result
            
        except Exception as e:
            return self._handle_failure(e)
    
    def _check_state(self) -> None:
        """
        Check and possibly update the current state.
        
        Raises:
            CircuitBreakerOpenError: When the circuit is open
        """
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                logger.info(f"Circuit breaker '{self.name}' changed from OPEN to HALF-OPEN state")
                self.state = CircuitState.HALF_OPEN
            else:
                remaining = self.recovery_timeout - (time.time() - self.last_failure_time)
                logger.warning(f"Circuit breaker '{self.name}' is OPEN. Retry after {remaining:.2f}s")
                raise CircuitBreakerOpenError(
                    service=self.name,
                    open_until=time.ctime(self.last_failure_time + self.recovery_timeout)
                )
    
    def _handle_failure(self, exception: Exception) -> Any:
        """
        Handle a failure in the protected function.
        
        Args:
            exception: The exception that was raised
            
        Raises:
            Exception: The original exception is re-raised
        """
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if (self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold) or \
           self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker '{self.name}' changed to OPEN state after {self.failure_count} failures")
        
        # Log the exception
        logger.error(f"Circuit breaker '{self.name}' recorded failure: {str(exception)}")
        
        # Re-raise the original exception
        raise exception
    
    def reset(self) -> None:
        """Reset the circuit breaker to its initial state."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        logger.info(f"Circuit breaker '{self.name}' manually reset to CLOSED state")


# Global registry of circuit breakers
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    timeout: Optional[float] = None,
) -> CircuitBreaker:
    """
    Get or create a circuit breaker.
    
    Args:
        name: Name of the circuit breaker
        failure_threshold: Number of failures before opening the circuit
        recovery_timeout: Time in seconds before trying recovery
        timeout: Timeout for protected function calls in seconds
        
    Returns:
        CircuitBreaker instance
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            timeout=timeout,
        )
    return _circuit_breakers[name] 