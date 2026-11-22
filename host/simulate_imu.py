#!/usr/bin/env python3
"""Generate synthetic IMU CSV for software development, not sensor validation.

AI assistance: Developed with OpenAI Codex; contributors must review and
understand this code and acknowledge assistance in the project write-up.
"""

import argparse
import csv
import math
from pathlib import Path
import random


SAMPLE_RATE_HZ = 50
INITIAL_REST_S = 5
REP_DURATION_S = 3
REP_COUNT = 10
FINAL_REST_S = 10

FIELDS = (
    "source", "seq", "t_us", "ax_g", "ay_g", "az_g",
    "gx_dps", "gy_dps", "gz_dps", "label_phase", "label_completed_reps",
)


def generate_samples(seed):
    """Yield a repeatable rest/movement/rest sequence at exact virtual times.

    A rigid sensor rotates about its y axis from 0 to 90 degrees and back.
    Acceleration contains only projected gravity and noise: translational
    acceleration, sensor bias, and realistic wrist mechanics are omitted.
    Gyroscope y is the analytic derivative of the rotation angle.
    """
    rng = random.Random(seed)
    motion_start = INITIAL_REST_S * SAMPLE_RATE_HZ
    samples_per_rep = REP_DURATION_S * SAMPLE_RATE_HZ
    motion_end = motion_start + REP_COUNT * samples_per_rep
    total_samples = motion_end + FINAL_REST_S * SAMPLE_RATE_HZ

    for seq in range(total_samples):
        angle_deg = 0.0
        angular_speed_dps = 0.0
        phase = "rest"
        completed = 0

        if motion_start <= seq < motion_end:
            phase = "movement"
            motion_sample = seq - motion_start
            completed = motion_sample // samples_per_rep
            cycle = 2 * math.pi * (motion_sample % samples_per_rep) / samples_per_rep
            angle_deg = 45 * (1 - math.cos(cycle))
            angular_speed_dps = 45 * (2 * math.pi / REP_DURATION_S) * math.sin(cycle)
        elif seq >= motion_end:
            completed = REP_COUNT

        angle_rad = math.radians(angle_deg)
        acceleration = (-math.sin(angle_rad), 0.0, math.cos(angle_rad))
        gyro = (0.0, angular_speed_dps, 0.0)
        values = {
            "source": "synthetic",
            "seq": seq,
            "t_us": seq * 1_000_000 // SAMPLE_RATE_HZ,
        }
        for name, value in zip(("ax_g", "ay_g", "az_g"), acceleration):
            values[name] = round(value + rng.gauss(0, 0.01), 6)
        for name, value in zip(("gx_dps", "gy_dps", "gz_dps"), gyro):
            values[name] = round(value + rng.gauss(0, 0.5), 6)
        values["label_phase"] = phase
        values["label_completed_reps"] = completed
        yield values


def generate_session(seed, sets):
    """Repeat the original fixture; preserve its default single-set output."""
    block_samples = (INITIAL_REST_S + REP_COUNT * REP_DURATION_S + FINAL_REST_S) * SAMPLE_RATE_HZ
    for block in range(sets):
        for row in generate_samples(seed + block):
            row["seq"] += block * block_samples
            row["t_us"] = row["seq"] * 1_000_000 // SAMPLE_RATE_HZ
            row["label_completed_reps"] += block * REP_COUNT
            yield row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New CSV path; existing files are never overwritten")
    parser.add_argument("--seed", type=int, default=250, help="Random seed for repeatable noise (default: 250)")
    parser.add_argument("--sets", type=int, default=1, help="Number of 10-cycle blocks (default: 1)")
    args = parser.parse_args()
    if args.sets < 1:
        parser.error("--sets must be positive")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open("x", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            count = 0
            for sample in generate_session(args.seed, args.sets):
                writer.writerow(sample)
                count += 1
    except FileExistsError:
        parser.error(f"Output already exists: {args.output}. Choose a new filename.")
    print(f"Wrote {count} SYNTHETIC samples at {SAMPLE_RATE_HZ} Hz to {args.output}")
    print(f"Sequence: {args.sets} block(s), each {INITIAL_REST_S}s rest, {REP_COUNT} cycles of {REP_DURATION_S}s, {FINAL_REST_S}s rest.")
    print("Timestamps are simulated; this does not acquire sensor data or run in real time.")


if __name__ == "__main__":
    main()
