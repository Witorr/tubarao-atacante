#!/usr/bin/env python3
"""Attack Shark X11 configuration/polling query, for CachyOS/Arch Linux.

Python standard library only. Discovers the receiver by sysfs metadata and
Feature Report sizes; verifies the opened fd with HIDIOCGRAWINFO.
Sends only query preparation A0, then GET_FEATURE A0 and 04 (or 06).
No setting-change, profile-write, macro-write or firmware commands are provided.
Protocol evidence: installed AttackShark.exe, Ghidra FUN_004a3f50/004a38a0.
Linux API: https://docs.kernel.org/hid/hidraw.html
Polling query has been exercised by the user; configuration query is experimental.
"""
import argparse
import fcntl
import json
import os
import pathlib
import platform
import re
import stat
import struct
import sys
import time

VID, PID = 0x1D57, 0xFA60
PREPARE = bytes.fromhex('a0 06 09 00 01 00 00 00')
RATES = {8: 125, 4: 250, 2: 500, 1: 1000}

# DPI mapping data adapted from OpenSharkX11 (MIT), source blob 33977f277f71fff531c5714e39753bb1d3249315.
# https://github.com/clevim/OpenSharkX11/blob/main/src-tauri/src/protocols/dpi.rs
# MIT License
# 
# Copyright (c) 2026 Clevs
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
_DPI_TABLE = (
    (50, 0x1), (100, 0x2), (150, 0x3), (200, 0x4), (250, 0x5), (300, 0x6),
    (350, 0x8), (400, 0x9), (450, 0xa), (500, 0xb), (550, 0xc), (600, 0xe),
    (650, 0xf), (700, 0x10), (750, 0x11), (800, 0x12), (850, 0x13), (900, 0x15),
    (950, 0x16), (1000, 0x17), (1050, 0x18), (1100, 0x19), (1150, 0x1b), (1200, 0x1c),
    (1250, 0x1d), (1300, 0x1e), (1350, 0x1f), (1400, 0x20), (1450, 0x22), (1500, 0x23),
    (1550, 0x24), (1600, 0x25), (1650, 0x26), (1700, 0x27), (1750, 0x29), (1800, 0x2a),
    (1850, 0x2b), (1900, 0x2c), (1950, 0x2d), (2000, 0x2f), (2050, 0x30), (2100, 0x31),
    (2150, 0x32), (2200, 0x33), (2250, 0x34), (2300, 0x36), (2350, 0x37), (2400, 0x38),
    (2450, 0x39), (2500, 0x3a), (2550, 0x3b), (2600, 0x3d), (2650, 0x3e), (2700, 0x3f),
    (2750, 0x40), (2800, 0x41), (2850, 0x43), (2900, 0x44), (2950, 0x45), (3000, 0x46),
    (3050, 0x47), (3100, 0x48), (3150, 0x4a), (3200, 0x4b), (3250, 0x4c), (3300, 0x4d),
    (3350, 0x4e), (3400, 0x4f), (3450, 0x51), (3500, 0x52), (3550, 0x53), (3600, 0x54),
    (3650, 0x55), (3700, 0x57), (3750, 0x58), (3800, 0x59), (3850, 0x5a), (3900, 0x5b),
    (3950, 0x5c), (4000, 0x5e), (4050, 0x5f), (4100, 0x60), (4150, 0x61), (4200, 0x62),
    (4250, 0x63), (4300, 0x65), (4350, 0x66), (4400, 0x67), (4450, 0x68), (4500, 0x69),
    (4550, 0x6b), (4600, 0x6c), (4650, 0x6d), (4700, 0x6e), (4750, 0x6f), (4800, 0x70),
    (4850, 0x72), (4900, 0x73), (4950, 0x74), (5000, 0x75), (5050, 0x76), (5100, 0x77),
    (5150, 0x79), (5200, 0x7a), (5250, 0x7b), (5300, 0x7c), (5350, 0x7d), (5400, 0x7f),
    (5450, 0x80), (5500, 0x81), (5550, 0x82), (5600, 0x83), (5650, 0x84), (5700, 0x86),
    (5750, 0x87), (5800, 0x88), (5850, 0x89), (5900, 0x8a), (5950, 0x8b), (6000, 0x8d),
    (6050, 0x8e), (6100, 0x8f), (6150, 0x90), (6200, 0x91), (6250, 0x93), (6300, 0x94),
    (6350, 0x95), (6400, 0x96), (6450, 0x97), (6500, 0x98), (6550, 0x9a), (6600, 0x9b),
    (6650, 0x9c), (6700, 0x9d), (6750, 0x9e), (6800, 0x9f), (6850, 0xa1), (6900, 0xa2),
    (6950, 0xa3), (7000, 0xa4), (7050, 0xa5), (7100, 0xa7), (7150, 0xa8), (7200, 0xa9),
    (7250, 0xaa), (7300, 0xab), (7350, 0xac), (7400, 0xae), (7450, 0xaf), (7500, 0xb0),
    (7550, 0xb1), (7600, 0xb2), (7650, 0xb3), (7700, 0xb5), (7750, 0xb6), (7800, 0xb7),
    (7850, 0xb8), (7900, 0xb9), (7950, 0xbb), (8000, 0xbc), (8050, 0xbd), (8100, 0xbe),
    (8150, 0xbf), (8200, 0xc0), (8250, 0xc2), (8300, 0xc3), (8350, 0xc4), (8400, 0xc5),
    (8450, 0xc6), (8500, 0xc7), (8550, 0xc9), (8600, 0xca), (8650, 0xcb), (8700, 0xcc),
    (8750, 0xcd), (8800, 0xcf), (8850, 0xd0), (8900, 0xd1), (8950, 0xd2), (9000, 0xd3),
    (9050, 0xd4), (9100, 0xd6), (9150, 0xd7), (9200, 0xd8), (9250, 0xd9), (9300, 0xda),
    (9350, 0xdb), (9400, 0xdd), (9450, 0xde), (9500, 0xdf), (9550, 0xe0), (9600, 0xe1),
    (9650, 0xe3), (9700, 0xe4), (9750, 0xe5), (9800, 0xe6), (9850, 0xe7), (9900, 0xe8),
    (9950, 0xea), (10000, 0xeb), (10100, 0x76), (10200, 0x77), (10300, 0x79), (10400, 0x7a),
    (10500, 0x7b), (10600, 0x7c), (10700, 0x7d), (10800, 0x7f), (10900, 0x80), (11000, 0x81),
    (11100, 0x82), (11200, 0x83), (11300, 0x84), (11400, 0x86), (11500, 0x87), (11600, 0x88),
    (11700, 0x89), (11800, 0x8a), (11900, 0x8b), (12000, 0x8d), (12100, 0x8e), (12200, 0x8f),
    (12300, 0x90), (12400, 0x91), (12500, 0x93), (12600, 0x94), (12700, 0x95), (12800, 0x96),
    (12900, 0x97), (13000, 0x98), (13100, 0x9a), (13200, 0x9b), (13300, 0x9c), (13400, 0x9d),
    (13500, 0x9e), (13600, 0x9f), (13700, 0xa1), (13800, 0xa2), (13900, 0xa3), (14000, 0xa4),
    (14100, 0xa5), (14200, 0xa7), (14300, 0xa8), (14400, 0xa9), (14500, 0xaa), (14600, 0xab),
    (14700, 0xac), (14800, 0xae), (14900, 0xaf), (15000, 0xb0), (15100, 0xb1), (15200, 0xb2),
    (15300, 0xb3), (15400, 0xb5), (15500, 0xb6), (15600, 0xb7), (15700, 0xb8), (15800, 0xb9),
    (15900, 0xbb), (16000, 0xbc), (16100, 0xbd), (16200, 0xbe), (16300, 0xbf), (16400, 0xc0),
    (16500, 0xc2), (16600, 0xc3), (16700, 0xc4), (16800, 0xc5), (16900, 0xc6), (17000, 0xc7),
    (17100, 0xc9), (17200, 0xca), (17300, 0xcb), (17400, 0xcc), (17500, 0xcd), (17600, 0xcf),
    (17700, 0xd0), (17800, 0xd1), (17900, 0xd2), (18000, 0xd3), (18100, 0xd4), (18200, 0xd6),
    (18300, 0xd7), (18400, 0xd8), (18500, 0xd9), (18600, 0xda), (18700, 0xdb), (18800, 0xdd),
    (18900, 0xde), (19000, 0xdf), (19100, 0xe0), (19200, 0xe1), (19300, 0xe3), (19400, 0xe4),
    (19500, 0xe5), (19600, 0xe6), (19700, 0xe7), (19800, 0xe8), (19900, 0xea), (20000, 0xeb),
    (20100, 0xeb), (20200, 0x76), (20300, 0x76), (20400, 0x77), (20500, 0x77), (20600, 0x79),
    (20700, 0x79), (20800, 0x7a), (20900, 0x7a), (21000, 0x7b), (21100, 0x7b), (21200, 0x7c),
    (21300, 0x7c), (21400, 0x7d), (21500, 0x7d), (21600, 0x7f), (21700, 0x7f), (21800, 0x80),
    (21900, 0x80), (22000, 0x81),
)



def ioc(direction, number, length):
    # Linux asm-generic/x86 UAPI; main rejects architectures with another ABI.
    return (direction << 30) | (length << 16) | (ord('H') << 8) | number


def feature_lengths(blob):
    state = {'id': 0, 'size': 0, 'count': 0}
    stack, bits = [], {}
    i = 0
    while i < len(blob):
        prefix = blob[i]
        i += 1
        if prefix == 0xFE:
            if i + 2 > len(blob):
                raise ValueError('Descritor HID truncado (long item).')
            length = blob[i]
            i += 2
            if i + length > len(blob):
                raise ValueError('Descritor HID truncado (long payload).')
            i += length
            continue
        size = (0, 1, 2, 4)[prefix & 3]
        if i + size > len(blob):
            raise ValueError('Descritor HID truncado (short item).')
        value = int.from_bytes(blob[i:i + size], 'little')
        i += size
        kind, tag = (prefix >> 2) & 3, prefix >> 4
        if kind == 1:
            if tag in (7, 8, 9):
                if tag == 8 and not 1 <= value <= 255:
                    raise ValueError('Report ID invalido.')
                state[{7: 'size', 8: 'id', 9: 'count'}[tag]] = value
            elif tag == 10:
                stack.append(state.copy())
            elif tag == 11:
                if not stack:
                    raise ValueError('Descritor HID: POP sem PUSH.')
                state = stack.pop()
        elif kind == 0 and tag == 11:
            rid = state['id']
            bits[rid] = bits.get(rid, 0) + state['size'] * state['count']
    return {rid: (count + 7) // 8 + 1 for rid, count in bits.items()}


def inspect_node(node, sysfs=pathlib.Path('/sys/class/hidraw')):
    if not re.fullmatch(r'/dev/hidraw\d+', str(node)):
        raise ValueError('Use um caminho /dev/hidrawN.')
    device = sysfs / pathlib.Path(node).name / 'device'
    metadata = dict(line.split('=', 1) for line in
                    (device / 'uevent').read_text().splitlines() if '=' in line)
    parts = metadata.get('HID_ID', '').split(':')
    if len(parts) != 3 or tuple(int(v, 16) for v in parts) != (3, VID, PID):
        raise ValueError('Interface nao corresponde ao receptor USB 1D57:FA60.')
    lengths = feature_lengths((device / 'report_descriptor').read_bytes())
    if lengths.get(0xA0) != 8 or lengths.get(6) != 9 or lengths.get(4) != 56:
        raise ValueError('Esta interface nao anuncia Feature A0/8, 06/9 e 04/56.')
    return {'node': str(node), 'vid_pid': '1d57:fa60',
            'name': metadata.get('HID_NAME'), 'feature_lengths': lengths}


def discover():
    candidates = []
    for entry in sorted(pathlib.Path('/sys/class/hidraw').glob('hidraw*')):
        try:
            candidates.append(inspect_node('/dev/' + entry.name))
        except (OSError, ValueError):
            continue
    if len(candidates) != 1:
        raise ValueError('Esperada uma interface de configuracao; encontradas %d. '
                         'Informe --device /dev/hidrawN se necessario.' % len(candidates))
    return candidates[0]


def verify_open_fd(fd):
    if not stat.S_ISCHR(os.fstat(fd).st_mode):
        raise ValueError('O caminho aberto nao e um dispositivo de caracteres.')
    info = bytearray(8)
    received = fcntl.ioctl(fd, ioc(2, 3, 8), info, True)
    if received != 0:
        raise ValueError('HIDIOCGRAWINFO retornou valor inesperado.')
    bus, vendor, product = struct.unpack('=Ihh', info)
    if (bus, vendor & 0xFFFF, product & 0xFFFF) != (3, VID, PID):
        raise ValueError('O dispositivo aberto nao corresponde ao receptor esperado.')


def query_feature(fd, trace, report_id, length, ioctl_fn=fcntl.ioctl, sleep_fn=time.sleep):
    if (report_id, length) not in ((6, 9), (4, 56), (5, 15)):
        raise ValueError('Somente consultas de polling, configuracao e iluminacao sao suportadas.')
    prepare = bytes([0xA0, report_id, length, 0, 1, 0, 0, 0])
    frame = bytearray(prepare)
    sent = ioctl_fn(fd, ioc(3, 6, len(frame)), frame, True)
    trace.append({'operation': 'prepare_query', 'hex': prepare.hex(' '),
                  'bytes_returned': sent})
    if sent != len(frame):
        raise ValueError('Preparacao da consulta retornou tamanho inesperado.')
    sleep_fn(0.5)

    def get_report(rid, length):
        buf = bytearray(length)
        buf[0] = rid
        received = ioctl_fn(fd, ioc(3, 7, length), buf, True)
        trace.append({'operation': 'get_feature', 'report_id': rid,
                      'bytes_returned': received, 'hex': bytes(buf).hex(' ')})
        if received != length or buf[0] != rid:
            raise ValueError('Report %02x com tamanho ou identificador inesperado.' % rid)
        return bytes(buf)

    ack = get_report(0xA0, 8)
    if ack[1] != 1:
        raise ValueError('Preparacao nao confirmada: byte 1 do report A0 diferente de 01.')
    sleep_fn(0.1)
    return get_report(report_id, length)


def query_polling(fd, trace, ioctl_fn=fcntl.ioctl, sleep_fn=time.sleep):
    report = query_feature(fd, trace, 6, 9, ioctl_fn, sleep_fn)
    if report[:2] != bytes([6, 9]) or report[3] not in RATES:
        raise ValueError('Resposta de polling ainda nao reconhecida; consulte trace.')
    checksum_ok = report[4] == (report[3] ^ 0xFF)
    # Keep a valid polling field separate from checksum validation of GET responses.
    return {'polling_hz_candidate': RATES[report[3]], 'value_byte': report[3],
            'complement_checksum_matches': checksum_ok,
            'physical_validation': 'pending_user_comparison',
            'raw_hex': report.hex(' ')}


def decode_dpi_candidates(code, range_flag, mask_a, mask_b):
    """Reverse only matching table entries; preserve non-unique encodings."""
    if range_flag not in (0, 1) or mask_a != mask_b:
        return []
    if not mask_a:
        lower, upper = (50, 10000) if range_flag == 0 else (10100, 12000)
    else:
        lower, upper = (12100, 20000) if range_flag == 0 else (20100, 22000)
    return [dpi for dpi, encoded in _DPI_TABLE
            if lower <= dpi <= upper and encoded == code]


def inspect_configuration(report):
    if len(report) != 56 or report[:3] != bytes.fromhex('04 38 01'):
        raise ValueError('Cabecalho de configuracao nao reconhecido; consulte trace.')
    stored = int.from_bytes(report[50:52], 'big')
    calculated = sum(report[3:50]) & 0xFFFF
    summary = {
        'length': len(report),
        'enabled_stage_mask': report[5],
        'enabled_stage_slots': [i + 1 for i in range(8) if report[5] & (1 << i)],
        'dpi_range_mask_a': report[6],
        'dpi_range_mask_b': report[7],
        'dpi_stage_codes': list(report[8:16]),
        'dpi_range_flags': list(report[16:24]),
        'raw_byte_3': report[3], 'raw_byte_4': report[4],
        'raw_byte_24': report[24], 'raw_byte_49': report[49],
        'color_triplets_wire_order': [list(report[i:i + 3]) for i in range(25, 49, 3)],
        'checksum_stored': stored, 'checksum_calculated': calculated,
        'checksum_matches': stored == calculated,
        'trailer_hex': report[52:56].hex(' '),
        'physical_validation': 'pending_user_comparison',
        'note': 'DPI mapping cross-checked against OpenSharkX11; confirm against vendor settings. No X/Y split is inferred.',
        'raw_hex': report.hex(' '),
    }
    if stored != calculated:
        summary['decode_status'] = 'checksum_mismatch_no_semantic_decode'
        return summary
    stages = []
    for i in range(8):
        candidates = decode_dpi_candidates(
            report[8 + i], report[16 + i],
            bool(report[6] & (1 << i)), bool(report[7] & (1 << i)))
        stages.append({'slot': i + 1, 'enabled': bool(report[5] & (1 << i)),
                       'code': report[8 + i], 'range_flag': report[16 + i],
                       'dpi_candidate': candidates[0] if len(candidates) == 1 else None,
                       'dpi_candidates': candidates,
                       'rgb_candidate': list(report[25 + i * 3:28 + i * 3])})
    summary.update(
        decode_status='candidate', stages=stages,
        active_stage_candidate=report[24] if 1 <= report[24] <= 8 else None,
        angle_snap_candidate=bool(report[3]) if report[3] in (0, 1) else None,
        ripple_control_candidate=bool(report[4]) if report[4] in (0, 1) else None)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', help='Opcional: /dev/hidrawN; default: autodeteccao.')
    parser.add_argument('--query', choices=('configuration', 'polling'), default='configuration')
    args = parser.parse_args()
    result = {'operation': 'query_' + args.query, 'status': 'error', 'trace': []}
    try:
        if sys.platform != 'linux' or platform.machine().lower() not in (
                'x86_64', 'amd64', 'aarch64', 'i386', 'i686'):
            raise ValueError('Este script requer Linux com ABI ioctl x86/asm-generic.')
        info = inspect_node(args.device) if args.device else discover()
        result['device'] = info
        fd = os.open(info['node'], os.O_RDWR | os.O_CLOEXEC | os.O_NONBLOCK)
        try:
            verify_open_fd(fd)
            if args.query == 'polling':
                result['response'] = query_polling(fd, result['trace'])
            else:
                raw = query_feature(fd, result['trace'], 4, 56)
                result['response'] = inspect_configuration(raw)
        finally:
            os.close(fd)
        result['status'] = 'received_candidate'
    except PermissionError as exc:
        result['error'] = str(exc)
        result['next_step'] = 'Envie este JSON para ajustar permissoes udev no CachyOS.'
    except (OSError, ValueError) as exc:
        result['error'] = str(exc)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'received_candidate' else 1


if __name__ == '__main__':
    raise SystemExit(main())
