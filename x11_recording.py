"""Bounded semantic recorder. It does not listen globally or execute events."""
import copy
import time
from x11_macros import MAX_STEPS, MAX_DELAY_MS


class Recording:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.steps = []
        self.held = []
        self.active = False
        self.last = None
        self.reason = ''

    def start(self):
        self.steps, self.held = [], []
        self.active, self.last, self.reason = True, None, ''

    def record(self, step):
        if not self.active:
            return
        action = step['action']
        token = ('button', step['button']) if action.startswith('mouse_') else ('key', step.get('key'))
        press = action in ('press', 'mouse_press')
        release = action in ('release', 'mouse_release')
        if press and token in self.held or release and token not in self.held:
            return
        now = self.clock()
        # The first action has no leading pause. Later pauses are captured in ms.
        gap = max(0, round((now - self.last) * 1000)) if self.last is not None else 0
        waits = [{'action': 'wait', 'ms': min(MAX_DELAY_MS, gap - i)}
                 for i in range(0, min(gap, MAX_DELAY_MS * MAX_STEPS), MAX_DELAY_MS)]
        held_after = len(self.held) + (1 if press else -1 if release else 0)
        # Reserve room for releases on stop, even at the recording limit.
        if gap > MAX_DELAY_MS * MAX_STEPS or len(self.steps) + len(waits) + 1 + held_after > MAX_STEPS:
            self.stop('Limite de passos atingido. A gravação foi parada.');return
        self.steps.extend(waits)
        self.steps.append(copy.deepcopy(step))
        if press:
            self.held.append(token)
        elif release:
            self.held.remove(token)
        self.last = now

    def stop(self, reason=''):
        if not self.active:
            return
        self.active = False
        if self.held:
            gap = max(0, round((self.clock() - self.last) * 1000)) if self.last is not None else 0
            while gap and len(self.steps) + len(self.held) < MAX_STEPS:
                part = min(MAX_DELAY_MS, gap)
                self.steps.append({'action': 'wait', 'ms': part})
                gap -= part
            if gap:
                reason = (reason + ' ' if reason else '') + 'Atraso final limitado pelo número máximo de eventos.'
            reason = (reason + ' ' if reason else '') + 'Solturas finais adicionadas às teclas ou botões ainda pressionados.'
        for kind, value in reversed(self.held):
            self.steps.append({'action': 'mouse_release', 'button': value} if kind == 'button'
                              else {'action': 'release', 'key': value})
        self.held = []
        self.reason = reason
