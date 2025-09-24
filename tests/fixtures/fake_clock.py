"""
Fake clock for deterministic time testing.

Allows tests to control time progression and ensure reproducible results
when testing time-dependent behavior.
"""

import datetime as dt
from typing import Optional


class FakeClock:
    """
    Controllable clock for testing time-dependent functionality.

    Provides deterministic time that can be advanced manually in tests,
    eliminating flaky time-based test failures.
    """

    def __init__(self, start: Optional[dt.datetime] = None):
        """
        Initialize fake clock.

        Args:
            start: Starting datetime (defaults to 2025-01-01 00:00:00 UTC)
        """
        self._now = start or dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)

    def now(self) -> dt.datetime:
        """Get current fake time."""
        return self._now

    def utcnow(self) -> dt.datetime:
        """Get current fake time in UTC (alias for now())."""
        return self._now

    def isoformat(self) -> str:
        """Get current time as ISO format string."""
        return self._now.isoformat()

    def timestamp(self) -> float:
        """Get current time as Unix timestamp."""
        return self._now.timestamp()

    def advance(self, seconds: float = 1.0):
        """
        Advance the clock by specified seconds.

        Args:
            seconds: Number of seconds to advance
        """
        self._now += dt.timedelta(seconds=seconds)

    def advance_minutes(self, minutes: float):
        """Advance clock by minutes."""
        self.advance(minutes * 60)

    def advance_hours(self, hours: float):
        """Advance clock by hours."""
        self.advance(hours * 3600)

    def advance_days(self, days: float):
        """Advance clock by days."""
        self.advance(days * 86400)

    def set_time(self, new_time: dt.datetime):
        """
        Set the clock to a specific time.

        Args:
            new_time: New datetime to set
        """
        self._now = new_time

    def reset(self, start: Optional[dt.datetime] = None):
        """
        Reset clock to initial time.

        Args:
            start: New starting time (uses original if None)
        """
        self._now = start or dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)

    def __str__(self) -> str:
        return f"FakeClock({self._now.isoformat()})"

    def __repr__(self) -> str:
        return self.__str__()


# Convenience functions for common test scenarios

def create_test_clock(year: int = 2025, month: int = 1, day: int = 1,
                      hour: int = 0, minute: int = 0, second: int = 0) -> FakeClock:
    """Create a fake clock starting at the specified time."""
    start_time = dt.datetime(year, month, day, hour, minute, second, tzinfo=dt.timezone.utc)
    return FakeClock(start_time)


def market_open_clock() -> FakeClock:
    """Create a fake clock set to market open (9:30 AM EST on a weekday)."""
    # January 3, 2025 is a Friday - market open
    market_open = dt.datetime(2025, 1, 3, 14, 30, tzinfo=dt.timezone.utc)  # 9:30 AM EST = 14:30 UTC
    return FakeClock(market_open)


def weekend_clock() -> FakeClock:
    """Create a fake clock set to weekend (markets closed)."""
    # January 4, 2025 is a Saturday
    weekend = dt.datetime(2025, 1, 4, 12, 0, tzinfo=dt.timezone.utc)
    return FakeClock(weekend)


class ClockContext:
    """
    Context manager for temporarily using a fake clock.

    Example:
        with ClockContext(fake_clock) as clock:
            # Time is controlled by fake_clock
            clock.advance_hours(1)
            # ... test time-dependent behavior
    """

    def __init__(self, clock: FakeClock):
        self.clock = clock
        self._original_now = None

    def __enter__(self) -> FakeClock:
        # Could monkey-patch datetime.now here if needed
        return self.clock

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original time functions if patched
        pass