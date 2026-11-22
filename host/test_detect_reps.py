"""Synthetic regression checks, not real exercise validation.
AI assistance: Developed with OpenAI Codex.
"""
import math
import random
import unittest
from detect_reps import process


def wave(period=3, cycles=4):
    times = [i / 50 for i in range(round((4 + period * cycles) * 50))]
    values = [90 * math.sin(2 * math.pi * (t - 2) / period)
              if 2 <= t < 2 + period * cycles else 0 for t in times]
    return times, values


class DetectorTests(unittest.TestCase):
    def test_full_cycles_at_multiple_speeds(self):
        for period in (1.5, 3, 5):
            t, v = wave(period)
            self.assertEqual(len(process(t, v)[1]), 4)

    def test_rest_noise(self):
        rng = random.Random(250)
        t = [i / 50 for i in range(1500)]
        self.assertEqual(process(t, [rng.gauss(0, 2) for _ in t])[1], [])

    def test_brief_opposite_spikes(self):
        t = [i / 50 for i in range(500)]
        v = [0.] * len(t)
        v[100], v[130] = 100, -100
        self.assertEqual(process(t, v)[1], [])

    def test_positive_half_cycles_only(self):
        t, v = wave()
        self.assertEqual(process(t, [max(0, x) for x in v])[1], [])

    def test_gap_discards_partial_cycle(self):
        t, v = wave(cycles=1)
        kept = [(time, value) for time, value in zip(t, v) if not 3.2 <= time <= 3.8]
        t, v = map(list, zip(*kept))
        self.assertEqual(process(t, v)[1], [])

    def test_slow_cycle_times_out(self):
        t, v = wave(period=10, cycles=1)
        self.assertEqual(process(t, v)[1], [])


if __name__ == '__main__':
    unittest.main()
