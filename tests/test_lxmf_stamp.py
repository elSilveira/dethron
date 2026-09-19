"""The LXMF stamp defect, proven deterministically, and a guard for when upstream fixes it."""
import inspect
import os
import unittest
from unittest import mock

try:
    from LXMF import LXStamper
    from dethron.lxmf_stamp import UPSTREAM, defect_present, generate_stamp, install
except ImportError as exc:  # pragma: no cover - needs the pinned environment
    raise unittest.SkipTest('requires .venv-gateway') from exc

PEERING = LXStamper.WORKBLOCK_EXPAND_ROUNDS_PEERING


def frozen_clock():
    """A clock that does not advance is exactly what a fast search sees."""
    return 1000.0


class StampDefectTests(unittest.TestCase):
    def test_the_pinned_version_still_divides_without_a_guard(self):
        source = inspect.getsource(LXStamper)
        self.assertIn('speed = rounds/duration', source)
        self.assertNotIn('speed = rounds/duration if duration > 0', source)
        self.assertTrue(defect_present())

    def test_detection_is_behavioural_and_not_a_text_match(self):
        # The guarded line still contains the original expression, so a substring
        # match would report the defect forever and the workaround would never lift.
        guarded = inspect.getsource(LXStamper).replace(
            'speed = rounds/duration', 'speed = rounds/duration if duration > 0 else 0')
        self.assertIn('speed = rounds/duration', guarded)

    def test_upstream_destroys_a_valid_stamp_when_the_clock_does_not_advance(self):
        with mock.patch.object(LXStamper.time, 'time', frozen_clock):
            with self.assertRaises(ZeroDivisionError):
                UPSTREAM(os.urandom(32), 1, expand_rounds=PEERING)

    def test_the_workaround_returns_the_stamp_under_the_same_clock(self):
        with mock.patch.object(LXStamper.time, 'time', frozen_clock):
            stamp, value = generate_stamp(os.urandom(32), 1, expand_rounds=PEERING)
        self.assertIsNotNone(stamp)
        self.assertGreaterEqual(value, 1)

    def test_a_cheap_peering_stamp_always_returns_a_usable_value(self):
        install()
        for _ in range(40):
            stamp, value = generate_stamp(os.urandom(32), 1, expand_rounds=PEERING)
            self.assertIsNotNone(stamp)
            self.assertGreaterEqual(value, 1)

    def test_installing_replaces_the_upstream_function_once(self):
        # Only while the defect is present; against a fixed LXMF, install() leaves it alone.
        self.assertTrue(install())
        self.assertEqual(LXStamper.generate_stamp.__module__, 'dethron.lxmf_stamp')
        install()
        self.assertIs(LXStamper.generate_stamp, generate_stamp)


if __name__ == '__main__':
    unittest.main()
