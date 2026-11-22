#!/usr/bin/env python3
"""Local MQTT CSV publisher and workout subscriber (one session per run).
AI assistance: Developed with OpenAI Codex; review and acknowledge in write-up.
"""
import argparse
import json
import math
from pathlib import Path
import queue
import threading
import time
import uuid
from plot_imu import load_samples, CHANNELS
from replay_live import paced_samples, EventReporter
from track_workout import WorkoutTracker

TOPIC = 'workout/imu/v1'


def decode(payload):
    """Validate wire data before any tracker state changes; labels are absent."""
    if len(payload) > 4096:
        raise ValueError('Message too large')
    data = json.loads(payload)
    if not isinstance(data, dict) or data.get('version') != 1:
        raise ValueError('Expected version 1 object')
    for key in ('session', 'source'):
        if not isinstance(data.get(key), str) or not 1 <= len(data[key]) <= 128:
            raise ValueError(f'Invalid {key}')
    if data.get('type') not in ('sample', 'end'):
        raise ValueError('Unknown message type')
    if type(data.get('seq')) is not int or data['seq'] < 0:
        raise ValueError('Invalid sequence number')
    if data['type'] == 'sample':
        if type(data.get('t_us')) is not int or data['t_us'] < 0:
            raise ValueError('Invalid timestamp')
        for key in CHANNELS:
            value = data.get(key)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f'Invalid {key}')
    return data


class Receiver:
    """Single-session receiver. Ignore duplicates; abort on loss/reordering."""
    def __init__(self, emit=print):
        self.session = None
        self.source = None
        self.expected = 0
        self.last_time = None
        self.first_time = None
        self.tracker = WorkoutTracker()
        self.reporter = EventReporter(emit)
        self.emit = emit

    def accept(self, data):
        if self.session is None:
            if data['type'] != 'sample' or data['seq'] != 0:
                raise ValueError('Missed session start; restart subscriber before publisher')
            self.session, self.source = data['session'], data['source']
            self.emit(f"Session {self.session} | source: {self.source}")
        if data['session'] != self.session or data['source'] != self.source:
            raise ValueError('Another session/source arrived; use one publisher')
        if data['seq'] < self.expected:
            return False  # QoS 1 can redeliver a sample.
        if data['seq'] != self.expected:
            raise ValueError(f"Missing/out-of-order sample: expected {self.expected}, got {data['seq']}")
        if data['type'] == 'end':
            completed = sum(r['status'] == 'complete' for r in self.tracker.sets)
            reps = sum(r['reps'] for r in self.tracker.sets) + (self.tracker.active['reps'] if self.tracker.active else 0)
            self.emit(f'Received {self.expected} samples | {completed} completed sets | {reps} detected reps')
            if self.tracker.active:
                self.emit('Final set remains active; end of stream does not complete it.')
            return True
        timestamp = data['t_us']
        if self.last_time is not None and timestamp <= self.last_time:
            raise ValueError('Timestamp is not increasing')
        if self.first_time is None:
            self.first_time = timestamp
        row = self.tracker.update((timestamp-self.first_time)/1e6,
                                  data['gx_dps'], data['gy_dps'], data['gz_dps'])
        self.last_time = timestamp
        self.expected += 1
        self.reporter.update(row, self.tracker)
        return False


def connect(args, subscribe=False):
    import paho.mqtt.client as mqtt
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id='workout-' + uuid.uuid4().hex[:12], reconnect_on_failure=False)
    ready = threading.Event()
    failed = threading.Event()
    inbox = queue.Queue(maxsize=10000)

    def on_connect(c, userdata, flags, reason, properties):
        if reason.is_failure:
            failed.set()
        elif subscribe:
            c.subscribe(args.topic, qos=1)
        else:
            ready.set()

    def on_subscribe(c, userdata, mid, reasons, properties):
        if not reasons or any(r.is_failure for r in reasons):
            failed.set()
        else:
            ready.set()

    def on_message(c, userdata, message):
        if message.retain:
            return  # Old retained measurements must not become a new workout.
        try:
            inbox.put_nowait(message.payload)
        except queue.Full:
            failed.set()

    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message
    client.on_disconnect = lambda c, u, f, r, p: failed.set()
    try:
        client.connect(args.host, args.port, keepalive=15)
        client.loop_start()
        deadline = time.monotonic() + 5
        while not ready.wait(0.05):
            if failed.is_set() or time.monotonic() > deadline:
                raise RuntimeError('Broker connection/subscription failed or timed out')
    except Exception:
        client.disconnect()
        client.loop_stop()
        raise
    return client, failed, inbox


def publish(args):
    times, signals, sources, _ = load_samples(args.input)
    if len(sources) != 1:
        raise ValueError('CSV must have one source')
    client, failed, _ = connect(args)
    session = uuid.uuid4().hex
    base = dict(version=1, session=session, source=next(iter(sources)))
    def send(data):
        if failed.is_set():
            raise RuntimeError('MQTT disconnected; replay aborted, restart both processes')
        info = client.publish(args.topic, json.dumps(data, allow_nan=False), qos=1, retain=False)
        info.wait_for_publish(timeout=5)
        if not info.is_published():
            raise RuntimeError('Broker acknowledgement timed out')
    try:
        print(f'Publishing {len(times)} samples | {args.speed:g}x | session {session}', flush=True)
        for i, sample in enumerate(paced_samples(times, signals, args.speed)):
            data = dict(base, type='sample', seq=i, t_us=round(sample[0]*1e6))
            data.update({key: signals[key][i] for key in CHANNELS})
            send(data)
        send(dict(base, type='end', seq=len(times)))
        print(f'Broker acknowledged {len(times)} samples and end marker. Check subscriber totals.')
    finally:
        client.disconnect()
        client.loop_stop()


def subscribe(args):
    client, failed, inbox = connect(args, subscribe=True)
    receiver = Receiver(lambda message: print(message, flush=True))
    print(f'READY: subscribed to {args.topic}; start publisher now. Ctrl+C exits.', flush=True)
    last_arrival = None
    try:
        while True:
            if failed.is_set():
                raise RuntimeError('MQTT disconnected or receive queue overflowed; restart both processes')
            try:
                payload = inbox.get(timeout=0.2)
            except queue.Empty:
                if last_arrival is not None and time.monotonic()-last_arrival > 5:
                    raise RuntimeError('No samples for 5 seconds; stream interrupted, not rest')
                continue
            last_arrival = time.monotonic()
            if receiver.accept(decode(payload)):
                break
    finally:
        client.disconnect()
        client.loop_stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('publish', 'subscribe'))
    parser.add_argument('--input', type=Path)
    parser.add_argument('--speed', type=float, default=1)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=1883)
    parser.add_argument('--topic', default=TOPIC)
    args = parser.parse_args()
    if not math.isfinite(args.speed) or args.speed <= 0:
        parser.error('--speed must be finite and positive')
    if args.mode == 'publish' and args.input is None:
        parser.error('publish requires --input CSV_PATH')
    if not args.topic or any(c in args.topic for c in '+#\x00'):
        parser.error('Use one concrete MQTT topic without wildcards')
    try:
        (publish if args.mode == 'publish' else subscribe)(args)
    except KeyboardInterrupt:
        print('\nStopped; no set completion inferred.')
        return 130
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        parser.exit(1, f'MQTT error: {exc}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
