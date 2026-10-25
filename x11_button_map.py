"""Visual local assignments. Button numbers are UI labels, not HID offsets."""
import math
from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QImage, QPainter, QPainterPath, QPen, QFont, QFontMetrics
from PySide6.QtWidgets import (QWidget, QAbstractButton, QDialog, QVBoxLayout,
 QListWidget, QListWidgetItem, QLabel, QDialogButtonBox, QPushButton)
from x11_macros import SHORTCUTS

BUTTON_NAMES = {1:'Clique esquerdo',2:'Clique direito',3:'Clique da roda',
                4:'Lateral superior',5:'Lateral inferior'}


class AssignmentCallout(QAbstractButton):
    hovered = Signal(int)

    def __init__(self, number, theme, parent):
        super().__init__(parent)
        self.number, self.theme = number, theme
        self.assignment = 'Clique para atribuir'
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(f'Botão {number}: {BUTTON_NAMES[number]}. Clique para atribuir')
        theme.changed.connect(self.update)

    def enterEvent(self, event):
        self.hovered.emit(self.number)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered.emit(0)
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        active = self.underMouse() or self.hasFocus()
        p.setBrush(self.theme.color('SELECTED' if active else 'FIELD'))
        p.setPen(QPen(self.theme.color('ACCENT' if active else 'LINE'), 1.5))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1,1,-1,-1),14,14)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.theme.color('ACCENT'))
        p.drawEllipse(QPointF(24,23),11,11)
        p.setPen(self.theme.color('ON_PRIMARY'))
        p.setFont(QFont('Google Sans',9,QFont.Weight.Bold))
        p.drawText(QRectF(13,12,22,22),Qt.AlignmentFlag.AlignCenter,str(self.number))
        p.setPen(self.theme.color('TEXT'))
        p.setFont(QFont('Google Sans',10,QFont.Weight.Bold))
        metrics=QFontMetrics(p.font())
        title=metrics.elidedText(BUTTON_NAMES[self.number],Qt.TextElideMode.ElideRight,self.width()-50)
        p.drawText(QRectF(43,9,self.width()-50,27),Qt.AlignmentFlag.AlignVCenter,title)
        p.setFont(QFont('Google Sans',9))
        p.setPen(self.theme.color('ACCENT' if self.assignment!='Clique para atribuir' else 'MUTED'))
        text=QFontMetrics(p.font()).elidedText(self.assignment,Qt.TextElideMode.ElideRight,self.width()-32)
        p.drawText(QRectF(16,38,self.width()-32,24),Qt.AlignmentFlag.AlignVCenter,text)


class ButtonMap(QWidget):
    activated = Signal(int)

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme, self.highlight = theme, 0
        self.image = QImage(str(Path(__file__).resolve().parent/'assets/x11-398.png'))
        self.setMinimumHeight(240)
        self.calls = {}
        for number in BUTTON_NAMES:
            call = AssignmentCallout(number,theme,self)
            call.clicked.connect(lambda checked=False,n=number:self.activated.emit(n))
            call.hovered.connect(self.highlight_button)
            self.calls[number] = call
        theme.changed.connect(self.update)

    def highlight_button(self, number):
        self.highlight=number
        self.update()

    def geometry_data(self):
        w,h=self.width(),self.height()
        height=min(h-20,398)
        width=height*215/398
        mouse=QRectF((w-width)/2,(h-height)/2,width,height)
        # Positions of the five numbered markers in the optional local resource.
        anchors={1:(.30,.21),2:(.73,.21),3:(.51,.20),4:(.065,.397),5:(.065,.545)}
        points={n:QPointF(mouse.x()+x*width,mouse.y()+y*height) for n,(x,y) in anchors.items()}
        return mouse,points

    def resizeEvent(self,event):
        w,h=self.width(),self.height()
        cw=int(w*.285);ch=70
        for n,y in ((1,0.),(4,.5),(5,1.)):
            self.calls[n].setGeometry(8,int((h-ch)*y),cw,ch)
        for n,y in ((2,0.),(3,.70)):
            self.calls[n].setGeometry(w-cw-8,int((h-ch)*y),cw,ch)
        super().resizeEvent(event)

    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        mouse,points=self.geometry_data()
        if not self.image.isNull():
            p.drawImage(mouse,self.image)
        else:
            self.draw_mouse(p,mouse)
        for n,point in points.items():
            box=self.calls[n].geometry()
            left=n in (1,4,5)
            start=QPointF(box.right()+5 if left else box.left()-5,box.center().y())
            end=QPointF(point.x()+(-14 if left else 14),point.y())
            color=self.theme.color('ACCENT' if n==self.highlight else 'MUTED')
            p.setPen(QPen(color,2 if n==self.highlight else 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            path=QPainterPath(start)
            middle=(start.x()+end.x())/2
            if n==3:
                end=QPointF(point.x(),point.y()+14)
                path.cubicTo(QPointF(middle,start.y()),QPointF(end.x(),end.y()+55),end)
            else:
                path.cubicTo(QPointF(middle,start.y()),QPointF(middle,end.y()),end)
            p.drawPath(path)
            direction=1 if left else -1
            if n==3:
                p.drawLine(end,QPointF(end.x()-4,end.y()+6))
                p.drawLine(end,QPointF(end.x()+4,end.y()+6))
            else:
                p.drawLine(end,QPointF(end.x()-direction*6,end.y()-4))
                p.drawLine(end,QPointF(end.x()-direction*6,end.y()+4))
            p.setPen(QPen(self.theme.color('BG'),2))
            p.setBrush(self.theme.color('ACCENT'))
            p.drawEllipse(point,11,11)
            p.setPen(self.theme.color('ON_PRIMARY'));p.setFont(QFont('Google Sans',8,QFont.Weight.Bold))
            p.drawText(QRectF(point.x()-10,point.y()-10,20,20),Qt.AlignmentFlag.AlignCenter,str(n))

    def draw_mouse(self,p,r):
        p.save();p.translate(r.topLeft());p.scale(r.width()/215,r.height()/398)
        path=QPainterPath(QPointF(20,50));path.cubicTo(20,-10,195,-10,195,50)
        path.cubicTo(210,180,215,375,108,390);path.cubicTo(0,375,5,180,20,50)
        p.setBrush(self.theme.color('TEXT'));p.setPen(QPen(self.theme.color('MUTED'),1));p.drawPath(path)
        p.drawLine(QPointF(108,10),QPointF(108,180));p.drawLine(QPointF(15,180),QPointF(200,180))
        p.setBrush(self.theme.color('BG'));p.drawRoundedRect(QRectF(97,40,22,60),7,7)
        p.drawRoundedRect(QRectF(8,145,7,26),3,3);p.drawRoundedRect(QRectF(8,200,7,26),3,3)
        p.restore()

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            _,points=self.geometry_data()
            for n,point in points.items():
                if math.hypot(event.position().x()-point.x(),event.position().y()-point.y())<=18:
                    self.activated.emit(n);return
        super().mousePressEvent(event)

    def set_assignments(self,bindings,items):
        names={item['id']:item['name'] for item in items}
        for n,call in self.calls.items():
            value=bindings[str(n)]
            label=SHORTCUTS[value][0] if value in SHORTCUTS else names.get(value,'Clique para atribuir')
            if value=='copy':label+=' · Ctrl+C'
            if value=='paste':label+=' · Ctrl+V'
            call.assignment=label
            call.setAccessibleName(f'Botão {n}: {BUTTON_NAMES[n]}. {label}')
            call.setToolTip(f'Botão {n} · {label} · Atribuição local, ainda não aplicada ao mouse')
            call.update()


class AssignmentDialog(QDialog):
    def __init__(self,number,items,current,parent=None):
        super().__init__(parent)
        self.create_requested=False
        self.value=current
        self.setWindowTitle(f'Botão {number} · {BUTTON_NAMES[number]}')
        self.resize(440,430)
        layout=QVBoxLayout(self);layout.setContentsMargins(24,24,24,24);layout.setSpacing(14)
        label=QLabel('Crie uma gravação de teclado e mouse ou associe uma macro da sua biblioteca.');label.setWordWrap(True);layout.addWidget(label)
        create=QPushButton('＋ Criar e gravar nova macro');create.clicked.connect(self.create);layout.addWidget(create)
        layout.addWidget(QLabel('Suas macros'))
        self.macros=QListWidget();self.macros.setAccessibleName('Macros para atribuir')
        for item in items:
            row=QListWidgetItem(item['name']);row.setData(Qt.ItemDataRole.UserRole,item['id']);self.macros.addItem(row)
            if item['id']==current:self.macros.setCurrentItem(row)
        layout.addWidget(self.macros,1)
        if not items:
            label=QLabel('Sua biblioteca está vazia. Crie uma macro para começar.');label.setWordWrap(True);layout.addWidget(label)
        remove=QPushButton('Remover atribuição local');remove.setEnabled(current is not None);remove.clicked.connect(self.remove);layout.addWidget(remove)
        note=QLabel('Atribuições locais. A execução no X11 depende da integração com o protocolo.');note.setWordWrap(True);layout.addWidget(note)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText('Atribuir macro selecionada')
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Cancelar')
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(self.macros.currentItem() is not None)
        self.macros.currentRowChanged.connect(lambda _:self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(self.macros.currentItem() is not None))
        self.buttons.accepted.connect(self.assign_selected);self.buttons.rejected.connect(self.reject);layout.addWidget(self.buttons)
    def create(self):
        self.create_requested=True;self.accept()
    def remove(self):
        self.value=None;self.accept()
    def assign_selected(self):
        if self.macros.currentItem() is not None:
            self.value=self.macros.currentItem().data(Qt.ItemDataRole.UserRole);self.accept()


class ButtonAssignments(QWidget):
    def __init__(self,window,store,on_create=None):
        from x11_ui import Text,column
        super().__init__();self.window,self.store=window,store;self.on_create=on_create
        layout=column(self)
        card,content=window.card('Atribua uma ação a cada botão','Clique no número do mouse ou no cartão indicado pela seta.')
        layout.addWidget(card,1)
        self.map=ButtonMap(window.theme);content.addWidget(self.map,1)
        note=Text('Atribuições locais · Ainda não aplicadas ao mouse',window.theme,9,role='MUTED');content.addWidget(note)
        self.map.activated.connect(lambda number:window.guard(lambda:self.choose(number)))
        self.refresh()

    def refresh(self):
        try:self.map.set_assignments(self.store.assignments(),self.store.list())
        except (OSError,ValueError) as exc:self.window.message.setText(str(exc))

    def choose(self,number):
        dialog=AssignmentDialog(number,self.store.list(),self.store.assignments()[str(number)],self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            if dialog.create_requested:
                if self.on_create:self.on_create(number)
            else:self.assign(number,dialog.value)

    def assign(self,number,value):
        self.store.assign(number,value);self.refresh()
        self.window.message.setText(f'Atribuição do botão {number} salva localmente. Ainda não aplicada ao mouse.')
