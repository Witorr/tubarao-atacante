"""Local macro drafts. No HID encoding, input injection or device access.

Limits below belong to this editor, not to the unverified X11 firmware.
Key names describe physical keys independently of a keyboard layout.
"""
import copy
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
import re
from pathlib import Path
import tempfile
import uuid

from x11_profiles import clean_name

KEYS = tuple('ABCDEFGHIJKLMNOPQRSTUVWXYZ') + tuple('0123456789') + tuple(
    f'F{i}' for i in range(1, 25)) + (
    'LeftCtrl', 'RightCtrl', 'LeftShift', 'RightShift', 'LeftAlt', 'RightAlt',
    'LeftMeta', 'RightMeta', 'Enter', 'Escape', 'Tab', 'Space', 'Backspace',
    'Delete', 'Insert', 'Home', 'End', 'PageUp', 'PageDown', 'ArrowUp',
    'ArrowDown', 'ArrowLeft', 'ArrowRight',
)
MAX_STEPS = 256
MAX_DELAY_MS = 60_000
MAX_REPEATS = 100
MAX_DURATION_MS = 3_600_000
MAX_FILE_BYTES = 2_000_000
MODES = {'once': 'Uma vez', 'hold': 'Enquanto pressionado',
         'toggle': 'Alternar', 'repeat': 'Repetir N vezes'}
MOUSE_BUTTONS = ('left', 'right', 'middle', 'back', 'forward')


def valid_key(key):
    if not isinstance(key, str):
        return False
    if key in KEYS:
        return True
    return bool(re.fullmatch(r'QtKey:[1-9][0-9]{0,8}', key)) and int(key[6:]) < 0x01ffffff

SHORTCUTS = {'copy': ('Copiar', 'C'), 'paste': ('Colar', 'V')}


def shortcut_macro(name):
    """Semantic preset only, without injecting keys or accessing the mouse."""
    if name not in SHORTCUTS:
        raise ValueError('Atalho não reconhecido.')
    key = SHORTCUTS[name][1]
    return {'repeats': 1, 'steps': [
        {'action': 'press', 'key': 'LeftCtrl'}, {'action': 'press', 'key': key},
        {'action': 'release', 'key': key}, {'action': 'release', 'key': 'LeftCtrl'}]}


class IncompleteMacroError(ValueError):
    def __init__(self, held):
        self.releases = [({'action': 'mouse_release', 'button': value} if kind == 'mouse'
                          else {'action': 'release', 'key': value})
                         for kind, value in reversed(list(held))]
        super().__init__('Faltam os eventos de soltura: ' + ', '.join(value for _, value in held)
                         + '. Conclua a combinação antes de salvar.')


def complete_macro(data):
    """Prepare a balanced candidate for explicit review; never persist or execute."""
    try:
        return validate_macro(data)
    except IncompleteMacroError as exc:
        candidate = copy.deepcopy(data)
        candidate['steps'].extend(exc.releases)
        return validate_macro(candidate)


def validate_macro(data):
    if not isinstance(data, dict) or set(data) not in ({'steps', 'repeats'}, {'steps', 'repeats', 'mode'}):
        raise ValueError('Formato de macro não reconhecido.')
    mode = data.get('mode', 'once')
    if not isinstance(mode, str) or mode not in MODES:
        raise ValueError('Modo de execução não reconhecido.')
    repeats, steps = data['repeats'], data['steps']
    if type(repeats) is not int or not 1 <= repeats <= MAX_REPEATS:
        raise ValueError(f'Use de 1 a {MAX_REPEATS} repetições.')
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        raise ValueError(f'Use de 1 a {MAX_STEPS} passos.')
    held, duration, presses = {}, 0, 0
    for index, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            raise ValueError(f'Passo {index} inválido.')
        action = step.get('action')
        if action == 'wait' and set(step) == {'action', 'ms'}:
            if type(step['ms']) is not int or not 1 <= step['ms'] <= MAX_DELAY_MS:
                raise ValueError(f'Passo {index}: atraso deve ser de 1 a {MAX_DELAY_MS} ms.')
            duration += step['ms']
        elif (action in ('press', 'release') and set(step) == {'action', 'key'}
              or action in ('mouse_press', 'mouse_release') and set(step) == {'action', 'button'}):
            mouse = action.startswith('mouse_')
            key = step['button'] if mouse else step['key']
            if not (isinstance(key, str) and key in MOUSE_BUTTONS if mouse else valid_key(key)):
                raise ValueError(f'Passo {index}: tecla ou botão não reconhecido.')
            key = ('mouse' if mouse else 'key', key)
            if action in ('press', 'mouse_press'):
                if key in held:
                    raise ValueError(f'Passo {index}: {key[1]} já está pressionada.')
                held[key] = None
                presses += 1
            else:
                if key not in held:
                    raise ValueError(f'Passo {index}: {key[1]} não foi pressionada.')
                del held[key]
        elif action == 'wheel' and set(step) == {'action', 'axis', 'delta'}:
            if (step['axis'] not in ('vertical', 'horizontal') or type(step['delta']) is not int
                    or not -12000 <= step['delta'] <= 12000 or step['delta'] == 0):
                raise ValueError(f'Passo {index}: rolagem inválida.')
            presses += 1
        else:
            raise ValueError(f'Passo {index}: ação não reconhecida.')
    if held:
        raise IncompleteMacroError(held)
    if not presses:
        raise ValueError('Grave pelo menos uma tecla, um clique ou uma rolagem.')
    effective_repeats = repeats if data.get('mode', 'repeat') == 'repeat' else 1
    if duration * effective_repeats > MAX_DURATION_MS:
        raise ValueError('A duração total dos atrasos deve ser de até uma hora.')
    return copy.deepcopy(data)


def summary(data):
    data = validate_macro(data)
    return {'steps': len(data['steps']), 'repeats': data['repeats'],
            'delay_ms': sum(s.get('ms', 0) for s in data['steps']) * (data['repeats'] if data.get('mode', 'repeat') == 'repeat' else 1)}


class MacroStore:
    def __init__(self, directory=None):
        base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')).expanduser()
        self.directory = Path(directory) if directory is not None else base / 'tubarao-atacante'
        self.path = self.directory / 'macros.json'

    @contextmanager
    def locked(self):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.directory / 'macros.lock',
                     os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def _read(self):
        if not self.path.exists():
            return {'schema': 3, 'macros': [], 'assignments': {str(i): None for i in range(1, 6)}}
        try:
            if self.path.stat().st_size > MAX_FILE_BYTES:
                raise ValueError('Arquivo de macros muito grande.')
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if (not isinstance(data, dict) or type(data.get('schema')) is not int
                    or data['schema'] not in (1, 2, 3)
                    or set(data) != ({'schema', 'macros'} if data['schema'] == 1 else {'schema', 'macros', 'assignments'})
                    or not isinstance(data['macros'], list)):
                raise ValueError('Formato de macros não reconhecido.')
            ids, names = set(), set()
            for item in data['macros']:
                if not isinstance(item, dict) or set(item) != {'id', 'name', 'created_at', 'updated_at', 'macro'}:
                    raise ValueError('Registro de macro inválido.')
                if str(uuid.UUID(item['id'])) != item['id'] or item['id'] in ids:
                    raise ValueError('Identificador inválido ou duplicado.')
                name = clean_name(item['name'])
                if name != item['name'] or name.casefold() in names:
                    raise ValueError('Nome inválido ou duplicado.')
                for field in ('created_at', 'updated_at'):
                    datetime.fromisoformat(item[field])
                item['macro'] = validate_macro(item['macro'])
                ids.add(item['id'])
                names.add(name.casefold())
            if data['schema'] == 1:
                data = dict(data, schema=2, assignments={str(i): None for i in range(1, 6)})
            bindings = data['assignments']
            if not isinstance(bindings, dict) or set(bindings) != {str(i) for i in range(1, 6)}:
                raise ValueError('Mapa de botões inválido.')
            for value in bindings.values():
                if value is not None and (not isinstance(value, str) or value not in ids | SHORTCUTS.keys()):
                    raise ValueError('Atribuição de macro inválida.')
            data['schema'] = 3
            return data
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise ValueError('Não foi possível ler macros.json. O arquivo foi preservado. ' + str(exc)) from exc

    def _write(self, data):
        payload = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
        if len(payload.encode('utf-8')) > MAX_FILE_BYTES:
            raise ValueError('Limite do arquivo de macros atingido.')
        fd, temporary = tempfile.mkstemp(prefix='.macros-', suffix='.tmp', dir=self.directory)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            dir_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @staticmethod
    def _find(data, macro_id):
        for item in data['macros']:
            if item['id'] == macro_id:
                return item
        raise ValueError('A macro não existe mais. Atualize a lista.')

    def list(self):
        with self.locked():
            return copy.deepcopy(self._read()['macros'])

    def save(self, name, macro, macro_id=None, button=None):
        if button is not None and (type(button) is not int or button not in range(1, 6)):
            raise ValueError('Escolha um dos cinco botões do mapa.')
        name, macro = clean_name(name), validate_macro(macro)
        with self.locked():
            data = self._read()
            if any(m['id'] != macro_id and m['name'].casefold() == name.casefold() for m in data['macros']):
                raise ValueError('Já existe uma macro com esse nome.')
            now = datetime.now(timezone.utc).isoformat()
            if macro_id is None:
                item = {'id': str(uuid.uuid4()), 'created_at': now}
                data['macros'].append(item)
            else:
                item = self._find(data, macro_id)
            item.update(name=name, macro=macro, updated_at=now)
            if button is not None:
                data['assignments'][str(button)] = item['id']
            self._write(data)
            return copy.deepcopy(item)

    def delete(self, macro_id):
        with self.locked():
            data = self._read()
            self._find(data, macro_id)
            data['macros'] = [m for m in data['macros'] if m['id'] != macro_id]
            data['assignments'] = {button: None if value == macro_id else value
                                   for button, value in data['assignments'].items()}
            self._write(data)

    def assignments(self):
        with self.locked():
            return copy.deepcopy(self._read()['assignments'])

    def assign(self, button, value):
        if type(button) is not int or button not in range(1, 6):
            raise ValueError('Escolha um dos cinco botões do mapa.')
        with self.locked():
            data = self._read()
            if value is not None:
                if not isinstance(value, str):
                    raise ValueError('Atribuição inválida.')
                if value not in SHORTCUTS:
                    self._find(data, value)
            data['assignments'][str(button)] = value
            self._write(data)
