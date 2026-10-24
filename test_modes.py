import contextlib
import unittest
from unittest.mock import Mock

import attack_shark_x11 as app
from test_lighting import LIGHTING, LightingReceiver


class ModeCodecTests(unittest.TestCase):
    def test_all_seven_mode_codes_and_names(self):
        expected={'off':0,'static':16,'breathing':32,'neon':48,'color-breathing':64,
                  'static-dpi':80,'breathing-dpi':96}
        for name,code in expected.items():
            with self.subTest(name=name):
                result=app.patch_lighting(LIGHTING,mode=name)
                self.assertEqual(result[3],code)
                self.assertEqual(result[4:11],LIGHTING[4:11])
                self.assertEqual(app.validate_lighting(result)['mode_key'],name)

    def test_reference_static_green_speed_vector(self):
        result=app.patch_lighting(LIGHTING,mode='static',speed=5,rgb='00ff00')
        self.assertEqual(result,bytes.fromhex('05 0f 01 10 01 a8 00 ff 00 01 04 01 bd 00 00'))

    def test_speed_preserves_deep_sleep_bucket_and_other_fields(self):
        before=bytearray(LIGHTING);before[4]=0xb3
        before[11:13]=sum(before[3:11]).to_bytes(2,'big')
        for speed,wire in [(1,5),(2,4),(3,3),(4,2),(5,1)]:
            result=app.patch_lighting(before,speed=speed)
            self.assertEqual(result[4],0xb0|wire)
            self.assertEqual(result[5:11],before[5:11])
            self.assertEqual(app.validate_lighting(result)['speed'],speed)

    def test_color_changes_only_rgb_and_checksum(self):
        result=app.patch_lighting(LIGHTING,rgb='#8000ff')
        self.assertEqual(result[6:9],bytes.fromhex('80 00 ff'))
        self.assertTrue(set(i for i,(a,b) in enumerate(zip(result,LIGHTING)) if a!=b)<={6,7,8,11,12})

    def test_speed_and_mode_validation(self):
        for value in [0,6,True,2.5,'3']:
            with self.subTest(speed=value),self.assertRaises(ValueError):
                app.patch_lighting(LIGHTING,speed=value)
        with self.assertRaises(ValueError):app.patch_lighting(LIGHTING,mode='pairing')

    def test_untouched_lighting_round_trip(self):
        self.assertEqual(app.patch_lighting(LIGHTING),LIGHTING)

    def test_unknown_speed_is_not_invented(self):
        before=bytearray(LIGHTING);before[4]=0xa9
        before[11:13]=sum(before[3:11]).to_bytes(2,'big')
        self.assertIsNone(app.validate_lighting(before)['speed'])
        result=app.patch_lighting(before,mode='neon')
        self.assertEqual(result[4],0xa9)


class ModeTransactionTests(unittest.TestCase):
    def setUp(self):
        self.receiver=LightingReceiver()
        self.backup=Mock(return_value='/private/snapshot.json')
        self.backend=app.X11(session_factory=lambda:contextlib.nullcontext(self.receiver),backup_fn=self.backup)

    def test_set_breathing_global_color_and_speed(self):
        result=self.backend.set_lighting(mode='breathing',speed=4,rgb='8000ff')
        self.assertEqual(result['status'],'verified')
        self.assertEqual([f[0] for f in self.receiver.writes],[4,5])
        self.assertEqual(self.receiver.frames[5],bytes.fromhex('05 0f 01 20 02 a8 80 00 ff 01 04 02 4e 00 00'))
        self.assertEqual(result['lighting']['speed'],4)
        self.assertEqual(result['lighting']['global_color'],'#8000ff')

    def test_profile_edits_preserve_selected_animation(self):
        self.receiver.frames[5]=app.patch_lighting(LIGHTING,mode='neon',speed=5)
        expected=self.receiver.frames[5]
        result=self.backend.set_profile(stage=2,preserve_lighting=True)
        self.assertEqual(result['status'],'verified')
        self.assertEqual(self.receiver.frames[5],expected)
        self.assertEqual(result['lighting']['mode_key'],'neon')

    def test_full_status_is_queries_only(self):
        result=self.backend.status(include_lighting=True)
        self.assertEqual(result['lighting']['mode_key'],'breathing')
        self.assertEqual(result['lighting']['speed'],3)
        self.assertEqual(self.receiver.writes,[])

    def test_empty_lighting_operation_does_not_open_receiver(self):
        factory=Mock()
        backend=app.X11(session_factory=factory)
        with self.assertRaises(ValueError):backend.set_lighting()
        factory.assert_not_called()

    def test_bad_rgb_or_speed_prevents_any_setting_write(self):
        for changes in ({'rgb':'garbage'},{'speed':6},{'mode':'unknown'}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                self.backend.set_lighting(**changes)
        self.assertEqual(self.receiver.writes,[])
        self.backup.assert_not_called()


if __name__=='__main__':unittest.main()
