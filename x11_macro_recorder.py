"""Qt input capture restricted to an explicit recording surface."""
from PySide6.QtCore import Qt, QEvent, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (QFrame, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
 QPushButton, QDialogButtonBox)
from x11_recording import Recording

QT_KEYS = {int(getattr(Qt.Key, 'Key_'+c)):c for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'}
QT_KEYS.update({int(getattr(Qt.Key, 'Key_F'+str(i))):'F'+str(i) for i in range(1,25)})
for qt,name in {'Control':'LeftCtrl','Shift':'LeftShift','Alt':'LeftAlt','Meta':'LeftMeta',
 'Return':'Enter','Enter':'Enter','Escape':'Escape','Tab':'Tab','Space':'Space','Backspace':'Backspace',
 'Delete':'Delete','Insert':'Insert','Home':'Home','End':'End','PageUp':'PageUp','PageDown':'PageDown',
 'Up':'ArrowUp','Down':'ArrowDown','Left':'ArrowLeft','Right':'ArrowRight'}.items():
 QT_KEYS[int(getattr(Qt.Key,'Key_'+qt))]=name
MOUSE = {Qt.MouseButton.LeftButton:'left',Qt.MouseButton.RightButton:'right',
 Qt.MouseButton.MiddleButton:'middle',Qt.MouseButton.BackButton:'back',Qt.MouseButton.ForwardButton:'forward'}
MOUSE_LABELS={'left':'Clique esquerdo','right':'Clique direito','middle':'Clique da roda',
 'back':'Botão lateral 4','forward':'Botão lateral 5'}


def key_name(event):
    key=int(event.key())
    if key in (0,int(Qt.Key.Key_unknown)):
        return None
    # On Linux evdev scan codes usually carry +8; X11 and Wayland can differ.
    # Preserve left/right distinction only for the two recognized conventions.
    scan=event.nativeScanCode()
    for scans,name in (((97,105),'RightCtrl'),((100,108),'RightAlt'),
                       ((54,62),'RightShift'),((126,134),'RightMeta')):
        if scan in scans and key in (int(Qt.Key.Key_Control),int(Qt.Key.Key_Alt),int(Qt.Key.Key_Shift),int(Qt.Key.Key_Meta)):
            expected={'RightCtrl':Qt.Key.Key_Control,'RightAlt':Qt.Key.Key_Alt,
                      'RightShift':Qt.Key.Key_Shift,'RightMeta':Qt.Key.Key_Meta}[name]
            if key==int(expected):return name
    return QT_KEYS.get(key,'QtKey:'+str(key))


def step_value(step):
    if step['action']=='wait':return str(step['ms'])
    if 'button' in step:return MOUSE_LABELS[step['button']]
    if step['action']=='wheel':
        return ('Vertical' if step['axis']=='vertical' else 'Horizontal')+' '+str(step['delta'])
    key=step['key']
    if key.startswith('QtKey:'):
        return QKeySequence(int(key[6:])).toString() or key
    return key


class CaptureSurface(QFrame):
    changed = Signal()
    stopped = Signal()

    def __init__(self, recorder, parent=None):
        super().__init__(parent)
        self.recorder=recorder
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName('Área de gravação de teclado e mouse')
        self.setMinimumHeight(150)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet('CaptureSurface {background:palette(base);border:2px solid palette(highlight);border-radius:12px;}')
        layout=QVBoxLayout(self)
        text=QLabel('Execute aqui suas teclas, cliques e rolagens.\n\nClique em Parar para finalizar. Sair desta área também encerra a gravação.')
        text.setAlignment(Qt.AlignmentFlag.AlignCenter);text.setWordWrap(True)
        text.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents);layout.addWidget(text)

    def event(self,event):
        if not hasattr(self,'recorder') or not self.recorder.active:return super().event(event)
        kind=event.type()
        if kind in (QEvent.Type.ShortcutOverride,QEvent.Type.KeyPress,QEvent.Type.KeyRelease):
            event.accept()
            if kind==QEvent.Type.ShortcutOverride:return True
            if not event.isAutoRepeat():
                name=key_name(event)
                if name:self.recorder.record({'action':'press' if kind==QEvent.Type.KeyPress else 'release','key':name})
            self.notify();return True
        if kind in (QEvent.Type.MouseButtonPress,QEvent.Type.MouseButtonDblClick,QEvent.Type.MouseButtonRelease):
            if event.button() in MOUSE:
                self.recorder.record({'action':'mouse_release' if kind==QEvent.Type.MouseButtonRelease else 'mouse_press',
                                      'button':MOUSE[event.button()]})
            event.accept();self.notify();return True
        if kind==QEvent.Type.Wheel:
            for axis,delta in (('vertical',event.angleDelta().y()),('horizontal',event.angleDelta().x())):
                if delta:
                    # Split large wheel deltas into bounded semantic events.
                    while delta and self.recorder.active:
                        part=max(-12000,min(12000,delta));delta-=part
                        self.recorder.record({'action':'wheel','axis':axis,'delta':part})
            event.accept();self.notify();return True
        return super().event(event)

    def notify(self):
        self.changed.emit()
        if not self.recorder.active:self.stopped.emit()

    def finish(self):
        self.recorder.stop();self.changed.emit();self.stopped.emit()

    def focusOutEvent(self,event):
        if self.recorder.active:self.finish()
        super().focusOutEvent(event)


class RecordingDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle('Gravar teclado e mouse');self.resize(600,390)
        self.recorder=Recording()
        layout=QVBoxLayout(self);layout.setContentsMargins(24,24,24,24);layout.setSpacing(14)
        label=QLabel('Clique em Gravar e execute as ações dentro da área abaixo. Os intervalos entre os eventos também serão registrados.')
        label.setWordWrap(True);layout.addWidget(label)
        self.surface=CaptureSurface(self.recorder);layout.addWidget(self.surface,1)
        controls=QHBoxLayout();self.start_button=QPushButton('Gravar');self.stop_button=QPushButton('Parar')
        controls.addWidget(self.start_button);controls.addWidget(self.stop_button);layout.addLayout(controls)
        self.status=QLabel('Pronto para gravar. Nenhuma entrada fora desta área será capturada.');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText('Usar gravação')
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Cancelar')
        layout.addWidget(self.buttons)
        self.start_button.clicked.connect(self.start);self.stop_button.clicked.connect(self.surface.finish)
        self.surface.changed.connect(self.update_state);self.surface.stopped.connect(self.update_state)
        self.buttons.accepted.connect(self.accept);self.buttons.rejected.connect(self.reject)
        self.update_state()

    def start(self):
        self.recorder.start();self.surface.setFocus();self.update_state()

    def update_state(self):
        self.start_button.setEnabled(not self.recorder.active)
        self.start_button.setText('Gravar novamente' if self.recorder.steps else 'Gravar')
        self.stop_button.setEnabled(self.recorder.active)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(bool(self.recorder.steps) and not self.recorder.active)
        if self.recorder.active:self.status.setText(f'Gravando · {len(self.recorder.steps)} eventos · Clique em Parar ao concluir')
        elif self.recorder.steps:self.status.setText(f'{len(self.recorder.steps)} eventos registrados. '+self.recorder.reason)

    def accept(self):
        self.surface.finish()
        if self.recorder.steps:super().accept()

    def reject(self):
        self.recorder.stop();super().reject()

    def closeEvent(self,event):
        self.recorder.stop();super().closeEvent(event)
