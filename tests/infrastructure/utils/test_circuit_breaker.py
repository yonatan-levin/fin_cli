"""
Unit tests for circuit breaker module.
"""
import unittest
import time
from unittest.mock import patch, MagicMock

from shared.infrastructure.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    get_circuit_breaker,
    CircuitBreakerOpenError
)


class TestCircuitBreaker(unittest.TestCase):
    """Test cases for the CircuitBreaker class."""

    def setUp(self):
        """Set up circuit breaker for tests."""
        self.circuit_breaker = CircuitBreaker(
            name="test-circuit",
            failure_threshold=3,
            recovery_timeout=2,  # Short timeout for faster tests
            timeout=1
        )
    
    def test_initial_state(self):
        """Test initial state of circuit breaker."""
        self.assertEqual(self.circuit_breaker.state, CircuitState.CLOSED)
        self.assertEqual(self.circuit_breaker.failure_count, 0)
        self.assertEqual(self.circuit_breaker.name, "test-circuit")
        self.assertEqual(self.circuit_breaker.failure_threshold, 3)
        self.assertEqual(self.circuit_breaker.recovery_timeout, 2)
        self.assertEqual(self.circuit_breaker.timeout, 1)
    
    def test_successful_call(self):
        """Test a successful function call with circuit breaker."""
        # Test function that always succeeds
        def success_func(value):
            return value * 2
        
        # Call the function through the circuit breaker
        result = self.circuit_breaker.call(success_func, 5)
        
        # Verify result and state
        self.assertEqual(result, 10)
        self.assertEqual(self.circuit_breaker.state, CircuitState.CLOSED)
        self.assertEqual(self.circuit_breaker.failure_count, 0)
    
    def test_failing_call(self):
        """Test a failing function call with circuit breaker."""
        # Test function that always fails
        def failing_func():
            raise ValueError("Test error")
        
        # Call the function through the circuit breaker and expect failure
        with self.assertRaises(ValueError):
            self.circuit_breaker.call(failing_func)
        
        # Verify state after failure
        self.assertEqual(self.circuit_breaker.state, CircuitState.CLOSED)
        self.assertEqual(self.circuit_breaker.failure_count, 1)
    
    def test_circuit_opens_after_threshold(self):
        """Test circuit opens after reaching the failure threshold."""
        # Test function that always fails
        def failing_func():
            raise ValueError("Test error")
        
        # Call the function multiple times to reach threshold
        for _ in range(3):  # failure_threshold is 3
            with self.assertRaises(ValueError):
                self.circuit_breaker.call(failing_func)
        
        # Verify circuit is now open
        self.assertEqual(self.circuit_breaker.state, CircuitState.OPEN)
        self.assertEqual(self.circuit_breaker.failure_count, 3)
        
        # Next call should fail with CircuitBreakerOpenError
        with self.assertRaises(CircuitBreakerOpenError):
            self.circuit_breaker.call(failing_func)
    
    def test_half_open_state_after_timeout(self):
        """Test circuit transitions to half-open state after timeout."""
        # Test function that always fails
        def failing_func():
            raise ValueError("Test error")
        
        # Call the function multiple times to open the circuit
        for _ in range(3):
            with self.assertRaises(ValueError):
                self.circuit_breaker.call(failing_func)
        
        # Verify circuit is open
        self.assertEqual(self.circuit_breaker.state, CircuitState.OPEN)
        
        # Wait for recovery timeout
        time.sleep(2.1)  # slightly longer than recovery_timeout
        
        # Now circuit should be half-open
        self.circuit_breaker._check_state()  # This would normally be called by .call()
        self.assertEqual(self.circuit_breaker.state, CircuitState.HALF_OPEN)
    
    def test_circuit_closes_after_successful_recovery(self):
        """Test circuit closes after successful call in half-open state."""
        # Set up the circuit breaker in half-open state
        self.circuit_breaker.state = CircuitState.HALF_OPEN
        self.circuit_breaker.failure_count = 3
        
        # Test function that succeeds
        def success_func():
            return "success"
        
        # Call should succeed and reset the circuit
        result = self.circuit_breaker.call(success_func)
        
        # Verify result and state
        self.assertEqual(result, "success")
        self.assertEqual(self.circuit_breaker.state, CircuitState.CLOSED)
        self.assertEqual(self.circuit_breaker.failure_count, 0)
    
    def test_circuit_reopens_after_failure_in_half_open(self):
        """Test circuit reopens after failure in half-open state."""
        # Set up the circuit breaker in half-open state
        self.circuit_breaker.state = CircuitState.HALF_OPEN
        self.circuit_breaker.failure_count = 3
        
        # Test function that fails
        def failing_func():
            raise ValueError("Test error")
        
        # Call should fail and reopen the circuit
        with self.assertRaises(ValueError):
            self.circuit_breaker.call(failing_func)
        
        # Verify state
        self.assertEqual(self.circuit_breaker.state, CircuitState.OPEN)
        self.assertEqual(self.circuit_breaker.failure_count, 4)
    
    def test_timeout_handling(self):
        """Test function timeout handling."""
        # Test function that takes too long
        def slow_func():
            time.sleep(1.5)  # longer than timeout=1
            return "slow result"
        
        # Call should raise TimeoutError
        with self.assertRaises(TimeoutError):
            self.circuit_breaker.call(slow_func)
        
        # Verify state after timeout
        self.assertEqual(self.circuit_breaker.state, CircuitState.CLOSED)
        self.assertEqual(self.circuit_breaker.failure_count, 1)
    
    def test_decorator_usage(self):
        """Test using circuit breaker as a decorator."""
        # Define a function with the circuit breaker decorator
        @self.circuit_breaker
        def decorated_func(value):
            return value * 3
        
        # Call the decorated function
        result = decorated_func(4)
        
        # Verify result and state
        self.assertEqual(result, 12)
        self.assertEqual(self.circuit_breaker.state, CircuitState.CLOSED)
        self.assertEqual(self.circuit_breaker.failure_count, 0)
    
    def test_manual_reset(self):
        """Test manually resetting the circuit breaker."""
        # Set up the circuit breaker in an open state
        self.circuit_breaker.state = CircuitState.OPEN
        self.circuit_breaker.failure_count = 5
        
        # Reset the circuit breaker
        self.circuit_breaker.reset()
        
        # Verify state after reset
        self.assertEqual(self.circuit_breaker.state, CircuitState.CLOSED)
        self.assertEqual(self.circuit_breaker.failure_count, 0)


class TestCircuitBreakerRegistry(unittest.TestCase):
    """Test cases for the circuit breaker registry."""

    def setUp(self):
        """Set up registry tests."""
        # Clear the registry before each test
        from shared.infrastructure.utils.circuit_breaker import _circuit_breakers
        _circuit_breakers.clear()
    
    def test_get_circuit_breaker(self):
        """Test getting a circuit breaker from the registry."""
        # Get a circuit breaker
        cb1 = get_circuit_breaker(
            name="service1",
            failure_threshold=3,
            recovery_timeout=60,
            timeout=5
        )
        
        # Verify properties
        self.assertEqual(cb1.name, "service1")
        self.assertEqual(cb1.failure_threshold, 3)
        self.assertEqual(cb1.recovery_timeout, 60)
        self.assertEqual(cb1.timeout, 5)
        
        # Get the same circuit breaker again
        cb2 = get_circuit_breaker(name="service1")
        
        # Verify it's the same instance
        self.assertIs(cb1, cb2)
        
        # Get a different circuit breaker
        cb3 = get_circuit_breaker(name="service2")
        
        # Verify it's a different instance
        self.assertIsNot(cb1, cb3)
        self.assertEqual(cb3.name, "service2")
    
    def test_circuit_breaker_isolation(self):
        """Test that circuit breakers are isolated from each other."""
        # Get two circuit breakers
        cb1 = get_circuit_breaker(name="service1", failure_threshold=3)
        cb2 = get_circuit_breaker(name="service2", failure_threshold=3)
        
        # Define a function that fails
        def failing_func():
            raise ValueError("Test error")
        
        # Open the first circuit breaker
        for _ in range(3):
            with self.assertRaises(ValueError):
                cb1.call(failing_func)
        
        # Verify first circuit breaker is open
        self.assertEqual(cb1.state, CircuitState.OPEN)
        
        # But the second one should still be closed
        self.assertEqual(cb2.state, CircuitState.CLOSED)
        
        # And we can still call through the second circuit breaker
        with self.assertRaises(ValueError):
            cb2.call(failing_func)
            
        # First call to the second circuit breaker should increment its failure count
        self.assertEqual(cb2.failure_count, 1)


if __name__ == "__main__":
    unittest.main() 