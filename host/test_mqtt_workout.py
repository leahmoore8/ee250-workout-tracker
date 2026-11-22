"""MQTT protocol checks. AI assistance: OpenAI Codex."""
import json
import unittest
from mqtt_workout import decode, Receiver
from plot_imu import CHANNELS


def sample(seq=0):
    return dict(version=1, session='test', source='synthetic', type='sample',
                seq=seq, t_us=seq*20000, **{key: 0 for key in CHANNELS})


class MqttTests(unittest.TestCase):
    def test_duplicate_is_not_processed_twice(self):
        r=Receiver(lambda m: None)
        r.accept(decode(json.dumps(sample())))
        r.accept(decode(json.dumps(sample())))
        self.assertEqual(r.expected, 1)

    def test_missing_sample_aborts(self):
        r=Receiver(lambda m: None); r.accept(sample())
        with self.assertRaises(ValueError): r.accept(sample(2))

    def test_restarted_session_rejected(self):
        r=Receiver(lambda m: None); r.accept(sample())
        message=sample(1); message['session']='another'
        with self.assertRaises(ValueError): r.accept(message)

    def test_bad_data_rejected(self):
        for key, value in [('gy_dps', float('nan')), ('t_us', -1), ('seq', True), ('version', 9)]:
            message=sample(); message[key]=value
            with self.assertRaises(ValueError): decode(json.dumps(message))

    def test_end_requires_all_samples(self):
        r=Receiver(lambda m: None); r.accept(sample())
        end=dict(version=1, session='test', source='synthetic', type='end', seq=2)
        with self.assertRaises(ValueError): r.accept(end)
        end['seq']=1
        self.assertTrue(r.accept(end))


if __name__ == '__main__': unittest.main()
