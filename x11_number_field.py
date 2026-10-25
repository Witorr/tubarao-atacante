"""Material-style number field using Qt's native numeric editing behavior."""
from PySide6.QtCore import Qt, QEvent, QRectF
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QSpinBox, QAbstractSpinBox, QAbstractButton


class StepButton(QAbstractButton):
    def __init__(self, direction, theme, parent):
        super().__init__(parent)
        self.direction, self.theme = direction, theme
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoRepeat(True)
        self.setAutoRepeatDelay(400)
        self.setAutoRepeatInterval(90)
        self.setAccessibleName('Aumentar' if direction > 0 else 'Diminuir')
        theme.changed.connect(self.update)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = self.theme
        if self.isEnabled() and (self.underMouse() or self.isDown() or self.hasFocus()):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(t.color('SELECTED'))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1,1,-1,-1),9,9)
        p.setPen(QPen(t.color('ACCENT' if self.isEnabled() else 'MUTED'),1.8,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
        x,y = self.width()/2,self.height()/2
        p.drawLine(int(x-4),int(y),int(x+4),int(y))
        if self.direction > 0:
            p.drawLine(int(x),int(y-4),int(x),int(y+4))
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(t.color('ACCENT'),1.2))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1,1,-1,-1),9,9)


class NumberField(QSpinBox):
    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setMinimumSize(120,38)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet('NumberField {border:0;background:transparent;padding:0;}')
        self.lineEdit().setStyleSheet('QLineEdit {border:0;background:transparent;padding:0;}')
        self.minus = StepButton(-1,theme,self)
        self.plus = StepButton(1,theme,self)
        self.minus.clicked.connect(self.stepDown)
        self.plus.clicked.connect(self.stepUp)
        self.valueChanged.connect(self.update_buttons)
        theme.changed.connect(self.update)
        for widget in (self.lineEdit(),self.minus,self.plus):
            widget.installEventFilter(self)
        self.update_buttons()

    def update_buttons(self, *_):
        if hasattr(self,'minus'):
            self.minus.setEnabled(self.value() > self.minimum() or self.wrapping())
            self.plus.setEnabled(self.value() < self.maximum() or self.wrapping())
        self.update()

    def setRange(self, minimum, maximum):
        super().setRange(minimum,maximum)
        self.update_buttons()

    def setMinimum(self, value):
        super().setMinimum(value)
        self.update_buttons()

    def setMaximum(self, value):
        super().setMaximum(value)
        self.update_buttons()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self,'minus'):
            height=self.height()
            self.minus.setGeometry(4,(height-30)//2,30,30)
            self.plus.setGeometry(self.width()-34,(height-30)//2,30,30)
            self.lineEdit().setGeometry(38,3,max(1,self.width()-76),height-6)

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.FocusIn,QEvent.Type.FocusOut):
            self.update()
        return super().eventFilter(obj,event)

    def paintEvent(self, event):
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        focused=self.hasFocus() or any(w.hasFocus() for w in (self.lineEdit(),self.minus,self.plus))
        p.setBrush(self.theme.color('FIELD' if self.isEnabled() else 'CARD'))
        p.setPen(QPen(self.theme.color('ACCENT' if focused else 'LINE'),1.5 if focused else 1))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1,1,-1,-1),12,12)
