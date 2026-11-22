# Laptop development: first milestone

Run from the repository root with Python 3; no third-party packages are needed:

```sh
python3 host/simulate_imu.py --output /tmp/workout_tracker_simulated_imu.csv
```

The program creates a CSV with 2,250 samples representing 45 seconds at 50 Hz:
5 seconds of rest, 10 movement cycles lasting 3 seconds each, and 10 seconds
of rest. It generates the file immediately rather than waiting 45 seconds.
An existing output file is never overwritten; choose a different path to rerun.

## Record format

| Fields | Meaning |
| --- | --- |
| `source` | Always `synthetic` in this program |
| `seq` | Sample number, starting at zero |
| `t_us` | Microseconds since the start of this recording, not wall-clock time |
| `ax_g`, `ay_g`, `az_g` | Acceleration in g, including gravity |
| `gx_dps`, `gy_dps`, `gz_dps` | Angular velocity in degrees per second |
| `label_phase` | Known synthetic phase: `rest` or `movement` |
| `label_completed_reps` | Known number of fully completed synthetic cycles |

The `label_` fields are ground truth for evaluating processing, never inputs
to a rep detector. Real firmware need not produce these labels. This is an
initial recording format; networking can be added separately.

## How the generator works

`generate_samples()` uses sample indices to produce exact 20,000-microsecond
spacing. During movement, a cosine-based angle goes from 0 to 90 degrees and
back; its derivative produces the y-axis gyroscope signal. The angle also
rotates gravity between the accelerometer x and z axes. Small seeded random
noise makes reruns reproducible without making every sample identical.

`main()` handles command-line arguments and writes the samples to CSV.

This deliberately simple model omits translational acceleration, wrist
mechanics, bias, dropouts, and motion artifacts. Ten synthetic cycles do not
demonstrate ten correctly detected real curls. No rep detector exists yet.

Next: plot all six signals against `t_us`, then build processing that uses
only measurement fields. Validate the model-independent parts of the pipeline
here, and select features and tune thresholds with actual MPU6050 recordings.

AI assistance: This script and documentation were developed with OpenAI Codex.
Team members must review the implementation and explain its design choices.


## Plot the recording

The plotting script uses matplotlib (the simulator still uses only Python's
standard library). Install it into the Python environment you use for this
project, then run:

```sh
python3 -m pip install matplotlib
python3 host/plot_imu.py /tmp/workout_tracker_simulated_imu.csv --output /tmp/workout_tracker_imu.png
open /tmp/workout_tracker_imu.png
```

Choose a new output filename if the PNG already exists. The plot has six raw
traces: acceleration on the left and angular velocity on the right. Axes share
time and use consistent vertical scales within each column. The title identifies
the CSV data source. No filtering, rep detection, or ground-truth labels are used.

`load_samples()` checks required measurement columns, numeric values, and
strictly increasing timestamps, then converts microseconds to elapsed seconds.
`plot_samples()` saves the six traces as a PNG; `main()` reports sample timing.
A 45-second recording has a first-to-last timestamp span of 44.98 seconds because
the first sample is at zero and the final sample is one interval before 45.

For the default simulation, inspect the quiet intervals at 0–5 and 35–45 seconds,
the changes in x/z acceleration as gravity rotates, and the positive/negative
lobes of y angular velocity during each movement cycle. The other axes mostly
contain noise by construction. Real wrist motion may distribute across different
axes, so this does not establish the best axis for real rep counting.


## First cycle detector (synthetic validation only)

```sh
python3 host/detect_reps.py /tmp/workout_tracker_simulated_imu.csv --plot /tmp/workout_tracker_reps.png
open /tmp/workout_tracker_reps.png
python3 -m unittest discover -s host -p 'test_detect_reps.py'
```

Omit `--plot` to run without matplotlib. The default sample produces 10 events;
labels are not used by the detector. Green lines mark estimated cycle completion.
The filter and dwell checks introduce a small delay (roughly 0.1 s on this file).

`RepDetector.update()` processes one timestamp and angular velocity at a time.
A causal exponential low-pass filter uses a 0.06-second time constant. The
state machine requires positive velocity >=20 deg/s for 0.12 s, then negative
velocity <=-20 deg/s for 0.12 s, then a return above -8 deg/s for 0.06 s. A
candidate must last 0.8–6 seconds from its first qualifying positive sample.
Gaps over 0.15 seconds discard pending cycles and reset the filter. Counts
already completed are preserved. These are provisional engineering settings.

`process()` replays a CSV through this same sample-by-sample interface;
`save_plot()` draws raw/filtered traces, thresholds, and count events.

Limitations: default y-axis and sign match the synthetic generator. Returning
near zero angular velocity does not prove a full range of motion; partial
back-and-forth gestures may count. Bias, mounting changes, and real motion
artifacts are untested. This is not yet set detection or a validated curl
counter. Tests cover synthetic cycles at several speeds, noise, brief spikes,
positive-only motion, missing samples, and a cycle that exceeds the timeout.


## Two sets and a rest timer

```sh
python3 host/simulate_imu.py --sets 2 --output /tmp/workout_tracker_two_sets.csv
python3 host/track_workout.py /tmp/workout_tracker_two_sets.csv --plot /tmp/workout_tracker_sets.png
open /tmp/workout_tracker_sets.png
python3 -m unittest discover -s host -p 'test_*.py'
```

The original single-set simulation remains the default. Two blocks produce
90 seconds (4,500 samples): movement at 5–35 and 50–80 seconds, with 15 seconds
between sets. Expected output: two completed sets of 10 reps and approximately
10 seconds of final continuous rest. Choose new filenames for reruns.

`WorkoutTracker.update()` consumes one timestamp and three gyro values at a
time and reuses `RepDetector`. A first confirmed rep creates a set; preceding
motion is `MOVING`, not yet confirmed exercise. The initial state is `IDLE`.
A gyro vector magnitude below 8 deg/s continuously for 3 seconds ends a set.
The state then becomes `RESTING`; the timer includes those first 3 seconds,
so it first appears at 3, not zero. New motion resets continuous rest; another
confirmed rep starts the next set. Completed counts remain in `tracker.sets`.

A gap greater than 0.15 seconds interrupts any active set, clears rest timing,
and discards partial reps. The gap is never credited as rest. This offline
replay detects a gap when the next sample arrives; live transport will also
need a watchdog for when no new sample arrives. Ending a recording does not
force an active set to complete. Interrupted sets are explicitly labeled.

The plot uses the exact shared project palette: purple signal, coral rep
markers, pink state, and blue rest duration. No label columns drive decisions.
All thresholds are provisional. Low rotation is only a motion proxy: it does
not establish physiological recovery or distinguish every kind of exercise.
Long pauses may split sets; translational motion and bias need further work.
Heart rate and readiness are not implemented in this milestone.

AI assistance: The set tracker, simulator extension, and tests were developed
with OpenAI Codex and require contributor review and understanding.


## Real-time CSV replay

```sh
python3 host/replay_live.py /tmp/workout_tracker_two_sets.csv
```

Default playback takes approximately 90 seconds. For a nine-second check:

```sh
python3 host/replay_live.py /tmp/workout_tracker_two_sets.csv --speed 10
```

No additional dependencies are needed. The file is validated and loaded before
playback; samples are then delivered individually to `WorkoutTracker.update()`.
`paced_samples()` uses absolute deadlines on a monotonic laptop clock, so
processing time does not accumulate as extra delay on every sample. If late,
it catches up in order without dropping samples. This is best-effort Python
scheduling, not a hard real-time guarantee. Sample timestamps always come from
the CSV, even during accelerated playback.

`EventReporter` prints changes of state, each rep, completed/interrupted sets,
and one rest message per recorded second. At 10x these rest updates arrive ten
times faster. Rest begins displaying at 3 seconds because confirmation requires
3 seconds of low motion. Recording gaps retain their duration during playback
and are handled by the existing tracker when the next sample arrives. There is
no independent live-disconnect watchdog yet.

Ctrl+C stops playback cleanly. Finishing or stopping playback never forces a
set to complete. The full two-set fixture should end with 4,500 processed
samples, two completed sets, and 20 detected reps. This milestone uses a local
CSV and terminal; MQTT, hardware input, and a live dashboard are still pending.

AI assistance: The replay script and its tests were developed with OpenAI Codex.


## Local MQTT milestone

One-time setup (use the same Python environment in both client terminals):

```sh
brew install mosquitto
python3 -m pip install -r host/requirements-mqtt.txt
```

From the repository root, use three terminals in this order:

1. Broker (leave running):

```sh
$(brew --prefix mosquitto)/sbin/mosquitto -c host/mosquitto-local.conf
```

2. Subscriber; wait for `READY`:

```sh
python3 host/mqtt_workout.py subscribe
```

3. Publisher:

```sh
python3 host/mqtt_workout.py publish --input /tmp/workout_tracker_two_sets.csv
```

For a quick check, add `--speed 10` to the publisher. Expected subscriber summary:
`Received 4500 samples | 2 completed sets | 20 detected reps`.
The subscriber exits on the end marker; restart it before each new publisher
run. Stop the foreground broker with Ctrl+C when finished. If port 1883 is
already in use, inspect the existing broker rather than starting another.

`mqtt_workout.py` has two modes. `publish` uses the existing paced CSV scheduler
and sends one JSON sample per message. `subscribe` waits for a successful
subscription acknowledgement, validates data in the main thread, and calls the
existing tracker/reporter. Paho's network thread only queues received payloads.
The same topic `workout/imu/v1` carries ordered sample and end messages.
Each sample includes version=1, type=sample, a unique session, source, seq,
t_us, ax_g/ay_g/az_g, and gx_dps/gy_dps/gz_dps. Units match the CSV. Labels are
not transmitted. The end message's seq is the expected total sample count.

QoS 1 is used, without retained measurements. The publisher waits for broker
acknowledgement; this does not prove subscriber receipt, so compare subscriber
totals. The receiver ignores duplicate sequence numbers and rejects missing or
out-of-order data, changed sessions, malformed values, and non-increasing time.
Start the subscriber first: this prototype has no message history or resume.

This milestone deliberately stops on broker loss, queue overflow, or five
seconds without a message after streaming begins. It does not silently count
an outage as rest. A malformed message also aborts with a clear error. Restart
both client commands after interruption. Automatic reconnection, resume,
last-will status, and a dashboard are future work. A recording gap longer than
five seconds also triggers this timeout. Ctrl+C stops either client.

The supplied broker config binds only to 127.0.0.1, allows local anonymous
clients, and stores no persistent sessions. It does not expose the broker to
the LAN or install a startup service. This is laptop pipeline testing, not the
final two-physical-node demo. ESP32 access will need a deliberate LAN broker
configuration later. `--host`, `--port`, and `--topic` are client options.

API reference: https://eclipse.dev/paho/clients/python/docs/
Paho is pinned in requirements-mqtt.txt; matplotlib remains optional for plots.
AI assistance: MQTT code and protocol tests were developed with OpenAI Codex.
