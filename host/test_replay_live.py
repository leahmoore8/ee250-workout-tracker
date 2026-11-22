"""Playback scheduling and reporting checks. AI assistance: OpenAI Codex."""
import unittest
from replay_live import paced_samples, EventReporter
from simulate_imu import generate_session
from track_workout import WorkoutTracker


class FakeClock:
    def __init__(self):
        self.now = 100.0
    def clock(self):
        return self.now
    def sleep(self, duration):
        self.now += duration


class ReplayTests(unittest.TestCase):
    def test_absolute_deadlines_do_not_accumulate_processing_delay(self):
        clock = FakeClock()
        times = [0, 0.02, 0.04, 0.06]
        signals = {k: [0]*4 for k in ('gx_dps', 'gy_dps', 'gz_dps')}
        seen = []
        for sample in paced_samples(times, signals, clock=clock.clock, sleep=clock.sleep):
            seen.append(clock.now - 100)
            clock.now += 0.005
        for actual, expected in zip(seen, times):
            self.assertAlmostEqual(actual, expected)

    def test_speed_changes_schedule_not_detector_results(self):
        source = list(generate_session(250, 2))
        times = [r['t_us']/1e6 for r in source]
        signals = {k: [r[k] for r in source] for k in ('gx_dps', 'gy_dps', 'gz_dps')}
        for speed in (1, 10):
            clock = FakeClock()
            tracker = WorkoutTracker()
            messages = []
            reporter = EventReporter(messages.append)
            for sample in paced_samples(times, signals, speed, clock.clock, clock.sleep):
                row = tracker.update(*sample)
                reporter.update(row, tracker)
            self.assertAlmostEqual(clock.now-100, times[-1]/speed)
            self.assertEqual([r['reps'] for r in tracker.sets], [10, 10])
            self.assertEqual(sum(' | Rep ' in m for m in messages), 20)
            self.assertEqual(sum('complete |' in m for m in messages), 2)
            rest = [m for m in messages if 'RESTING |' in m]
            self.assertEqual(len(rest), len(set(rest)))
            self.assertLess(len(rest), 30)

    def test_invalid_speeds(self):
        for speed in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                list(paced_samples([], {}, speed))


if __name__ == '__main__':
    unittest.main()
