import contextlib
import unittest
from unittest.mock import Mock

import attack_shark_x11 as app
import x11_protocol as proto
from test_x11 import PROFILE, POLLING

# Byte 11/12 is a big-endian sum, as in the installed Windows binary.
LIGHTING = bytes.fromhex('05 0f 01 20 03 a8 11 ff 00 01 04 01 e0 00 00')


class LightingCodecTests(unittest.TestCase):
    def test_follow_stage_preserves_sleep_debounce_rgb_and_padding(self):
        result=app.patch_follow_stage_lighting(LIGHTING)
        self.assertEqual(result[3],0x50)
        self.assertEqual(result[4:11],LIGHTING[4:11])
        self.assertEqual(result[13:],LIGHTING[13:])
        self.assertEqual(result[11:13],bytes.fromhex('02 10'))
        self.assertEqual(app.validate_lighting(result)['mode'],0x50)
        self.assertTrue(set(i for i,(a,b) in enumerate(zip(LIGHTING,result)) if a!=b)<={3,11,12})

    def test_mode_lower_bits_are_preserved(self):
        before=bytearray(LIGHTING);before[3]=0x23
        before[11:13]=sum(before[3:11]).to_bytes(2,'big')
        self.assertEqual(app.patch_follow_stage_lighting(before)[3],0x53)

    def test_unknown_checksum_rejected(self):
        bad=bytearray(LIGHTING);bad[11]=0
        with self.assertRaisesRegex(ValueError,'Checksum'):
            app.patch_follow_stage_lighting(bad)

    def test_wrong_report_rejected(self):
        with self.assertRaises(ValueError):app.patch_follow_stage_lighting(POLLING)

    def test_query_05_uses_only_preparation_write(self):
        requests=[]
        def ioctl(fd,request,buf,mutable):
            requests.append(request)
            if request==0xc0084806:
                self.assertEqual(bytes(buf),bytes.fromhex('a0 05 0f 00 01 00 00 00'))
            elif request==0xc0084807:
                buf[:]=bytes.fromhex('a0 01 00 00 00 00 00 00')
            elif request==0xc00f4807:
                buf[:]=LIGHTING
            else:self.fail('unexpected request')
            return len(buf)
        self.assertEqual(proto.query_feature(123,[],5,15,ioctl,lambda _:None),LIGHTING)
        self.assertEqual(requests,[0xc0084806,0xc0084807,0xc00f4807])


class LightingReceiver:
    def __init__(self):
        self.info={'node':'/dev/hidraw2','vid_pid':'1d57:fa60'}
        self.frames={4:PROFILE,5:LIGHTING,6:POLLING}
        self.writes=[]
        self.reject_05=False
        self.disconnect_on_05=False

    def read(self,rid):
        return self.frames[rid]

    def write(self,frame):
        self.writes.append(frame)
        if frame[0]==5 and self.disconnect_on_05:
            raise OSError('disconnected')
        if frame[0]!=5 or not self.reject_05:
            self.frames[frame[0]]=frame


class LightingTransactionTests(unittest.TestCase):
    def setUp(self):
        self.receiver=LightingReceiver()
        self.backup=Mock(return_value='/private/snapshot.json')
        self.backend=app.X11(session_factory=lambda:contextlib.nullcontext(self.receiver),backup_fn=self.backup)

    def test_enabling_mode_replays_04_then_05_and_keeps_polling(self):
        result=self.backend.set_profile(follow_stage=True)
        self.assertEqual(result['status'],'verified')
        self.assertEqual([f[0] for f in self.receiver.writes],[4,5])
        self.assertEqual(self.receiver.writes[0],PROFILE)
        self.assertEqual(result['polling_hz'],1000)
        self.assertEqual(result['lighting']['mode'],0x50)
        self.assertEqual(self.backup.call_args.args[2:],(PROFILE,POLLING,LIGHTING))

    def test_real_user_color_and_active_stage(self):
        result=self.backend.set_profile(stage=2,colors={2:'#79c400'},follow_stage=True)
        self.assertEqual(result['status'],'verified')
        self.assertEqual(self.receiver.frames[4][24],2)
        self.assertEqual(self.receiver.frames[4][28:31],bytes.fromhex('79 c4 00'))
        self.assertEqual(self.receiver.frames[5][3],0x50)
        self.assertEqual(self.receiver.frames[5][4:11],LIGHTING[4:11])

    def test_checksum_failure_happens_before_profile_or_lighting_write(self):
        self.receiver.frames[5]=bytes(15)
        with self.assertRaises(ValueError):self.backend.set_profile(follow_stage=True)
        self.assertEqual(self.receiver.writes,[])
        self.backup.assert_not_called()

    def test_backup_failure_prevents_both_writes(self):
        self.backup.side_effect=OSError('disk full')
        with self.assertRaises(OSError):self.backend.set_profile(follow_stage=True)
        self.assertEqual(self.receiver.writes,[])

    def test_existing_mode_still_reapplied_after_color_changes(self):
        self.receiver.frames[5]=app.patch_follow_stage_lighting(LIGHTING)
        self.assertEqual(self.backend.set_profile(colors={2:'79c400'},follow_stage=True)['status'],'verified')
        self.assertEqual([f[0] for f in self.receiver.writes],[4,5])

    def test_unchanged_profile_and_mode_do_not_write(self):
        self.receiver.frames[5]=app.patch_follow_stage_lighting(LIGHTING)
        self.assertEqual(self.backend.set_profile(follow_stage=True)['status'],'unchanged')
        self.assertEqual(self.receiver.writes,[])

    def test_mode_readback_mismatch_reported_without_retry(self):
        self.receiver.reject_05=True
        result=self.backend.set_profile(follow_stage=True)
        self.assertEqual(result['status'],'verification_mismatch')
        self.assertEqual(len(self.receiver.writes),2)
        self.assertIn(3,result['different_offsets']['lighting'])

    def test_partial_write_failure_retains_snapshot(self):
        self.receiver.disconnect_on_05=True
        with self.assertRaisesRegex(RuntimeError,'/private/snapshot.json'):
            self.backend.set_profile(follow_stage=True)
        self.assertEqual([f[0] for f in self.receiver.writes],[4,5])


if __name__=='__main__':unittest.main()
