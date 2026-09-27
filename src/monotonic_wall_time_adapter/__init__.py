"""Monotonic Wall Time Adapter.

A single clock function returning a monotonic float with a stable epoch.
"""

from .core import MonotonicClock, default_clock, monotonic_now

__all__ = ["MonotonicClock", "default_clock", "monotonic_now"]
