#!/usr/bin/env python3
"""Attack Shark X11 — native Linux prototype for CachyOS/Arch, receiver only.

No arguments: graphical interface (Qt 6). Commands: status, set-polling,
set-stage, set-dpi, set-color. Writes use read/modify/write, a local backup,
and readback verification. No firmware, pairing or macro commands.
Hardware: 1D57:FA60, HID Feature collection with A0/8, 04/56, 06/9.
"""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import time

import x11_protocol as proto

VERSION = '0.7.0'

LIGHTING_MODES = {
    'off': (0x00, 'Desligado', 'LED Off'),
    'static': (0x10, 'Estático', 'Static'),
    'breathing': (0x20, 'Respiração', 'Breathing'),
    'neon': (0x30, 'Neon', 'Neon'),
    'color-breathing': (0x40, 'Respiração multicolor', 'Color Breathing'),
    'static-dpi': (0x50, 'Cor do DPI', 'Static DPI'),
    'breathing-dpi': (0x60, 'Respiração do DPI', 'Breathing DPI'),
}


def validate_profile(frame):
    parsed = proto.inspect_configuration(frame)
    if not parsed['checksum_matches']:
        raise ValueError('Checksum da configuração inválido. Nenhuma gravação realizada.')
    return parsed


def validate_polling(frame):
    if (len(frame) != 9 or frame[:3] != bytes([6, 9, 1])
            or frame[3] not in proto.RATES or frame[4] != (frame[3] ^ 255)):
        raise ValueError('Relatório de polling não reconhecido. Nenhuma gravação realizada.')


def validate_lighting(frame):
    # Installed vendor binary: FUN_004a1d20 stores sum(bytes 3..10) as
    # big-endian uint16 at 11..12. Keep this separate from profile checksum.
    if len(frame) != 15 or frame[:3] != bytes([5, 15, 1]):
        raise ValueError('Relatório 05 não reconhecido: ' + frame.hex(' '))
    expected = sum(frame[3:11]) & 65535
    stored = int.from_bytes(frame[11:13], 'big')
    if stored != expected:
        raise ValueError('Checksum do relatório 05 não corresponde ao software analisado. '
                         'Nenhuma alteração de iluminação enviada. Frame: ' + frame.hex(' '))
    mode = frame[3] & 0xf0
    key = next((key for key, spec in LIGHTING_MODES.items() if spec[0] == mode), None)
    hardware_speed = frame[4] & 0x0f
    return {'mode_byte': frame[3], 'mode': mode, 'mode_key': key,
            'mode_name': LIGHTING_MODES[key][1] if key else 'Modo não reconhecido',
            'speed': 6 - hardware_speed if 1 <= hardware_speed <= 5 else None,
            'hardware_speed': hardware_speed,
            'global_rgb': list(frame[6:9]), 'global_color': '#%02x%02x%02x' % tuple(frame[6:9]),
            'follows_active_stage': (frame[3] & 0xf0) in (0x50, 0x60),
            'checksum_matches': True, 'raw_hex': frame.hex(' ')}


def patch_follow_stage_lighting(before):
    return patch_lighting(before, mode='static-dpi')


def patch_lighting(before, *, mode=None, speed=None, rgb=None):
    validate_lighting(before)
    after = bytearray(before)
    if mode is not None:
        if mode not in LIGHTING_MODES:
            raise ValueError('Modo de iluminação não reconhecido.')
        after[3] = (after[3] & 0x0f) | LIGHTING_MODES[mode][0]
    if speed is not None:
        if isinstance(speed, bool) or not isinstance(speed, int) or not 1 <= speed <= 5:
            raise ValueError('A velocidade deve estar entre 1 e 5.')
        # Upper nibble belongs to deep sleep. Only the lower nibble is speed.
        after[4] = (after[4] & 0xf0) | (6 - speed)
    if rgb is not None:
        after[6:9] = parse_rgb(rgb)
    after[11:13] = sum(after[3:11]).to_bytes(2, 'big')
    return bytes(after)


def stage_index(stage):
    if isinstance(stage, bool) or not isinstance(stage, int) or not 1 <= stage <= 6:
        raise ValueError('O estágio deve estar entre 1 e 6.')
    return stage - 1


def encode_dpi(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError('DPI deve ser um número inteiro.')
    matches = [code for dpi, code in proto._DPI_TABLE if dpi == value]
    if not matches:
        raise ValueError('DPI fora da tabela do dispositivo. Use um valor exato suportado; '
                         'até 10000, os passos são de 50 DPI.')
    code = matches[0]
    high = value > 12000
    flag = int(10100 <= value <= 12000 or 20100 <= value <= 22000)
    if proto.decode_dpi_candidates(code, flag, high, high) != [value]:
        raise ValueError('Esse DPI possui codificação ambígua; escolha outro valor.')
    return code, flag, high


def parse_rgb(value):
    if not isinstance(value, str) or not re.fullmatch(r'#?[0-9a-fA-F]{6}', value):
        raise ValueError('A cor deve estar no formato #RRGGBB.')
    return bytes.fromhex(value.lstrip('#'))


def patch_profile(before, *, stage=None, dpis=None, colors=None):
    validate_profile(before)
    result = bytearray(before)
    if stage is not None:
        index = stage_index(stage)
        if not before[5] & (1 << index):
            raise ValueError('O estágio selecionado está desabilitado no mouse.')
        result[24] = stage
    for number, value in (dpis or {}).items():
        index = stage_index(number)
        if not before[5] & (1 << index):
            raise ValueError('Não é possível editar um estágio desabilitado.')
        code, flag, high = encode_dpi(value)
        result[8 + index] = code
        result[16 + index] = flag
        for offset in (6, 7):
            result[offset] = (result[offset] & ~(1 << index)) | (int(high) << index)
    for number, value in (colors or {}).items():
        index = stage_index(number)
        result[25 + index * 3:28 + index * 3] = parse_rgb(value)
    checksum = sum(result[3:50]) & 65535
    result[50:52] = checksum.to_bytes(2, 'big')
    return bytes(result)


def patch_polling(before, hz):
    validate_polling(before)
    values = {125: 8, 250: 4, 500: 2, 1000: 1}
    if isinstance(hz, bool) or hz not in values:
        raise ValueError('Polling permitido: 125, 250, 500 ou 1000 Hz.')
    result = bytearray(before)
    result[3] = values[hz]
    result[4] = values[hz] ^ 255
    return bytes(result)


def state_directory():
    parent = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')).expanduser()
    folder = parent / 'attack-shark-x11'
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    return folder


class Receiver:
    def __init__(self, fd, info):
        self.fd, self.info, self.trace = fd, info, []

    def read(self, report_id):
        length = {4: 56, 5: 15, 6: 9}[report_id]
        frame = proto.query_feature(self.fd, self.trace, report_id, length)
        if report_id == 4:
            validate_profile(frame)
        elif report_id == 6:
            validate_polling(frame)
        else:
            validate_lighting(frame)
        return frame

    def write(self, frame):
        if not frame:
            raise ValueError('Relatório vazio.')
        if frame[0] == 4:
            validate_profile(frame)
        elif frame[0] == 6:
            validate_polling(frame)
        elif frame[0] == 5:
            validate_lighting(frame)
        else:
            raise ValueError('Somente relatórios 04, 05 e 06 podem ser gravados.')
        sent = fcntl.ioctl(self.fd, proto.ioc(3, 6, len(frame)), bytearray(frame), True)
        self.trace.append({'operation': 'write_setting', 'report_id': frame[0],
                           'hex': frame.hex(' '), 'bytes_returned': sent})
        if sent != len(frame):
            raise OSError('Envio incompleto. A configuração deve ser consultada novamente.')
        time.sleep(0.5)


@contextmanager
def open_receiver(device=None):
    if sys.platform != 'linux' or proto.platform.machine().lower() not in (
            'x86_64', 'amd64', 'aarch64', 'i386', 'i686'):
        raise ValueError('Requer Linux com ABI ioctl x86/asm-generic.')
    lock_path = state_directory() / 'transport.lock'
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    fd = None
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Outra instância está acessando o mouse. Aguarde e tente novamente.')
        info = proto.inspect_node(device) if device else proto.discover()
        fd = os.open(info['node'], os.O_RDWR | os.O_CLOEXEC | os.O_NONBLOCK)
        proto.verify_open_fd(fd)
        yield Receiver(fd, info)
    finally:
        if fd is not None:
            os.close(fd)
        os.close(lock_fd)


def save_backup(info, operation, config, polling, lighting=None):
    path = state_directory() / ('before-%d-%s.json' % (time.time_ns(), operation))
    contents = {'schema': 1, 'version': VERSION, 'operation': operation, 'device': info,
                'configuration_hex': config.hex(' '), 'polling_hex': polling.hex(' ')}
    if lighting is not None:
        contents['lighting_hex'] = lighting.hex(' ')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(contents, stream, indent=2, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    return str(path)


class X11:
    def __init__(self, device=None, session_factory=None, backup_fn=save_backup):
        self.session_factory = session_factory or (lambda: open_receiver(device))
        self.backup_fn = backup_fn

    @staticmethod
    def summarize(receiver, config, polling):
        validate_polling(polling)
        return {'device': receiver.info, 'polling_hz': proto.RATES[polling[3]],
                'configuration': validate_profile(config),
                'configuration_hex': config.hex(' '), 'polling_hex': polling.hex(' ')}

    def status(self, include_lighting=False):
        with self.session_factory() as receiver:
            config, polling = receiver.read(4), receiver.read(6)
            result = {'status': 'read', **self.summarize(receiver, config, polling)}
            if include_lighting:
                result['lighting'] = validate_lighting(receiver.read(5))
            return result

    def _change(self, operation, report_id, patch):
        with self.session_factory() as receiver:
            config, polling = receiver.read(4), receiver.read(6)
            before = config if report_id == 4 else polling
            after = patch(before)
            if after == before:
                return {'status': 'unchanged', **self.summarize(receiver, config, polling)}
            backup = self.backup_fn(receiver.info, operation, config, polling)
            try:
                receiver.write(after)
                readback = receiver.read(report_id)
                config = readback if report_id == 4 else config
                polling = readback if report_id == 6 else polling
                differences = [i for i, (a, b) in enumerate(zip(after, readback)) if a != b]
                if len(after) != len(readback):
                    differences.append('length')
                return {'status': 'verified' if not differences else 'verification_mismatch',
                        'operation': operation, 'backup': backup,
                        'expected_hex': after.hex(' '), 'actual_hex': readback.hex(' '),
                        'different_offsets': differences,
                        **self.summarize(receiver, config, polling)}
            except (OSError, ValueError) as exc:
                raise RuntimeError('A gravação foi tentada, mas a verificação falhou. '
                                   'Consulte novamente antes de repetir. Backup: %s. Detalhe: %s'
                                   % (backup, exc)) from exc

    def set_polling(self, hz):
        return self._change('polling', 6, lambda before: patch_polling(before, hz))

    def lighting_status(self):
        with self.session_factory() as receiver:
            lighting = receiver.read(5)
            return {'status': 'read', 'device': receiver.info,
                    'lighting': validate_lighting(lighting)}

    def set_profile(self, *, stage=None, dpis=None, colors=None, follow_stage=False,
                    preserve_lighting=False):
        if follow_stage:
            return self._profile_with_lighting(stage=stage, dpis=dpis, colors=colors,
                                               mode='static-dpi')
        if preserve_lighting:
            return self._profile_with_lighting(stage=stage, dpis=dpis, colors=colors)
        return self._change('profile', 4, lambda before: patch_profile(
            before, stage=stage, dpis=dpis, colors=colors))

    def set_lighting(self, *, mode=None, speed=None, rgb=None):
        if mode is None and speed is None and rgb is None:
            raise ValueError('Informe um modo, uma velocidade ou uma cor.')
        return self._profile_with_lighting(mode=mode, speed=speed, rgb=rgb)

    def apply_saved_profile(self, settings):
        from x11_profiles import validate_settings
        settings=validate_settings(settings)  # Reject invalid presets before opening HID.
        with self.session_factory() as receiver:
            config,polling,lighting=receiver.read(4),receiver.read(6),receiver.read(5)
            light=settings['lighting']
            target={4:patch_profile(config,stage=settings['stage'],
                       dpis=dict(enumerate(settings['dpis'],1)),colors=dict(enumerate(settings['colors'],1))),
                    5:patch_lighting(lighting,mode=light['mode'],speed=light['speed'],rgb=light['color']),
                    6:patch_polling(polling,settings['polling_hz'])}
            before={4:config,5:lighting,6:polling}
            if target==before:
                return {'status':'unchanged','lighting':validate_lighting(lighting),
                        **self.summarize(receiver,config,polling)}
            backup=self.backup_fn(receiver.info,'saved-profile',config,polling,lighting)
            sent=[]
            try:
                # Configuration must precede lighting, including when only one changed.
                sequence=([4,5] if target[4]!=config or target[5]!=lighting else [])
                if target[6]!=polling:sequence.append(6)
                for rid in sequence:
                    receiver.write(target[rid]);sent.append(rid)
                actual={rid:receiver.read(rid) for rid in (4,5,6)}
                return {'status':'verified' if actual==target else 'verification_mismatch',
                        'operation':'saved-profile','backup':backup,'reports_sent':sent,
                        'different_offsets':{str(rid):[i for i,(a,b) in enumerate(zip(target[rid],actual[rid])) if a!=b]
                                             for rid in (4,5,6)},
                        'lighting':validate_lighting(actual[5]),
                        **self.summarize(receiver,actual[4],actual[6])}
            except (OSError,ValueError) as exc:
                raise RuntimeError('Perfil enviado parcialmente ou sem confirmação. Consulte novamente '
                                   'antes de repetir. Backup: %s. Detalhe: %s'%(backup,exc)) from exc

    def _profile_with_lighting(self, *, stage=None, dpis=None, colors=None,
                                mode=None, speed=None, rgb=None):
        with self.session_factory() as receiver:
            config, polling = receiver.read(4), receiver.read(6)
            # Read and validate all old frames BEFORE any setting write.
            lighting = receiver.read(5)
            after = patch_profile(config, stage=stage, dpis=dpis, colors=colors)
            after_lighting = patch_lighting(lighting, mode=mode, speed=speed, rgb=rgb)
            if after == config and after_lighting == lighting:
                return {'status': 'unchanged', 'lighting': validate_lighting(lighting),
                        **self.summarize(receiver, config, polling)}
            backup = self.backup_fn(receiver.info, 'profile-lighting', config, polling, lighting)
            try:
                # Report 04 must precede 05, even if only the lighting mode changes.
                # Receiver.write waits 500 ms, exceeding the reference's 300 ms gap.
                receiver.write(after)
                receiver.write(after_lighting)
                actual_config = receiver.read(4)
                actual_lighting = receiver.read(5)
                different = {
                    'configuration': [i for i,(a,b) in enumerate(zip(after,actual_config)) if a != b],
                    'lighting': [i for i,(a,b) in enumerate(zip(after_lighting,actual_lighting)) if a != b],
                }
                matched = actual_config == after and actual_lighting == after_lighting
                return {'status': 'verified' if matched else 'verification_mismatch',
                        'operation': 'profile-lighting', 'backup': backup,
                        'different_offsets': different,
                        'lighting': validate_lighting(actual_lighting),
                        'expected_lighting_hex': after_lighting.hex(' '),
                        **self.summarize(receiver, actual_config, polling)}
            except (OSError, ValueError) as exc:
                raise RuntimeError('Perfil/iluminação enviados parcialmente ou sem confirmação. '
                                   'Consulte novamente antes de repetir. Backup: %s. Detalhe: %s'
                                   % (backup, exc)) from exc



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', help='Opcional: /dev/hidrawN. Padrão: autodetectar receptor.')
    parser.add_argument('--version', action='version', version=VERSION)
    commands = parser.add_subparsers(dest='command')
    commands.add_parser('status', help='Consulta configurações e polling; não grava ajustes.')
    commands.add_parser('lighting-status', help='Consulta o relatório de iluminação, sem alterar ajustes.')
    commands.add_parser('follow-stage-color', help='Acende continuamente na cor do estágio ativo.')
    sub = commands.add_parser('set-lighting', help='Aplica modo, velocidade e cor global.')
    sub.add_argument('mode', choices=tuple(LIGHTING_MODES))
    sub.add_argument('--speed', type=int, choices=range(1, 6))
    sub.add_argument('--rgb', help='Cor global RRGGBB ou #RRGGBB entre aspas.')
    sub = commands.add_parser('set-polling', help='Grava e verifica o polling.')
    sub.add_argument('hz', type=int, choices=(125, 250, 500, 1000))
    sub = commands.add_parser('set-stage', help='Seleciona estágio habilitado.')
    sub.add_argument('stage', type=int, choices=range(1, 7))
    sub = commands.add_parser('set-dpi', help='Altera DPI de um estágio preservando os demais.')
    sub.add_argument('stage', type=int, choices=range(1, 7))
    sub.add_argument('dpi', type=int)
    sub = commands.add_parser('set-color', help='Altera a cor RGB de um estágio.')
    sub.add_argument('stage', type=int, choices=range(1, 7))
    sub.add_argument('rgb', help='RRGGBB ou #RRGGBB entre aspas.')
    args = parser.parse_args()
    backend = X11(args.device)
    if not args.command:
        try:
            from x11_ui import launch
            return launch(backend)
        except ImportError as exc:
            print('Interface Qt indisponível: %s. No CachyOS/Arch, execute '
                  'sudo pacman -S --needed pyside6 e use o Python do sistema (/usr/bin/python). '
                  'Os comandos de terminal continuam disponíveis.' % exc, file=sys.stderr)
            return 2
    try:
        if args.command == 'status':
            result = backend.status(include_lighting=True)
        elif args.command == 'lighting-status':
            result = backend.lighting_status()
        elif args.command == 'follow-stage-color':
            result = backend.set_profile(follow_stage=True)
        elif args.command == 'set-lighting':
            result = backend.set_lighting(mode=args.mode, speed=args.speed, rgb=args.rgb)
        elif args.command == 'set-polling':
            result = backend.set_polling(args.hz)
        elif args.command == 'set-stage':
            result = backend.set_profile(stage=args.stage, preserve_lighting=True)
        elif args.command == 'set-dpi':
            result = backend.set_profile(dpis={args.stage: args.dpi}, preserve_lighting=True)
        else:
            result = backend.set_profile(colors={args.stage: args.rgb}, preserve_lighting=True)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result['status'] in ('read', 'verified', 'unchanged') else 1
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, indent=2, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
