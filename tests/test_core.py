import unittest

from monotonic_wall_time_adapter import MonotonicClock, default_clock, monotonic_now
from monotonic_wall_time_adapter.core import _select_default_source


class FakeSource:
    """A scriptable, deterministic time source for tests."""

    def __init__(self, readings):
        if not readings:
            raise ValueError("readings must be non-empty")
        self._readings = list(readings)
        self._idx = 0

    def __call__(self):
        if self._idx >= len(self._readings):
            # Hold the last value rather than raising, so a test that reads
            # more times than expected still gets a deterministic answer.
            return self._readings[-1]
        v = self._readings[self._idx]
        self._idx += 1
        return v


class TestMonotonicClock(unittest.TestCase):

    # --- construction & defaults ---

    def test_default_source_is_monotonic_or_perf_counter(self):
        src = _select_default_source()
        # Either time.monotonic or time.perf_counter is acceptable; time.time
        # is NOT, because it is not monotonic.
        import time
        self.assertIn(src, (time.monotonic, time.perf_counter))

    def test_default_clock_callable_returns_float(self):
        # We cannot assert a range, but we can assert the type and
        # non-negativity, which are real properties of the implementation.
        value = default_clock()
        self.assertIsInstance(value, float)
        self.assertGreaterEqual(value, 0.0)

    def test_monotonic_now_matches_default_clock(self):
        # Both must read from the same clock instance; near-simultaneous
        # reads should be ordered (now >= clock()) because the clock is
        # non-decreasing. We compare with >= which holds even under float
        # rounding because both go through the same epoch subtraction.
        a = default_clock()
        b = monotonic_now()
        self.assertGreaterEqual(b, a)

    # --- injected source behaviour ---

    def test_first_call_is_zero_relative_to_sampled_epoch(self):
        fake = FakeSource([100.0, 100.0, 100.0])
        clock = MonotonicClock(source=fake)
        # The first read in __init__ consumed index 0 (epoch). The first
        # __call__ consumes index 1.
        self.assertEqual(clock(), 0.0)

    def test_elapsed_is_difference_from_epoch(self):
        fake = FakeSource([50.0, 52.5, 60.0])
        clock = MonotonicClock(source=fake)
        # epoch sampled at construction -> 50.0
        self.assertAlmostEqual(clock(), 2.5)
        self.assertAlmostEqual(clock(), 10.0)

    def test_clock_is_non_decreasing_under_monotonic_source(self):
        fake = FakeSource([0.0, 0.0, 1.0, 1.0, 2.0, 2.0, 2.0])
        clock = MonotonicClock(source=fake)
        prev = clock()
        for _ in range(3):
            cur = clock()
            self.assertGreaterEqual(cur, prev)
            prev = cur

    def test_negative_float_rounding_near_epoch_clamped_to_zero(self):
        # Construct with an explicit epoch and then have the source report a
        # value an epsilon *below* it, which can happen due to float
        # subtraction ordering. The implementation clamps negatives to 0.
        fake = FakeSource([1.0000000000000002, 1.0])
        clock = MonotonicClock(source=fake, epoch=1.0000000000000002)
        self.assertEqual(clock(), 0.0)

    def test_explicit_epoch_is_respected(self):
        fake = FakeSource([1000.0])
        clock = MonotonicClock(source=fake, epoch=10.0)
        # Source returns 1000.0, epoch is 10.0 -> 990.0 elapsed.
        self.assertAlmostEqual(clock(), 990.0)

    def test_epoch_property_exposes_stored_epoch(self):
        fake = FakeSource([42.0])
        clock = MonotonicClock(source=fake, epoch=42.0)
        self.assertEqual(clock.epoch, 42.0)

    def test_source_property_exposes_callable(self):
        fake = FakeSource([1.0])
        clock = MonotonicClock(source=fake)
        self.assertIs(clock.source, fake)

    def test_reset_reanchors_epoch_to_now(self):
        fake = FakeSource([0.0, 0.0, 0.0, 5.0])
        clock = MonotonicClock(source=fake)  # epoch -> 0.0 (idx 0)
        self.assertAlmostEqual(clock(), 0.0)        # idx 1 -> 0.0
        new_epoch = clock.reset()                   # idx 2 -> 0.0
        self.assertEqual(new_epoch, 0.0)
        self.assertEqual(clock.epoch, 0.0)
        self.assertAlmostEqual(clock(), 5.0)       # idx 3 -> 5.0

    def test_reset_accepts_explicit_epoch(self):
        fake = FakeSource([100.0])
        clock = MonotonicClock(source=fake, epoch=0.0)
        returned = clock.reset(epoch=90.0)
        self.assertEqual(returned, 90.0)
        self.assertEqual(clock.epoch, 90.0)
        self.assertAlmostEqual(clock(), 10.0)

    def test_two_clocks_share_epoch_when_given_same_explicit_value(self):
        fake_a = FakeSource([20.0])
        fake_b = FakeSource([20.0])
        shared_epoch = 10.0
        a = MonotonicClock(source=fake_a, epoch=shared_epoch)
        b = MonotonicClock(source=fake_b, epoch=shared_epoch)
        self.assertEqual(a.epoch, b.epoch)
        self.assertAlmostEqual(a(), 10.0)
        self.assertAlmostEqual(b(), 10.0)

    def test_instance_is_callable(self):
        fake = FakeSource([0.0, 7.0])
        clock = MonotonicClock(source=fake)
        self.assertTrue(callable(clock))
        self.assertAlmostEqual(clock(), 7.0)

    def test_readings_not_comparable_across_independent_clocks(self):
        # This test documents the intended semantics: two clocks each with
        # their own sampled epoch produce values in independent frames. We
        # do NOT assert ordering between them.
        fake_a = FakeSource([5.0, 5.0, 6.0])
        fake_b = FakeSource([1000.0, 1000.0, 1001.0])
        a = MonotonicClock(source=fake_a)
        b = MonotonicClock(source=fake_b)
        av = a()
        bv = b()
        # Both are non-negative floats; nothing else is guaranteed.
        self.assertIsInstance(av, float)
        self.assertIsInstance(bv, float)
        self.assertGreaterEqual(av, 0.0)
        self.assertGreaterEqual(bv, 0.0)


if __name__ == "__main__":
    unittest.main()
