#!/usr/bin/env python3
"""Paced CSV playback through the workout tracker; no hardware or MQTT.
AI assistance: Developed with OpenAI Codex; review and acknowledge in write-up.
"""
import argparse
import math
from pathlib import Path
import time
from plot_imu import load_samples
from track_workout import WorkoutTracker


def paced_samples(times, signals, speed=1.0, clock=time.monotonic, sleep=time.sleep):
    """Schedule against absolute monotonic deadlines to avoid sleep drift.

    Late samples are processed in order, never dropped. Detector timestamps
    remain recording time regardless of playback speed or scheduling delays.
    Clock/sleep injection allows deterministic tests without waiting.
    """
    if not math.isfinite(speed) or speed <= 0:
        raise ValueError('Speed must be positive and finite')
    origin = clock()
    for i, t in enumerate(times):
        deadline = origin + (t - times[0]) / speed
        while True:
            remaining = deadline - clock()
            if remaining <= 0:
                break
            sleep(min(remaining, 0.1))
        yield t, signals['gx_dps'][i], signals['gy_dps'][i], signals['gz_dps'][i]


class EventReporter:
    """Print state/rep/set events and one rest update per recording second."""
    def __init__(self, emit):
        self.emit = emit
        self.previous_state = None
        self.records_reported = 0
        self.rest_second = None

    def update(self, row, tracker):
        prefix = f"[{row['t']:6.2f}s] "
        for record in tracker.sets[self.records_reported:]:
            self.emit(prefix + f"Set {record['number']} {record['status']} | {record['reps']} reps")
        self.records_reported = len(tracker.sets)
        if row['state'] != self.previous_state:
            self.emit(prefix + row['state'])
        if row['rep']:
            self.emit(prefix + f"Set {row['set_number']} | Rep {row['reps']} | EXERCISING")
        if row['state'] == 'RESTING':
            second = int(row['rest_s'])
            if second != self.rest_second:
                self.emit(prefix + f'RESTING | {second} seconds')
            self.rest_second = second
        else:
            self.rest_second = None
        self.previous_state = row['state']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--speed', type=float, default=1.0,
                        help='Playback multiplier; default 1 (real time), 10 for a quick run')
    args = parser.parse_args()
    if not math.isfinite(args.speed) or args.speed <= 0:
        parser.error('--speed must be positive and finite')
    try:
        times, signals, sources, _ = load_samples(args.input)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print('CSV playback | source: ' + ', '.join(sorted(sources)), flush=True)
    print(f'{len(times)} samples | {args.speed:g}x speed | approximately {(times[-1]-times[0])/args.speed:.1f}s wall time', flush=True)
    print('Event times are recording seconds. Ctrl+C stops playback.', flush=True)
    tracker = WorkoutTracker()
    reporter = EventReporter(lambda message: print(message, flush=True))
    started = time.monotonic()
    processed = 0
    try:
        for sample in paced_samples(times, signals, args.speed):
            row = tracker.update(*sample)
            reporter.update(row, tracker)
            processed += 1
    except KeyboardInterrupt:
        print('\nPlayback stopped by user; no set completion inferred.', flush=True)
        return 130
    completed = sum(r['status'] == 'complete' for r in tracker.sets)
    reps = sum(r['reps'] for r in tracker.sets) + (tracker.active['reps'] if tracker.active else 0)
    print(f'Playback finished: {processed} samples | {completed} completed sets | {reps} detected reps | {time.monotonic()-started:.2f}s wall time')
    if tracker.active:
        print(f"Set {tracker.active['number']} remains active; end of file is not a set-ending event.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
