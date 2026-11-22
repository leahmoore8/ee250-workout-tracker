"""Synthetic state-transition checks. AI assistance: OpenAI Codex."""
import unittest
from simulate_imu import generate_session
from track_workout import WorkoutTracker


def run_fixture(sets=2, stop=None, gap=None):
    tracker = WorkoutTracker()
    rows = []
    for r in generate_session(250, sets):
        t = r['t_us']/1e6
        if stop is not None and t > stop:
            break
        if gap and gap[0] <= t < gap[1]:
            continue
        rows.append(tracker.update(t, r['gx_dps'], r['gy_dps'], r['gz_dps']))
    return tracker, rows


class WorkoutTests(unittest.TestCase):
    def test_two_sets_and_no_split_at_turnarounds(self):
        tracker, rows = run_fixture()
        self.assertEqual([s['reps'] for s in tracker.sets], [10, 10])
        self.assertTrue(all(s['status']=='complete' for s in tracker.sets))
        self.assertEqual(rows[-1]['state'], 'RESTING')
        self.assertAlmostEqual(rows[-1]['rest_s'], 10, delta=0.1)
        for s in tracker.sets:
            self.assertGreaterEqual(s['end_confirmed_s']-s['end_s'], 3)

    def test_initial_rest_is_not_a_set(self):
        tracker, rows = run_fixture(stop=4)
        self.assertEqual(tracker.sets, [])
        self.assertEqual(rows[-1]['state'], 'IDLE')
        self.assertEqual(rows[-1]['rest_s'], 0)

    def test_recording_end_does_not_force_completion(self):
        tracker, rows = run_fixture(stop=20)
        self.assertEqual(tracker.sets, [])
        self.assertIsNotNone(tracker.active)

    def test_gap_interrupts_instead_of_inventing_rest(self):
        tracker, rows = run_fixture(stop=15, gap=(10, 15))
        self.assertEqual(tracker.sets[0]['status'], 'interrupted')
        self.assertEqual(rows[-1]['rest_s'], 0)
        self.assertNotEqual(rows[-1]['state'], 'RESTING')

    def test_other_axis_motion_blocks_rest(self):
        tracker, _ = run_fixture(stop=34)
        for i in range(1, 501):
            tracker.update(34+i/50, 30, 0, 0)
        self.assertIsNotNone(tracker.active)
        self.assertEqual(tracker.sets, [])

    def test_movement_resets_rest_without_starting_false_set(self):
        tracker, _ = run_fixture(sets=1)
        row = tracker.update(45, 40, 0, 0)
        self.assertEqual(row['state'], 'MOVING')
        self.assertEqual(row['rest_s'], 0)
        self.assertEqual(len(tracker.sets), 1)
        self.assertIsNone(tracker.active)


if __name__ == '__main__':
    unittest.main()
