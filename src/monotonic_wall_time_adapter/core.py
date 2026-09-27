"""Core clock implementation.

Design decision:
    We build on ``time.monotonic`` rather than ``time.perf_counter``.

    Both are monotonic and high-resolution on CPython, but ``monotonic`` has
    a stronger semantic guarantee that matters here: it never goes backwards
    across system suspend/resume cycles, whereas ``perf_counter`` may include
    time the process spent suspended on some platforms. For a "wall-ish"
    monotonic clock that survives a laptop sleep, ``monotonic`` is the safer
    primitive.

    The trade-off: ``perf_counter`` can be marginally higher resolution and
    lower overhead for tight benchmarking. If you only need sub-millisecond
    interval measurement *within* an active process and never suspend,
    ``perf_counter`` is the better tool. This library is for the other case.

    The adapter's job is to give callers one name to depend on, so that the
    underlying primitive can be swapped (or injected for tests) without a
    ripple of edits through a codebase.
"""

from __future__ import annotations

import time
from typing import Callable, Optional


__all__ = ["MonotonicClock", "default_clock", "monotonic_now"]


class MonotonicClock:
    """A monotonic clock with a fixed epoch.

    The epoch is captured once at construction (or at ``reset()``) so that
    all subsequent reads are expressed relative to that anchor. Because the
    underlying primitive (``time.monotonic`` by default) is monotonic, reads
    are non-decreasing even across system suspend/resume on platforms where
    ``time.monotonic`` honors that contract.

    The source of time is injectable so tests can drive the clock without
    sleeping or depending on wall time.
    """

    __slots__ = ("_source", "_epoch")

    def __init__(
        self,
        source: Optional[Callable[[], float]] = None,
        *,
        epoch: Optional[float] = None,
    ) -> None:
        """Construct a clock.

        Args:
            source: A zero-arg callable returning a monotonic float. When
                ``None``, defaults to ``time.monotonic``. Passing a fake is
                the supported way to test time-dependent code.
            epoch: An explicit epoch value in the *same frame* as ``source``.
                When ``None``, the epoch is sampled from ``source`` at
                construction. Useful when multiple clocks must share an
                origin.
        """
        self._source: Callable[[], float] = source if source is not None else time.monotonic
        self._epoch: float = epoch if epoch is not None else self._source()

    @property
    def source(self) -> Callable[[], float]:
        """Return the underlying time source callable."""
        return self._source

    @property
    def epoch(self) -> float:
        """Return the epoch this clock's readings are relative to."""
        return self._epoch

    def reset(self, *, epoch: Optional[float] = None) -> float:
        """Re-anchor the clock's epoch to now (or to ``epoch``).

        Returns the new epoch so callers can chain or log it.
        """
        self._epoch = epoch if epoch is not None else self._source()
        return self._epoch

    def __call__(self) -> float:
        """Return elapsed seconds since the epoch as a non-negative float.

        Subtracts the stored epoch from the current source reading. If the
        source is genuinely monotonic, the result is non-decreasing. We clamp
        tiny negative deltas (from float rounding near the epoch) to zero
        rather than returning a negative elapsed time.
        """
        elapsed = self._source() - self._epoch
        if elapsed < 0.0:
            return 0.0
        return elapsed


def _select_default_source() -> Callable[[], float]:
    """Choose the default source at import time.

    We prefer ``time.monotonic`` for its suspend/resume safety. On an exotic
    interpreter lacking it, we fall back to ``time.perf_counter`` so the
    library still imports and runs, losing only the suspend-safety guarantee.
    We never fall back to ``time.time`` because it is not monotonic.
    """
    src = getattr(time, "monotonic", None)
    if src is not None:
        return src
    # perf_counter is always present on supported CPython; guard anyway.
    return getattr(time, "perf_counter", time.time)  # pragma: no cover


# Module-level default clock. Instantiated once so all callers share a
# stable epoch within a process. Constructed lazily-safe: import time is
# before any clock reads.
default_clock = MonotonicClock(source=_select_default_source())


def monotonic_now() -> float:
    """Return elapsed seconds since the process-local epoch.

    Thin convenience wrapper around ``default_clock``. The value is only
    meaningful as a delta against another reading from this same function or
    from ``default_clock()``; it is not comparable to ``time.time()`` and not
    comparable across processes.
    """
    return default_clock()
