#!/usr/bin/env python3
"""Prototype cycle detector for synthetic gyroscope data, not validated curls.

AI assistance: Developed with OpenAI Codex; review and understand the code
and acknowledge assistance in the project write-up.
"""
import argparse
import math
from pathlib import Path
from plot_imu import load_samples


class RepDetector:
    """Causal filter and ordered movement states; update with one sample at a time.

    Defaults are development settings, not calibrated physiological thresholds.
    Assumes an outward positive rotation followed by a negative return rotation.
    """
    def __init__(self):
        self.count = 0
        self.previous_time = None
        self.filtered = 0.0
        self.reset_cycle()

    def reset_cycle(self):
        self.state = 'WAIT_POSITIVE'
        self.started = None
        self.run_start = None

    def held(self, condition, t, duration):
        # Require consecutive samples satisfying a condition, not one spike.
        if not condition:
            self.run_start = None
            return False
        if self.run_start is None:
            self.run_start = t
        return t - self.run_start >= duration

    def update(self, t, value):
        if not math.isfinite(t) or not math.isfinite(value):
            raise ValueError('Time and angular velocity must be finite')
        if self.previous_time is not None and t <= self.previous_time:
            raise ValueError('Time must increase strictly')
        dt = 0 if self.previous_time is None else t - self.previous_time
        if self.previous_time is None or dt > 0.15:
            # Never join a partial cycle across missing data.
            self.reset_cycle()
            self.filtered = value
        else:
            alpha = 1 - math.exp(-dt / 0.06)
            self.filtered += alpha * (value - self.filtered)
        self.previous_time = t
        if self.started is not None and t - self.started > 6.0:
            self.reset_cycle()
        v = self.filtered
        event = False
        if self.state == 'WAIT_POSITIVE':
            if self.held(v >= 20, t, 0.12):
                self.started = self.run_start
                self.state = 'WAIT_NEGATIVE'
                self.run_start = None
        elif self.state == 'WAIT_NEGATIVE':
            if self.held(v <= -20, t, 0.12):
                self.state = 'WAIT_RETURN'
                self.run_start = None
        elif self.state == 'WAIT_RETURN':
            # Returning above -8 after a negative lobe approximates completion.
            # It does not prove that the wrist returned to its original angle.
            if self.held(v >= -8, t, 0.06):
                if 0.8 <= t - self.started <= 6.0:
                    self.count += 1
                    event = True
                self.reset_cycle()
        return self.filtered, event


def process(times, values):
    detector = RepDetector()
    filtered, events = [], []
    for t, value in zip(times, values):
        smooth, event = detector.update(t, value)
        filtered.append(smooth)
        if event:
            events.append(t)
    return filtered, events


def save_plot(times, raw, filtered, events, sources, axis, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from plot_style import apply_style, CORAL, PINK, PURPLE, MUTED
    apply_style(plt)
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(times, raw, color=PINK, linewidth=1.2, label='Raw')
    ax.plot(times, filtered, color=PURPLE, linewidth=1.6, label='Filtered')
    for level in (20, -20, -8):
        ax.axhline(level, color=MUTED, linestyle=':', linewidth=0.8)
    for index, t in enumerate(events, 1):
        ax.axvline(t, color=CORAL, linewidth=1.2, linestyle='--', label='Count event' if index == 1 else None)
        ax.text(t, 0.97, str(index), transform=ax.get_xaxis_transform(), ha='center', va='top', fontsize=9, bbox=dict(facecolor='white', edgecolor='none', alpha=0.8))
    ax.set(xlabel='Time since first sample (s)', ylabel=f'{axis} (deg/s)',
           title=f'Prototype: {len(events)} detected cycles | source: {", ".join(sorted(sources))}')
    ax.legend(loc='lower left')
    ax.grid(alpha=0.7)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        fig.savefig(stream, format='png', dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--axis', choices=('gx_dps', 'gy_dps', 'gz_dps'), default='gy_dps')
    parser.add_argument('--plot', type=Path, help='Optional new PNG path (requires matplotlib)')
    args = parser.parse_args()
    try:
        times, signals, sources, _ = load_samples(args.input)
        filtered, events = process(times, signals[args.axis])
        if args.plot:
            save_plot(times, signals[args.axis], filtered, events, sources, args.axis, args.plot)
    except (OSError, ValueError, ImportError) as exc:
        parser.error(str(exc))
    print(f'Source: {", ".join(sorted(sources))} | axis: {args.axis}')
    print(f'Detected cycles: {len(events)}')
    print('Event times (s): ' + ', '.join(f'{t:.2f}' for t in events))
    print('Prototype only: axis, sign, thresholds, and timing require real-data validation.')
    if args.plot:
        print(f'Saved {args.plot}')


if __name__ == '__main__':
    main()
