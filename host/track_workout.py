#!/usr/bin/env python3
"""Replay IMU samples through a prototype set/rest tracker.
AI assistance: Developed with OpenAI Codex; review and acknowledge in write-up.
"""
import argparse
import math
from pathlib import Path
from detect_reps import RepDetector
from plot_imu import load_samples


class WorkoutTracker:
    """Confirm sets with a rep; end after 3 s of continuous low rotation.

    Uses all three gyro axes for inactivity, selected y axis for reps.
    Thresholds are provisional. Low rotation does not prove physiological rest.
    """
    def __init__(self):
        self.detector = RepDetector()
        self.state = 'IDLE'
        self.previous = None
        self.quiet_since = None
        self.rest_since = None
        self.active = None
        self.sets = []

    def update(self, t, gx, gy, gz):
        if not all(math.isfinite(v) for v in (t, gx, gy, gz)):
            raise ValueError('Samples must be finite')
        if self.previous is not None and t <= self.previous:
            raise ValueError('Timestamps must increase')
        if self.previous is not None and t - self.previous > 0.15:
            if self.active is not None:
                self.active.update(status='interrupted', end_s=self.previous)
                self.sets.append(self.active)
                self.active = None
            self.state = 'UNKNOWN'
            self.quiet_since = self.rest_since = None
        self.previous = t
        filtered, rep = self.detector.update(t, gy)
        quiet = math.sqrt(gx*gx + gy*gy + gz*gz) < 8
        if quiet:
            if self.quiet_since is None:
                self.quiet_since = t
        else:
            self.quiet_since = None
            # Motion invalidates a continuous rest timer, even without a rep.
            self.rest_since = None
            if self.active is None:
                self.state = 'MOVING'
        if rep:
            if self.active is None:
                self.active = dict(number=len(self.sets)+1, reps=0,
                                   confirmed_s=t, status='active')
            self.active['reps'] += 1
            self.state = 'EXERCISING'
            self.rest_since = None
        if self.quiet_since is not None and t - self.quiet_since >= 3:
            if self.active is not None:
                self.active.update(status='complete', end_s=self.quiet_since,
                                   end_confirmed_s=t)
                self.sets.append(self.active)
                self.active = None
                self.detector.reset_cycle()
            if self.sets:
                self.state = 'RESTING'
                self.rest_since = self.quiet_since
            else:
                self.state = 'IDLE'
        rest = t - self.rest_since if self.rest_since is not None else 0
        return dict(t=t, filtered=filtered, state=self.state, rest_s=rest,
                    reps=self.active['reps'] if self.active else 0,
                    completed_sets=sum(record['status'] == 'complete' for record in self.sets),
                    set_number=self.active['number'] if self.active else len(self.sets), rep=rep)


def replay(times, signals):
    tracker = WorkoutTracker()
    rows = [tracker.update(t, signals['gx_dps'][i], signals['gy_dps'][i], signals['gz_dps'][i])
            for i, t in enumerate(times)]
    return tracker, rows


def save_plot(rows, sources, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from plot_style import apply_style, PURPLE, CORAL, BLUE, PINK, PLUM
    apply_style(plt)
    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    t = [r['t'] for r in rows]
    axes[0].plot(t, [r['filtered'] for r in rows], color=PURPLE)
    axes[0].set_ylabel('Gyroscope y (deg/s)')
    for r in rows:
        if r['rep']:
            axes[0].axvline(r['t'], color=CORAL, linestyle='--', linewidth=0.7)
    states = ['UNKNOWN', 'IDLE', 'MOVING', 'EXERCISING', 'RESTING']
    axes[1].step(t, [states.index(r['state']) for r in rows], where='post', color=PINK)
    axes[1].set_yticks(range(len(states)), states)
    axes[1].set_ylim(-0.3, len(states)-0.7)
    axes[2].plot(t, [r['rest_s'] for r in rows], color=BLUE)
    axes[2].set_ylabel('Confirmed rest (s)')
    counts = [r['completed_sets'] for r in rows]
    axes[3].step(t, counts, where='post', color=PLUM, linewidth=2)
    axes[3].set_yticks(range(max(counts) + 1))
    axes[3].set_ylim(-0.15, max(1, max(counts)) + 0.4)
    axes[3].set(ylabel='Completed sets', xlabel='Time since first sample (s)')
    for i in range(1, len(rows)):
        if counts[i] > counts[i-1]:
            axes[3].plot(t[i], counts[i], 'o', color=PLUM)
            axes[3].annotate(f'Set {counts[i]} complete', (t[i], counts[i]),
                             xytext=(-8, 10), textcoords='offset points',
                             ha='right', color=PLUM, fontsize=9)
    for ax in axes:
        ax.grid(alpha=0.7)
    fig.suptitle('Workout state, rest timer, and set count | source: ' + ', '.join(sorted(sources)))
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        fig.savefig(stream, format='png', dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--plot', type=Path)
    args = parser.parse_args()
    try:
        times, signals, sources, _ = load_samples(args.input)
        tracker, rows = replay(times, signals)
        if args.plot:
            save_plot(rows, sources, args.plot)
    except (ValueError, OSError, ImportError) as exc:
        parser.error(str(exc))
    print('Source: ' + ', '.join(sorted(sources)))
    for record in tracker.sets:
        print(f"Set {record['number']}: {record['reps']} reps | {record['status']} | end {record['end_s']:.2f}s")
    if tracker.active:
        print(f"Set {tracker.active['number']}: {tracker.active['reps']} reps | still active (recording ended)")
    print(f"Final state: {rows[-1]['state']} | continuous rest: {rows[-1]['rest_s']:.2f}s")
    print('Rest is confirmed after 3 s of low rotation, then timed from its onset. No readiness estimate yet.')


if __name__ == '__main__':
    main()
