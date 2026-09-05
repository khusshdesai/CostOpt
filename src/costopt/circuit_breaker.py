import time
import threading
import logging
from typing import Dict, List, Optional

logger = logging.getLogger("costopt.circuit_breaker")

class CostOptCircuitBreakerError(Exception):
    """Raised when CostOpt trips a circuit breaker to prevent silent loop billing leaks."""
    pass

class CircuitBreaker:
    def __init__(self, max_calls: int = 15, time_window_seconds: float = 30.0):
        self.max_calls = max_calls
        self.time_window_seconds = time_window_seconds
        # Maps location key (e.g. "main.py:42") -> list of monotonic timestamps
        self._history: Dict[str, List[float]] = {}
        self._lock = threading.Lock()
        self._call_count = 0  # BUG-8: used for periodic stale-key eviction

    def check_and_record(self, location_key: str) -> None:
        """Checks if calls from location_key exceed rate threshold within time window.
        Trips and raises CostOptCircuitBreakerError if limit exceeded."""
        if not location_key:
            return

        now = time.monotonic()

        with self._lock:
            timestamps = self._history.get(location_key, [])
            cutoff = now - self.time_window_seconds
            recent_timestamps = [t for t in timestamps if t >= cutoff]
            recent_timestamps.append(now)
            self._history[location_key] = recent_timestamps

            # BUG-8 fix: periodic eviction of stale keys to prevent unbounded dict growth
            self._call_count += 1
            if self._call_count % 100 == 0:
                stale = [k for k, v in self._history.items()
                         if not any(t >= cutoff for t in v)]
                for k in stale:
                    del self._history[k]

            if len(recent_timestamps) > self.max_calls:
                msg = (
                    f"CostOpt Circuit Breaker TRIPPED for [{location_key}]: "
                    f"Exceeded {self.max_calls} calls in {self.time_window_seconds}s window ({len(recent_timestamps)} calls recorded). "
                    f"Intercepted to prevent runaway LLM billing leak."
                )
                logger.error(msg)
                raise CostOptCircuitBreakerError(msg)

    def reset(self, location_key: Optional[str] = None) -> None:
        """Resets recorded call timestamps."""
        with self._lock:
            if location_key:
                self._history.pop(location_key, None)
            else:
                self._history.clear()
