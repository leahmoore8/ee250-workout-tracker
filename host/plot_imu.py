#!/usr/bin/env python3
"""Plot timestamped IMU CSV measurements; no filtering or rep detection.

AI assistance: Developed with OpenAI Codex. Review and understand this code
and acknowledge assistance in the project write-up.
"""

import argparse
import csv
import math
from pathlib import Path
import statistics


CHANNELS = ("ax_g", "ay_g", "az_g", "gx_dps", "gy_dps", "gz_dps")


def load_samples(path):
    """Read measurement columns and reject invalid or unordered samples.

    Ground-truth label columns are deliberately not needed by this plotter.
    """
    times = []
    signals = {name: [] for name in CHANNELS}
    sources = set()
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        missing = set(("t_us",) + CHANNELS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing CSV columns: {', '.join(sorted(missing))}")
        for line, row in enumerate(reader, start=2):
            try:
                timestamp = int(row["t_us"])
                values = [float(row[name]) for name in CHANNELS]
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Invalid numeric value on CSV line {line}") from exc
            if timestamp < 0 or (times and timestamp <= times[-1]):
                raise ValueError(f"Timestamps must be nonnegative and strictly increasing (line {line})")
            if not all(math.isfinite(value) for value in values):
                raise ValueError(f"Nonfinite measurement on CSV line {line}")
            times.append(timestamp)
            for name, value in zip(CHANNELS, values):
                signals[name].append(value)
            sources.add(row.get("source") or "unspecified")
    if len(times) < 2:
        raise ValueError("At least two samples are required")
    seconds = [(timestamp - times[0]) / 1_000_000 for timestamp in times]
    intervals = [(b - a) / 1_000_000 for a, b in zip(times, times[1:])]
    return seconds, signals, sources, intervals


def plot_samples(seconds, signals, sources, output):
    """Save six raw traces with shared time and comparable scales per sensor."""
    import matplotlib
    matplotlib.use("Agg")  # Save a PNG even without a graphical desktop.
    import matplotlib.pyplot as plt

    from plot_style import apply_style, CORAL, ROSE, PINK, PURPLE, BLUE, PLUM
    apply_style(plt)
    fig, axes = plt.subplots(3, 2, figsize=(12, 8), sharex=True, sharey="col")
    for axis_index, axis_name in enumerate("xyz"):
        for column, (prefix, suffix, unit, color) in enumerate((
            ("a", "g", "g", (CORAL, ROSE, PINK)[axis_index]),
            ("g", "dps", "deg/s", (PURPLE, BLUE, PLUM)[axis_index]),
        )):
            key = f"{prefix}{axis_name}_{suffix}"
            ax = axes[axis_index, column]
            ax.plot(seconds, signals[key], color=color, linewidth=1.1)
            ax.set_ylabel(f"{key} ({unit})")
            ax.grid(alpha=0.7)
    axes[0, 0].set_title("Acceleration (includes gravity)")
    axes[0, 1].set_title("Angular velocity")
    for ax in axes[-1]:
        ax.set_xlabel("Time since first sample (s)")
    fig.suptitle(f"Raw IMU signals | source: {', '.join(sorted(sources))}")
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects any existing image.
    with output.open("xb") as stream:
        fig.savefig(stream, format="png", dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="IMU CSV recording")
    parser.add_argument("--output", type=Path, required=True, help="New PNG file path")
    args = parser.parse_args()
    try:
        seconds, signals, sources, intervals = load_samples(args.input)
        plot_samples(seconds, signals, sources, args.output)
    except ModuleNotFoundError as exc:
        if exc.name == "matplotlib":
            parser.error("Plotting needs matplotlib. Install with: python3 -m pip install matplotlib")
        raise
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Read {len(seconds)} samples; first-to-last span: {seconds[-1]:.2f} s")
    print(f"Median sample interval: {statistics.median(intervals) * 1000:.2f} ms")
    print(f"Interval range: {min(intervals) * 1000:.2f} to {max(intervals) * 1000:.2f} ms")
    print(f"Saved raw signal plot to {args.output}")


if __name__ == "__main__":
    main()
