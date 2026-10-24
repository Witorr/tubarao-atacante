import unittest
from unittest.mock import Mock
import x11_protocol as q

class QueryTests(unittest.TestCase):
    def test_confirmed_query_sequence(self):
        def ioctl(fd, request, buf, mutate):
            if request == 0xC0084806:
                self.assertEqual(bytes(buf), bytes.fromhex('a0 06 09 00 01 00 00 00'))
            elif request == 0xC0084807:
                buf[:] = bytes.fromhex('a0 01 00 00 00 00 00 00')
            elif request == 0xC0094807:
                buf[:] = bytes.fromhex('06 09 01 08 f7 00 00 00 00')
            else:
                self.fail('Unexpected ioctl')
            return len(buf)
        trace = []
        result = q.query_polling(123, trace, ioctl_fn=ioctl, sleep_fn=lambda _: None)
        self.assertEqual(result['polling_hz_candidate'], 125)
        self.assertTrue(result['complement_checksum_matches'])
        self.assertEqual([x['operation'] for x in trace], ['prepare_query','get_feature','get_feature'])
    def test_unconfirmed_query_stops_before_polling(self):
        calls = []
        def ioctl(fd, request, buf, mutate):
            calls.append(request)
            if request == 0xC0084807:
                buf[:] = bytes.fromhex('a0 00 00 00 00 00 00 00')
            return len(buf)
        with self.assertRaises(ValueError):
            q.query_polling(123, [], ioctl_fn=ioctl, sleep_fn=lambda _: None)
        self.assertNotIn(0xC0094807, calls)
    def test_short_transfer_rejected(self):
        with self.assertRaises(ValueError):
            q.query_polling(123, [], ioctl_fn=lambda *args: 0, sleep_fn=lambda _: None)
    def test_descriptor_accumulates_fields(self):
        self.assertEqual(q.feature_lengths(bytes.fromhex('85 a0 75 08 95 03 b1 02 95 04 b1 02 85 06 95 08 b1 02')), {160: 8, 6: 9})
    def test_descriptor_push_pop(self):
        self.assertEqual(q.feature_lengths(bytes.fromhex('85 a0 75 08 95 07 a4 85 06 95 08 b1 02 b4 b1 02')), {6: 9,160:8})
    def test_bad_descriptors(self):
        for blob in [bytes.fromhex('76 01'),bytes.fromhex('fe 03'),bytes.fromhex('b4'),bytes.fromhex('85 00')]:
            with self.subTest(blob=blob), self.assertRaises(ValueError):
                q.feature_lengths(blob)
    def test_wrong_node_rejected(self):
        for path in ['/dev/input/event0','/dev/sda','/tmp/hidraw2']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                q.inspect_node(path)

class ConfigurationTests(unittest.TestCase):
    def test_configuration_query_has_only_prepare_write(self):
        requests = []
        sample = bytearray(56)
        sample[:3] = bytes.fromhex('04 38 01')
        sample[5] = 0x3f
        sample[49] = 2
        sample[50:52] = bytes.fromhex('00 41')
        def ioctl(fd, request, buf, mutate):
            requests.append(request)
            if request == 0xC0084806:
                self.assertEqual(bytes(buf), bytes.fromhex('a0 04 38 00 01 00 00 00'))
            elif request == 0xC0084807:
                buf[:] = bytes.fromhex('a0 01 00 00 00 00 00 00')
            elif request == 0xC0384807:
                buf[:] = sample
            else:
                self.fail('Unexpected ioctl')
            return len(buf)
        result = q.query_feature(123, [], 4, 56, ioctl, lambda _: None)
        decoded = q.inspect_configuration(result)
        self.assertTrue(decoded['checksum_matches'])
        self.assertEqual(decoded['enabled_stage_slots'], [1,2,3,4,5,6])
        self.assertEqual(requests, [0xC0084806,0xC0084807,0xC0384807])
    def test_configuration_corruption_is_reported(self):
        frame = bytearray(56)
        frame[:3] = bytes.fromhex('04 38 01')
        frame[5] = 1
        self.assertFalse(q.inspect_configuration(frame)['checksum_matches'])
    def test_unsupported_report_rejected_before_io(self):
        ioctl = Mock()
        with self.assertRaises(ValueError):
            q.query_feature(123, [], 9, 64, ioctl, lambda _: None)
        ioctl.assert_not_called()

class DpiDecodeTests(unittest.TestCase):
    def test_received_user_packet(self):
        raw=bytes.fromhex('04 38 01 00 01 3f 20 20 3d 58 5e 8d d3 81 01 01 00 00 00 00 00 01 00 00 01 ff 00 00 00 ff 00 00 00 ff ff ff 00 00 ff ff ff 00 ff ff 40 00 ff ff ff 02 10 8d 00 00 00 00')
        r=q.inspect_configuration(raw)
        self.assertTrue(r['checksum_matches'])
        self.assertEqual(r['checksum_stored'], 0x108d)
        self.assertEqual([x['dpi_candidate'] for x in r['stages'] if x['enabled']], [2600,3750,4000,6000,9000,22000])
        self.assertEqual(r['active_stage_candidate'], 1)
        self.assertNotIn('y_stage_codes',r)
    def test_same_code_needs_range_markers(self):
        self.assertEqual(q.decode_dpi_candidates(0x81,0,False,False),[5500])
        self.assertEqual(q.decode_dpi_candidates(0x81,1,False,False),[11000])
        self.assertEqual(q.decode_dpi_candidates(0x81,1,True,True),[22000])
    def test_nonunique_encoding_is_preserved(self):
        self.assertEqual(q.decode_dpi_candidates(0x76,1,True,True),[20200,20300])
    def test_unknown_and_inconsistent_encodings(self):
        self.assertEqual(q.decode_dpi_candidates(0x07,0,False,False),[])
        self.assertEqual(q.decode_dpi_candidates(0x81,0,True,False),[])
    def test_checksum_failure_stops_semantic_decode(self):
        frame=bytearray(56);frame[:3]=bytes.fromhex('04 38 01');frame[5]=1
        self.assertNotIn('stages',q.inspect_configuration(frame))

if __name__ == '__main__':
    unittest.main()
