import contextlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import attack_shark_x11 as app

PROFILE = bytes.fromhex('04 38 01 00 01 3f 20 20 3d 58 5e 8d d3 81 01 01 '
                        '00 00 00 00 00 01 00 00 01 ff 00 00 00 ff 00 00 '
                        '00 ff ff ff 00 00 ff ff ff 00 ff ff 40 00 ff ff '
                        'ff 02 10 8d 00 00 00 00')
POLLING = bytes.fromhex('06 09 01 01 fe 00 00 00 00')


class CodecTests(unittest.TestCase):
    def test_received_profile_decodes_to_confirmed_values(self):
        result = app.validate_profile(PROFILE)
        self.assertEqual([s['dpi_candidate'] for s in result['stages'][:6]],
                         [2600, 3750, 4000, 6000, 9000, 22000])

    def test_unchanged_profile_round_trip(self):
        result = app.patch_profile(PROFILE, stage=1,
            dpis=dict(enumerate([2600,3750,4000,6000,9000,22000], 1)),
            colors=dict(enumerate(['ff0000','00ff00','0000ff','ffff00','00ffff','ff00ff'], 1)))
        self.assertEqual(result, PROFILE)

    def test_stage_change_preserves_other_settings(self):
        result = app.patch_profile(PROFILE, stage=2)
        self.assertEqual(result[24], 2)
        self.assertEqual([i for i,(a,b) in enumerate(zip(PROFILE,result)) if a != b], [24,51])
        self.assertTrue(app.validate_profile(result)['checksum_matches'])

    def test_high_to_low_dpi_updates_both_masks_and_flag(self):
        result = app.patch_profile(PROFILE, dpis={6:800})
        self.assertEqual(result[13], 0x12)
        self.assertEqual(result[21], 0)
        self.assertEqual(result[6:8], b'\0\0')
        self.assertEqual(app.validate_profile(result)['stages'][5]['dpi_candidate'], 800)
        self.assertTrue(set(i for i,(a,b) in enumerate(zip(PROFILE,result)) if a != b)
                        <= {6,7,13,21,50,51})

    def test_low_to_high_round_trip(self):
        low = app.patch_profile(PROFILE, dpis={6:800})
        self.assertEqual(app.patch_profile(low, dpis={6:22000}), PROFILE)

    def test_color_preserves_extra_slots_and_other_fields(self):
        result = app.patch_profile(PROFILE, colors={1:'#112233'})
        self.assertEqual(result[25:28], bytes.fromhex('11 22 33'))
        self.assertEqual(result[28:50], PROFILE[28:50])
        self.assertEqual(result[:25], PROFILE[:25])
        self.assertEqual(result[52:], PROFILE[52:])

    def test_invalid_dpi_has_no_approximation(self):
        for dpi in [0,51,20200,30000,True,800.0]:
            with self.subTest(dpi=dpi), self.assertRaises(ValueError):
                app.patch_profile(PROFILE, dpis={1:dpi})

    def test_invalid_stage(self):
        for stage in [0,7,True,'1']:
            with self.subTest(stage=stage), self.assertRaises(ValueError):
                app.patch_profile(PROFILE, stage=stage)

    def test_disabled_stage_is_not_activated(self):
        frame=bytearray(PROFILE);frame[5]=0x3d
        frame[50:52]=sum(frame[3:50]).to_bytes(2,'big')
        with self.assertRaisesRegex(ValueError,'desabilitado'):
            app.patch_profile(frame, stage=2)

    def test_invalid_colors(self):
        for color in ['red','#fff','11223344','0011gg',None]:
            with self.subTest(color=color), self.assertRaises(ValueError):
                app.patch_profile(PROFILE, colors={1:color})

    def test_corrupt_profile_prevents_modification(self):
        frame=bytearray(PROFILE);frame[10]^=1
        with self.assertRaisesRegex(ValueError,'Checksum'):
            app.patch_profile(frame, stage=2)

    def test_polling_known_vector_and_preservation(self):
        self.assertEqual(app.patch_polling(POLLING,125),bytes.fromhex('06 09 01 08 f7 00 00 00 00'))
        for hz in (125,250,500,1000):
            result=app.patch_polling(POLLING,hz)
            app.validate_polling(result)
            self.assertEqual(result[:3],POLLING[:3])
            self.assertEqual(result[5:],POLLING[5:])

    def test_unsupported_polling(self):
        for hz in (0,126,2000,True):
            with self.subTest(hz=hz),self.assertRaises(ValueError):
                app.patch_polling(POLLING,hz)


class FakeReceiver:
    def __init__(self):
        self.info={'node':'/dev/hidraw2','vid_pid':'1d57:fa60'}
        self.frames={4:PROFILE,6:POLLING}
        self.writes=[]
        self.mismatch=False
        self.fail_readback=False

    def read(self,report):
        if self.writes and self.fail_readback:
            raise OSError('disconnected')
        return self.frames[report]

    def write(self,frame):
        self.writes.append(frame)
        if not self.mismatch:
            self.frames[frame[0]]=frame


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.receiver=FakeReceiver()
        self.backup=Mock(return_value='/private/snapshot.json')
        self.backend=app.X11(session_factory=lambda:contextlib.nullcontext(self.receiver),backup_fn=self.backup)

    def test_status_does_not_write_settings(self):
        result=self.backend.status()
        self.assertEqual(result['polling_hz'],1000)
        self.assertEqual(self.receiver.writes,[])
        self.backup.assert_not_called()

    def test_backup_is_completed_before_write(self):
        def backup(*args):
            self.assertEqual(self.receiver.writes,[])
            self.assertEqual(args[2:],(PROFILE,POLLING))
            return '/private/snapshot.json'
        self.backup.side_effect=backup
        result=self.backend.set_polling(500)
        self.assertEqual(result['status'],'verified')
        self.assertEqual(result['polling_hz'],500)
        self.assertEqual(len(self.receiver.writes),1)

    def test_noop_does_not_write_or_backup(self):
        self.assertEqual(self.backend.set_polling(1000)['status'],'unchanged')
        self.assertEqual(self.receiver.writes,[])
        self.backup.assert_not_called()

    def test_profile_write_verified(self):
        result=self.backend.set_profile(stage=2)
        self.assertEqual(result['status'],'verified')
        self.assertEqual(result['configuration']['active_stage_candidate'],2)

    def test_backup_failure_prevents_setting_write(self):
        self.backup.side_effect=OSError('disk full')
        with self.assertRaises(OSError):self.backend.set_polling(500)
        self.assertEqual(self.receiver.writes,[])

    def test_mismatch_is_reported_without_retry_or_rollback(self):
        self.receiver.mismatch=True
        result=self.backend.set_polling(500)
        self.assertEqual(result['status'],'verification_mismatch')
        self.assertEqual(result['different_offsets'],[3,4])
        self.assertEqual(result['polling_hz'],1000)
        self.assertEqual(len(self.receiver.writes),1)

    def test_readback_failure_retains_backup_location(self):
        self.receiver.fail_readback=True
        with self.assertRaisesRegex(RuntimeError,'/private/snapshot.json'):
            self.backend.set_polling(500)
        self.assertEqual(len(self.receiver.writes),1)

    def test_invalid_value_prevents_write_and_backup(self):
        with self.assertRaises(ValueError):self.backend.set_profile(dpis={1:51})
        self.assertEqual(self.receiver.writes,[])
        self.backup.assert_not_called()


class TransportTests(unittest.TestCase):
    def test_unknown_reports_never_reach_ioctl(self):
        receiver=app.Receiver(123,{})
        with patch.object(app.fcntl,'ioctl') as ioctl:
            for frame in [b'',bytes.fromhex('0b 08 00 00 00 00 00 00')]:
                with self.assertRaises(ValueError):receiver.write(frame)
            ioctl.assert_not_called()

    def test_valid_setting_write_uses_expected_ioctl(self):
        receiver=app.Receiver(123,{})
        with patch.object(app.fcntl,'ioctl',return_value=9) as ioctl,patch.object(app.time,'sleep'):
            receiver.write(POLLING)
            self.assertEqual(ioctl.call_args.args[:2],(123,0xc0094806))
            self.assertEqual(bytes(ioctl.call_args.args[2]),POLLING)

    def test_incomplete_write_fails(self):
        receiver=app.Receiver(123,{})
        with patch.object(app.fcntl,'ioctl',return_value=1),self.assertRaises(OSError):
            receiver.write(POLLING)

    def test_backup_contains_both_frames_and_private_permissions(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'XDG_STATE_HOME':tmp}):
            path=Path(app.save_backup({'node':'test'},'polling',PROFILE,POLLING))
            data=json.loads(path.read_text())
            self.assertEqual(bytes.fromhex(data['configuration_hex']),PROFILE)
            self.assertEqual(bytes.fromhex(data['polling_hex']),POLLING)
            self.assertEqual(path.stat().st_mode & 0o777,0o600)


if __name__=='__main__':
    unittest.main()
