# Monotonic Wall Time Adapter

A single clock function returning a monotonic float with a stable, process-local epoch, hiding the choice between `time.monotonic` and `time.perf_counter`.

## Usage

```python
from monotonic_wall_time_adapter import monotonic_now, default_clock, MonotonicClock

# Simplest use: seconds since the process started (modulo import time).
elapsed = monotonic_now()

# Share one clock across modules.
t0 = default_clock()
# ... do work ...
t1 = default_clock()
delta = t1 - t0

# Inject a fake source for deterministic tests.
clock = MonotonicClock(source=lambda: 3.0)
assert clock() == 0.0  # epoch sampled at construction
```

## Why this exists

Code that measures intervals wants two things at once: a clock that never goes backwards, and a single name to depend on so the underlying primitive can be swapped without a sweep of edits. `time.monotonic` and `time.perf_counter` are both monotonic on CPython, but they differ in one awkward way — `perf_counter` can advance across system suspend on some platforms, while `monotonic` is defined not to. This library picks `monotonic` as the default for suspend/resume safety and wraps it behind an injectable type.

The trade-off is that `perf_counter` can be marginally lower overhead and higher resolution for tight in-process benchmarking. If you are benchmarking nanosecond-scale loops and never suspend, use `perf_counter` directly instead.

## Edge you will hit

Values from this clock are only meaningful as deltas against other readings from the same clock instance (or from `monotonic_now`). They are not comparable to `time.time()`, not comparable across processes, and not comparable across separate `MonotonicClock` instances — each instance samples its own epoch at construction. The `epoch` property and the `epoch=` constructor argument exist precisely so you can share an origin when you need to.

If the underlying source ever reports a reading fractionally below the stored epoch due to float rounding, the implementation clamps the result to `0.0` rather than returning a negative elapsed time.

## Performance

The window keeps a bounded buffer, so `push` is constant time and memory does not
grow with the length of the stream. `peak` and `trough` are linear in the window
size, which is the trade that keeps `push` cheap.

## Limitations

Values are coerced to floats, so very large integers lose precision. If you need
exact integer aggregates over a window, this is the wrong tool.

## Design notes

The window stores values eagerly rather than keeping running aggregates. Running
sums drift with floating point over long streams, and recomputing from a small
buffer is cheap enough that the drift is not worth the speed.

