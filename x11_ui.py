"""Qt 6 interface: antialiased painting and time-based native animations."""
import colorsys
import json
import math
from pathlib import Path
import time
from PySide6.QtCore import (Qt,QObject,Signal,QTimer,QVariantAnimation,QEasingCurve,QRectF,QPointF,
                            QRunnable,QThreadPool,QSignalBlocker)
from PySide6.QtGui import QColor,QPainter,QPen,QFont,QFontDatabase,QPalette,QImage,QIcon,QPixmap
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QFrame,QLabel,QPushButton,QAbstractButton,
 QHBoxLayout,QVBoxLayout,QGridLayout,QStackedWidget,QSlider,QLineEdit,QRadioButton,QButtonGroup,
 QListWidget,QTextEdit,QScrollBar,QInputDialog,QMessageBox,QColorDialog,QSizePolicy,QDialog,QDialogButtonBox)
from x11_appearance import LIGHT,DARK,load_preference,save_preference,system_theme
from x11_profiles import ProfileStore,validate_settings

ROOT=Path(__file__).resolve().parent


def mix(a,b,t):
 a,b=QColor(a),QColor(b)
 return QColor.fromRgbF(*(x+(y-x)*t for x,y in zip(a.getRgbF(),b.getRgbF())))


def ink(color):
 c=QColor(color);values=[c.redF(),c.greenF(),c.blueF()]
 lum=sum((v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4)*k for v,k in zip(values,(.2126,.7152,.0722)))
 return QColor('#141218' if lum>.179 else '#ffffff')


class TaskSignals(QObject):
 result=Signal(object);error=Signal(str)


class Task(QRunnable):
 def __init__(self,operation):super().__init__();self.operation=operation;self.signals=TaskSignals()
 def run(self):
  try:self.signals.result.emit(self.operation())
  except Exception as exc:self.signals.error.emit(str(exc))


class Theme(QObject):
 changed=Signal();targetChanged=Signal(bool)
 def __init__(self,parent):
  super().__init__(parent);self.mode=load_preference();self.current='light';self.target='light'
  self.colors={k:QColor(v) for k,v in LIGHT.items()};self.darkness=0.;self.pending=False;self.task=None
  self.animation=QVariantAnimation(self);self.animation.setDuration(360)
  self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
  self.animation.valueChanged.connect(self.frame)
  self.timer=QTimer(self);self.timer.timeout.connect(self.check_system);self.timer.start(5000)
  if self.mode!='system':self.apply(self.mode,False)
  QTimer.singleShot(0,self.check_system)
 def color(self,key):return self.colors[key]
 def frame(self,value):
  self.darkness=self.start_dark+(float(self.target=='dark')-self.start_dark)*float(value)
  self.colors={k:mix(self.start[k],self.end[k],float(value)) for k in LIGHT};self.publish()
 def publish(self):
  p=QPalette()
  for role,key in ((QPalette.ColorRole.Window,'BG'),(QPalette.ColorRole.WindowText,'TEXT'),
   (QPalette.ColorRole.Base,'FIELD'),(QPalette.ColorRole.AlternateBase,'CARD'),(QPalette.ColorRole.Text,'TEXT'),
   (QPalette.ColorRole.Button,'SELECTED'),(QPalette.ColorRole.ButtonText,'TEXT'),(QPalette.ColorRole.Highlight,'ACCENT'),
   (QPalette.ColorRole.HighlightedText,'ON_PRIMARY'),(QPalette.ColorRole.Mid,'LINE'),(QPalette.ColorRole.PlaceholderText,'MUTED'),
   (QPalette.ColorRole.ToolTipBase,'CARD'),(QPalette.ColorRole.ToolTipText,'TEXT')):p.setColor(role,self.color(key))
  application=QApplication.instance();application.setPalette(p)
  # Qt stylesheets resolve palette() when polished. Refresh only the native
  # input/scroll widgets, rather than rebuilding the stylesheet or the window.
  for widget in application.allWidgets():
   if isinstance(widget,(QLineEdit,QTextEdit,QListWidget,QRadioButton,QScrollBar)) or widget.isWindow():
    widget.setPalette(p)
    if isinstance(widget,(QLineEdit,QTextEdit,QListWidget,QScrollBar)):
     widget.style().unpolish(widget);widget.style().polish(widget);widget.setPalette(p)
  self.changed.emit()
 def apply(self,mode,animate=True):
  self.animation.stop();self.start_dark=self.darkness;self.start=dict(self.colors);self.end={k:QColor(v) for k,v in (DARK if mode=='dark' else LIGHT).items()}
  self.current=self.target=mode;self.targetChanged.emit(mode=='dark')
  if animate:
   self.animation.setStartValue(0.);self.animation.setEndValue(1.);self.animation.start()
  else:self.darkness=float(mode=='dark');self.colors=dict(self.end);self.publish()
 def select(self,mode):
  save_preference(mode);self.mode=mode
  if mode=='system':self.check_system()
  else:self.apply(mode)
  self.changed.emit()
 def check_system(self):
  if self.mode!='system' or self.pending:return
  self.pending=True;self.task=Task(system_theme)
  self.task.signals.result.connect(self.system_result);self.task.signals.error.connect(lambda _:self.system_result('light'))
  QThreadPool.globalInstance().start(self.task)
 def system_result(self,result):
  self.pending=False
  if self.mode=='system' and result!=self.target:self.apply(result)
  self.changed.emit()


class Text(QLabel):
 def __init__(self,text,theme,size=10,bold=False,role='TEXT'):
  super().__init__(text);self.theme=theme;self.role=role;self.setFont(QFont('Google Sans',size,QFont.Weight.Bold if bold else QFont.Weight.Normal))
  self.setWordWrap(True);theme.changed.connect(self.refresh);self.refresh()
 def refresh(self):
  p=self.palette();p.setColor(QPalette.ColorRole.WindowText,self.theme.color(self.role));self.setPalette(p)


class Card(QWidget):
 def __init__(self,theme,radius=24,role='CARD'):
  super().__init__();self.theme=theme;self.radius=radius;self.role=role;theme.changed.connect(self.update)
 def paintEvent(self,event):
  p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setPen(Qt.PenStyle.NoPen);p.setBrush(self.theme.color(self.role));p.drawRoundedRect(QRectF(self.rect()),self.radius,self.radius)


class BrandImage(QWidget):
 def __init__(self,name,theme):
  super().__init__();self.theme=theme
  self.light=QPixmap(str(ROOT/f'branding/{name}.png'));self.dark=QPixmap(str(ROOT/f'branding/{name}-dark.png'))
  self.setFixedSize(self.light.size());theme.changed.connect(self.update)
 def paintEvent(self,event):
  painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
  painter.setOpacity(1-self.theme.darkness);painter.drawPixmap(0,0,self.light)
  painter.setOpacity(self.theme.darkness);painter.drawPixmap(0,0,self.dark)


class Button(QPushButton):
 def __init__(self,text,theme,callback=None,primary=False):
  super().__init__(text);self.theme=theme;self.primary=primary;self.selected=False;self.swatch=None;self.flat=False
  self.setFont(QFont('Google Sans',10,QFont.Weight.Medium));self.setMinimumHeight(38);self.setCursor(Qt.CursorShape.PointingHandCursor)
  self.setContentsMargins(18,0,18,0);self.setMinimumWidth(self.fontMetrics().horizontalAdvance(text)+30)
  theme.changed.connect(self.update)
  if callback:self.clicked.connect(callback)
 def keyPressEvent(self,event):
  if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):self.click();event.accept()
  else:super().keyPressEvent(event)
 def paintEvent(self,event):
  t=self.theme;c=QColor(self.swatch) if self.swatch else t.color('ACCENT' if self.primary else 'SELECTED')
  if self.flat and not self.selected and not self.swatch:c=t.color('SIDE')
  fg=ink(c) if self.swatch else t.color('ON_PRIMARY' if self.primary else 'ACCENT' if self.selected else 'TEXT')
  if not self.isEnabled():c=mix(t.color('CARD'),t.color('TEXT'),.08);fg=t.color('MUTED')
  elif self.isDown():c=mix(c,fg,.14)
  elif self.underMouse():c=mix(c,fg,.07)
  p=QPainter(self);p.setRenderHints(QPainter.RenderHint.Antialiasing|QPainter.RenderHint.TextAntialiasing)
  p.setPen(QPen(t.color('ACCENT'),1.4) if self.hasFocus() or self.selected else Qt.PenStyle.NoPen);p.setBrush(c)
  p.drawRoundedRect(QRectF(self.rect()).adjusted(1,1,-1,-1),19,19);p.setPen(fg);p.setFont(self.font());p.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,self.text())


class SmoothSlider(QSlider):
 def __init__(self,theme,vertical=False):
  super().__init__(Qt.Orientation.Vertical if vertical else Qt.Orientation.Horizontal);self.theme=theme;self.vertical=vertical
  self.setFocusPolicy(Qt.FocusPolicy.StrongFocus);theme.changed.connect(self.update)
  if vertical:self.setMinimumWidth(32);self.setMinimumHeight(65)
  else:self.setMinimumHeight(30)
 def paintEvent(self,event):
  p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
  t=self.theme;ratio=(self.value()-self.minimum())/max(1,self.maximum()-self.minimum());accent=t.color('ACCENT' if self.isEnabled() else 'MUTED')
  if self.vertical:
   x=self.width()/2;y=self.height()-12-(self.height()-24)*ratio
   track=QRectF(x-3,10,6,self.height()-20);active=QRectF(x-3,y,6,max(0,self.height()-10-y))
  else:
   x=12+(self.width()-24)*ratio;y=self.height()/2
   track=QRectF(10,y-3,self.width()-20,6);active=QRectF(10,y-3,max(0,x-10),6)
  p.setPen(Qt.PenStyle.NoPen);p.setBrush(t.color('SELECTED'));p.drawRoundedRect(track,3,3)
  p.setBrush(accent);p.drawRoundedRect(active,3,3);p.drawEllipse(QPointF(x,y),8,8)
  if self.hasFocus():p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(accent,1));p.drawEllipse(QPointF(x,y),12,12)
 def set_from_point(self,event):
  self.setFocus();r=1-(event.position().y()-12)/max(1,self.height()-24) if self.vertical else (event.position().x()-12)/max(1,self.width()-24)
  self.setValue(round(self.minimum()+min(1,max(0,r))*(self.maximum()-self.minimum())))
 def mousePressEvent(self,event):
  if event.button()==Qt.MouseButton.LeftButton:self.setSliderDown(True);self.set_from_point(event)
 def mouseMoveEvent(self,event):
  if self.isSliderDown():self.set_from_point(event)
 def mouseReleaseEvent(self,event):self.setSliderDown(False)


class ThemeSwitch(QAbstractButton):
 def __init__(self,theme):
  super().__init__();self.theme=theme;self.position=0.;self.setCheckable(True);self.setFixedSize(92,40);self.setCursor(Qt.CursorShape.PointingHandCursor)
  self.setAccessibleName('Tema escuro');self.setToolTip('Alternar tema claro/escuro')
  self.anim=QVariantAnimation(self);self.anim.setDuration(360);self.anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
  self.anim.valueChanged.connect(self.frame);self.toggled.connect(self.animate);theme.changed.connect(self.update)
  theme.targetChanged.connect(self.setChecked)
 def keyPressEvent(self,event):
  if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):self.click();event.accept()
  else:super().keyPressEvent(event)
 def animate(self,dark):
  self.anim.stop();self.anim.setStartValue(self.position);self.anim.setEndValue(float(dark));self.anim.start()
 def frame(self,value):self.position=float(value);self.update()
 def paintEvent(self,event):
  p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);t=self.theme
  p.setPen(QPen(t.color('ACCENT' if self.hasFocus() else 'LINE'),1));p.setBrush(t.color('FIELD'));p.drawRoundedRect(QRectF(1,1,90,38),19,19)
  x=21+50*self.position;p.setPen(Qt.PenStyle.NoPen);p.setBrush(t.color('ACCENT'));p.drawEllipse(QPointF(x,20),16,16)
  for cx,dark in ((21,False),(71,True)):
   active=(not dark and self.position<.5) or (dark and self.position>=.5);color=t.color('ON_PRIMARY' if active else 'MUTED')
   p.setPen(QPen(color,1.6));p.setBrush(Qt.BrushStyle.NoBrush)
   if dark:
    # Crescent path is antialiased; no overlapping hard-edged bitmaps.
    from PySide6.QtGui import QPainterPath
    moon=QPainterPath();moon.addEllipse(QPointF(cx,20),7,7);cut=QPainterPath();cut.addEllipse(QPointF(cx+4,16),7,7)
    p.fillPath(moon.subtracted(cut),color)
   else:
    p.drawEllipse(QPointF(cx,20),4,4)
    for degrees in range(0,360,45):
     a=math.radians(degrees);p.drawLine(QPointF(cx+7*math.cos(a),20+7*math.sin(a)),QPointF(cx+10*math.cos(a),20+10*math.sin(a)))


class MousePreview(QWidget):
 def __init__(self,theme,settings):
  super().__init__();self.theme=theme;self.settings=settings;self.setMinimumSize(180,110)
  self.base=QImage(str(ROOT/'assets/x11-398.png'));self.mask=json.loads((ROOT/'assets/led-masks.json').read_text())['398'] if (ROOT/'assets/led-masks.json').exists() else None
  self.timer=QTimer(self);self.timer.timeout.connect(self.update);self.timer.start(32)
 def paintEvent(self,event):
  mode,color,speed=self.settings();rgb=QColor(color)
  phase=time.monotonic()/(7-speed)
  if mode=='off':rgb=QColor('#a3adb7')
  elif mode in ('neon','color-breathing'):rgb=QColor.fromHsvF(phase%1,.82,1)
  if mode in ('breathing','color-breathing','breathing-dpi'):rgb=mix('#e6edf5',rgb,.15+.85*(math.sin(phase*math.tau)+1)/2)
  if self.base.isNull() or self.mask is None:
   self.draw_community(rgb);return
  image=self.base.copy();m=self.mask
  for y,row in enumerate(m['rows']):
   for x,(r,g,b,alpha) in enumerate(row):image.setPixelColor(m['x']+x,m['y']+y,mix(QColor(r,g,b),rgb,alpha/255))
  scale=min((self.width()-16)/image.width(),(self.height()-16)/image.height(),1.)
  w,h=image.width()*scale,image.height()*scale
  p=QPainter(self);p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform);p.drawImage(QRectF((self.width()-w)/2,(self.height()-h)/2,w,h),image)

 def draw_community(self,led):
  # Original generic illustration for the freely distributable source tree.
  from PySide6.QtGui import QPainterPath
  scale=min((self.width()-30)/215,(self.height()-24)/365,1.)
  p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
  p.translate(self.width()/2,self.height()/2);p.scale(scale,scale)
  path=QPainterPath();path.moveTo(-85,-125);path.cubicTo(-90,-185,90,-185,85,-125)
  path.cubicTo(95,-25,105,155,0,169);path.cubicTo(-105,155,-95,-25,-85,-125);path.closeSubpath()
  p.setBrush(QColor('#f1f3f7'));p.setPen(QPen(QColor('#b3bdc9'),1.4));p.drawPath(path)
  p.drawLine(QPointF(0,-160),QPointF(0,-38));p.drawLine(QPointF(-84,-38),QPointF(84,-38))
  p.setBrush(QColor('#2c3342'));p.setPen(Qt.PenStyle.NoPen);p.drawRoundedRect(QRectF(-10,-140,20,65),8,8)
  p.setBrush(led);p.drawRoundedRect(QRectF(-8,-21,16,4),2,2)
  p.setPen(QColor('#8b96a7'));p.setFont(QFont('Google Sans',18));p.drawText(QRectF(-50,75,100,50),Qt.AlignmentFlag.AlignCenter,'X11')



def row(parent,spacing=12):
 l=QHBoxLayout(parent);l.setContentsMargins(0,0,0,0);l.setSpacing(spacing);return l


def column(parent,margin=0,spacing=12):
 l=QVBoxLayout(parent);l.setContentsMargins(margin,margin,margin,margin);l.setSpacing(spacing);return l


class ModernApplication(QMainWindow):
 def __init__(self,backend):
  super().__init__();from attack_shark_x11 import LIGHTING_MODES,VERSION,proto
  self.backend=backend;self.modes=LIGHTING_MODES;self.loaded=False;self.busy=False;self.syncing=False;self.close_pending=False;self.last_result={}
  self.have_speed=False;self.speed_dirty=False;self.controls=[];self.pages={};self.nav={};self.selected_id=None;self.items=[];self.store=ProfileStore();self.store_ok=True
  self.supported=sorted({dpi for dpi,code in proto._DPI_TABLE if proto.decode_dpi_candidates(code,int(10100<=dpi<=12000 or 20100<=dpi<=22000),dpi>12000,dpi>12000)==[dpi]})
  self.dpi_indices={value:i for i,value in enumerate(self.supported)}
  self.setWindowTitle('Tubarão Atacante · Attack Shark X11');self.resize(1120,820);self.setMinimumSize(1000,760)
  self.setWindowIcon(QIcon(str(ROOT/'branding/juliet-icon.png')))
  QFontDatabase.addApplicationFont(str(ROOT/'fonts/GoogleSans.ttf'));QApplication.instance().setFont(QFont('Google Sans',10))
  self.theme=Theme(self);self.theme.changed.connect(self.update_theme)
  QApplication.instance().setStyleSheet('''QLineEdit,QSpinBox,QComboBox {background:palette(base);border:1px solid palette(mid);border-radius:8px;padding:6px;selection-background-color:palette(highlight);} QListWidget,QTextEdit {background:transparent;border:0;} QListWidget::item {padding:7px;border-radius:8px;} QListWidget::item:selected {background:palette(button);color:palette(highlight);} QScrollBar:vertical {background:transparent;width:12px;margin:2px;} QScrollBar::handle:vertical {background:palette(mid);border-radius:4px;min-height:24px;margin:0 2px;} QScrollBar::handle:vertical:hover {background:palette(highlight);} QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;} QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {background:transparent;} QDialog,QMessageBox {background:palette(window);} QDialog QPushButton {background:palette(button);color:palette(button-text);border:0;border-radius:16px;padding:9px 18px;}''')
  shell=Card(self.theme,0,'BG');self.setCentralWidget(shell);outer=column(shell,0,0)
  header=Card(self.theme,0,'SIDE');outer.addWidget(header);head=QHBoxLayout(header);head.setContentsMargins(24,12,24,10)
  self.logo=BrandImage('juliet-header',self.theme);head.addWidget(self.logo);names=QWidget();names_l=column(names,0,3);self.wordmark=BrandImage('wordmark',self.theme);names_l.addWidget(self.wordmark);names_l.addWidget(Text('ATTACK SHARK X11',self.theme,8,role='MUTED'));head.addWidget(names);head.addStretch()
  self.connection=Text('○  Desconectado',self.theme,9,role='MUTED');head.addWidget(self.connection)
  self.connect=Button('Conectar',self.theme,self.refresh,True);head.addWidget(self.connect)
  navigation=Card(self.theme,0,'SIDE');outer.addWidget(navigation);nav_l=QHBoxLayout(navigation);nav_l.setContentsMargins(24,2,24,12)
  for key,title in [('overview','Mouse'),('dpi','DPI'),('lighting','Iluminação'),('profiles','Perfis')]:
   b=Button(title,self.theme,lambda checked=False,k=key:self.show_page(k));b.flat=True;nav_l.addWidget(b);self.nav[key]=b
  nav_l.addStretch();self.theme_caption=Text('',self.theme,8,role='MUTED');nav_l.addWidget(self.theme_caption)
  self.switch=ThemeSwitch(self.theme);self.switch.clicked.connect(lambda dark:self.select_theme('dark' if dark else 'light'));nav_l.addWidget(self.switch)
  self.auto=Button('Auto',self.theme,lambda:self.select_theme('system'));nav_l.addWidget(self.auto);nav_l.addWidget(Text('v'+VERSION,self.theme,8,role='MUTED'))
  body_outer=QWidget();body_row=row(body_outer,0);body_row.addStretch();self.body=QWidget();self.body.setMaximumWidth(1280);body_row.addWidget(self.body,1);body_row.addStretch();outer.addWidget(body_outer,1)
  body=column(self.body,24,12);self.heading=Text('',self.theme,21);body.addWidget(self.heading);self.subtitle=Text('',self.theme,9,role='MUTED');body.addWidget(self.subtitle)
  stat_widget=QWidget();stat=row(stat_widget,28);self.stat_labels=[]
  for title in ('DPI ativo','Polling','Iluminação'):
   label=Text(title+'  —',self.theme,10);self.stat_labels.append(label);stat.addWidget(label)
  stat.addStretch();body.addWidget(stat_widget)
  self.stack=QStackedWidget();body.addWidget(self.stack,1)
  footer_widget=QWidget();footer=row(footer_widget);self.message=Text('Conecte o mouse para carregar as configurações.',self.theme,9,role='MUTED');footer.addWidget(self.message,1);footer.addWidget(Button('Diagnóstico',self.theme,self.show_details));body.addWidget(footer_widget)
  self.stage_group=QButtonGroup(self);self.dpi_entries=[];self.dpi_sliders=[];self.color_buttons=[];self.colors=['#94a5ba']*6;self.polling_value=None;self.mode_key=None;self.global_color='#94a5ba';self.speed_value=3
  self.build_overview();self.build_dpi();self.build_lighting();self.build_profiles()
  self.show_page('overview');self.theme.publish();self.switch.setChecked(self.theme.target=='dark');self.switch.position=float(self.switch.isChecked());self.switch.anim.stop()
  self.reload_profiles();self.set_enabled()
 def reg(self,widget):self.controls.append(widget);return widget
 def card(self,title,subtitle='',width=None):
  c=Card(self.theme);l=column(c,20,10);l.addWidget(Text(title,self.theme,13,True))
  if subtitle:l.addWidget(Text(subtitle,self.theme,9,role='MUTED'))
  if width:c.setFixedWidth(width)
  return c,l
 def page(self,key):
  p=QWidget();self.pages[key]=p;self.stack.addWidget(p);return p
 def preview_card(self):
  c,l=self.card('Attack Shark X11','Receptor sem fio · 2.4 GHz');l.addWidget(MousePreview(self.theme,self.preview_settings),1);label=Text('Prévia da iluminação',self.theme,8,role='MUTED');label.setAlignment(Qt.AlignmentFlag.AlignCenter);l.addWidget(label);return c
 def build_overview(self):
  p=self.page('overview');l=row(p,16);left=QWidget();left.setFixedWidth(390);side=column(left,0,16);l.addWidget(left)
  card,c=self.card('Taxa de atualização','Defina a frequência de comunicação do mouse.');side.addWidget(card)
  rates=QWidget();r=row(rates,6);self.polling_buttons={}
  for hz in (125,250,500,1000):
   b=self.reg(Button(str(hz)+' Hz',self.theme,lambda checked=False,n=hz:self.choose_polling(n)));r.addWidget(b);self.polling_buttons[hz]=b
  c.addWidget(rates);self.polling_apply=self.reg(Button('Aplicar polling',self.theme,self.apply_polling,True));c.addWidget(self.polling_apply)
  card,c=self.card('Personalize seu X11','Ajuste a sensibilidade e encontre seu efeito.');side.addWidget(card)
  c.addWidget(Button('Estágios de DPI  →',self.theme,lambda:self.show_page('dpi')));c.addWidget(Button('Iluminação  →',self.theme,lambda:self.show_page('lighting')))
  side.addWidget(Text('As alterações são enviadas ao clicar em Aplicar.',self.theme,9,role='MUTED'));side.addStretch();l.addWidget(self.preview_card(),1)
 def build_dpi(self):
  p=self.page('dpi');vertical=column(p);panels=QWidget();l=row(panels,16);vertical.addWidget(panels,1)
  card,c=self.card('Estágios de DPI','Selecione o estágio ativo. Clique na cor para editar.');l.addWidget(card,1);preview=self.preview_card();preview.setFixedWidth(270);l.addWidget(preview)
  grid_widget=QWidget();grid=QGridLayout(grid_widget);grid.setContentsMargins(0,0,0,0);grid.setHorizontalSpacing(8);grid.setVerticalSpacing(6);c.addWidget(grid_widget,1);grid.setRowStretch(2,1)
  for i in range(6):
   grid.setColumnStretch(i,1);label=Text('DPI '+str(i+1),self.theme,9,role='MUTED');label.setAlignment(Qt.AlignmentFlag.AlignCenter);grid.addWidget(label,0,i)
   top=Text(str(self.supported[-1]),self.theme,8,role='MUTED');top.setAlignment(Qt.AlignmentFlag.AlignCenter);grid.addWidget(top,1,i)
   slider=self.reg(SmoothSlider(self.theme,True));slider.setRange(0,len(self.supported)-1);slider.valueChanged.connect(lambda v,n=i:self.dpi_moved(n,v));grid.addWidget(slider,2,i);self.dpi_sliders.append(slider)
   low=Text(str(self.supported[0]),self.theme,8,role='MUTED');low.setAlignment(Qt.AlignmentFlag.AlignCenter);grid.addWidget(low,3,i)
   entry=self.reg(QLineEdit());entry.setAlignment(Qt.AlignmentFlag.AlignCenter);entry.setMaximumWidth(90);entry.setMaxLength(7);entry.textEdited.connect(lambda v,n=i:self.dpi_typed(n,v));grid.addWidget(entry,4,i,alignment=Qt.AlignmentFlag.AlignHCenter);self.dpi_entries.append(entry)
   color=self.reg(Button('Cor',self.theme,lambda checked=False,n=i:self.choose_stage_color(n)));grid.addWidget(color,5,i);self.color_buttons.append(color)
   radio=self.reg(QRadioButton());self.stage_group.addButton(radio,i+1);grid.addWidget(radio,6,i,alignment=Qt.AlignmentFlag.AlignHCenter)
  bottom=QWidget();b=row(bottom);b.addWidget(Text('A cor fica visível nos modos Cor do DPI e Respiração do DPI.',self.theme,9,role='MUTED'),1)
  self.profile_apply=self.reg(Button('Aplicar estágios',self.theme,self.apply_dpi,True));b.addWidget(self.profile_apply);vertical.addWidget(bottom)
 def build_lighting(self):
  p=self.page('lighting');v=column(p);panels=QWidget();l=row(panels,16);v.addWidget(panels,1)
  card,c=self.card('Efeito de iluminação','Escolha um modo para personalizar o LED.');l.addWidget(card,1)
  grid_widget=QWidget();grid=QGridLayout(grid_widget);grid.setContentsMargins(0,0,0,0);self.mode_buttons={}
  for i,(key,spec) in enumerate(self.modes.items()):
   b=self.reg(Button(spec[1],self.theme,lambda checked=False,k=key:self.choose_mode(k)));b.setToolTip(spec[2]);grid.addWidget(b,i//2,i%2);self.mode_buttons[key]=b
  c.addWidget(grid_widget);speedrow=QWidget();sr=row(speedrow);sr.addWidget(Text('Velocidade',self.theme,10,True));sr.addStretch();self.speed_label=Text('—',self.theme,10,True,'ACCENT');sr.addWidget(self.speed_label);c.addWidget(speedrow)
  self.speed=self.reg(SmoothSlider(self.theme));self.speed.setRange(1,5);self.speed.setValue(3);self.speed.valueChanged.connect(self.speed_changed);c.addWidget(self.speed)
  hints=QWidget();r=row(hints);r.addWidget(Text('Lento',self.theme,8,role='MUTED'));r.addStretch();r.addWidget(Text('Rápido',self.theme,8,role='MUTED'));c.addWidget(hints);c.addStretch()
  card,c=self.card('Attack Shark X11','Prévia local do efeito selecionado.',300);l.addWidget(card);c.addWidget(MousePreview(self.theme,self.preview_settings),1)
  c.addWidget(Text('Cor global',self.theme,10,True));self.global_button=self.reg(Button('Escolher cor',self.theme,self.choose_global_color));c.addWidget(self.global_button);self.color_hint=Text('',self.theme,9,role='MUTED');c.addWidget(self.color_hint)
  bottom=QWidget();r=row(bottom);r.addWidget(Text('A prévia não altera o mouse. Use Aplicar para enviar o efeito.',self.theme,9,role='MUTED'),1);self.lighting_apply=self.reg(Button('Aplicar iluminação',self.theme,self.apply_lighting,True));r.addWidget(self.lighting_apply);v.addWidget(bottom)
 def build_profiles(self):
  p=self.page('profiles');l=row(p,16);card,c=self.card('Meus perfis','Salvos neste computador.',280);l.addWidget(card)
  self.profile_list=QListWidget();self.profile_list.currentRowChanged.connect(self.profile_selected);c.addWidget(self.profile_list,1);self.reload_button=Button('Atualizar lista',self.theme,self.reload_profiles);c.addWidget(self.reload_button)
  card,c=self.card('Configurações salvas','Aplicar envia o perfil salvo. Salve suas edições antes.');l.addWidget(card,1)
  toolbar=QWidget();r=row(toolbar,6);self.pbuttons={}
  for key,title,callback in [('new','Criar',self.new_profile),('duplicate','Duplicar',self.duplicate_profile),('rename','Renomear',self.rename_profile),('delete','Excluir',self.delete_profile)]:
   b=Button(title,self.theme,lambda checked=False,f=callback:self.guard(f));r.addWidget(b);self.pbuttons[key]=b
  c.addWidget(toolbar);self.summary=QTextEdit();self.summary.setReadOnly(True);c.addWidget(self.summary,1)
  self.pbuttons['save']=Button('Salvar ajustes atuais',self.theme,lambda:self.guard(self.save_profile));c.addWidget(self.pbuttons['save'])
  actions=QWidget();r=row(actions,8)
  for key,title,fn in [('load','Carregar para edição',self.load_profile),('apply','Aplicar ao mouse',self.apply_saved)]:
   b=Button(title,self.theme,lambda checked=False,f=fn:self.guard(f),key=='apply');r.addWidget(b,1);self.pbuttons[key]=b
  c.addWidget(actions)
 def update_theme(self):
  if not hasattr(self,'logo'):return
  if hasattr(self,'theme_caption'):
   self.theme_caption.setText(('Sistema · ' if self.theme.mode=='system' else '')+('Escuro' if self.theme.target=='dark' else 'Claro'))
   self.auto.selected=self.theme.mode=='system';self.auto.update()
 def select_theme(self,mode):self.guard(lambda:self.theme.select(mode))
 def show_page(self,key):
  headings={'overview':('Configurações do mouse','Ajuste seu X11 com tudo no lugar.'),'dpi':('Sensibilidade e cores','Configure os seis estágios e selecione qual deseja usar.'),'lighting':('Iluminação','Escolha o efeito, a velocidade e a cor.'),'profiles':('Perfis de configuração','Salve seus ajustes e escolha quando aplicá-los ao X11.')}
  self.stack.setCurrentWidget(self.pages[key]);self.heading.setText(headings[key][0]);self.subtitle.setText(headings[key][1])
  for k,b in self.nav.items():b.selected=k==key;b.update()
 def choose_polling(self,hz):
  self.polling_value=hz
  for value,b in self.polling_buttons.items():b.selected=value==hz;b.update()
 def dpi_moved(self,i,value):
  if not self.syncing:self.dpi_entries[i].setText(str(self.supported[value]))
 def dpi_typed(self,i,value):
  try:value=int(value)
  except ValueError:return
  if value in self.dpi_indices:
   blocker=QSignalBlocker(self.dpi_sliders[i]);self.dpi_sliders[i].setValue(self.dpi_indices[value])
 def choose_mode(self,key):self.mode_key=key;self.set_enabled()
 def speed_changed(self,value):
  self.speed_value=value
  if not self.syncing:self.speed_dirty=True
  self.speed_label.setText(str(value)+' / 5')
 def choose_stage_color(self,i):
  color=QColorDialog.getColor(QColor(self.colors[i]),self,'Cor do estágio '+str(i+1),QColorDialog.ColorDialogOption.DontUseNativeDialog)
  if color.isValid():self.colors[i]=color.name();self.paint_colors()
 def choose_global_color(self):
  color=QColorDialog.getColor(QColor(self.global_color),self,'Cor da iluminação',QColorDialog.ColorDialogOption.DontUseNativeDialog)
  if color.isValid():self.global_color=color.name();self.paint_colors()
 def paint_colors(self):
  for i,b in enumerate(self.color_buttons):b.swatch=self.colors[i];b.setText(self.colors[i]);b.update()
  self.global_button.swatch=self.global_color;self.global_button.setText(self.global_color);self.global_button.update()
 def preview_settings(self):
  stage=max(1,self.stage_group.checkedId())
  return (self.mode_key if self.loaded else 'off',self.colors[stage-1] if self.mode_key in ('static-dpi','breathing-dpi') else self.global_color,self.speed_value)
 def set_enabled(self):
  ready=self.loaded and not self.busy
  self.connect.setEnabled(not self.busy);self.connect.setText('Atualizando…' if self.busy else 'Atualizar' if self.loaded else 'Conectar')
  for w in self.controls:w.setEnabled(ready)
  if hasattr(self,'speed'):
   self.lighting_apply.setEnabled(ready and self.mode_key in self.modes)
   animated=self.mode_key in ('breathing','neon','color-breathing','breathing-dpi');self.speed.setEnabled(ready and animated);self.global_button.setEnabled(ready and self.mode_key in ('static','breathing'))
   for key,b in self.mode_buttons.items():b.selected=key==self.mode_key;b.update()
   self.color_hint.setText('Usa a cor do estágio ativo. Edite as cores na aba DPI.' if self.mode_key in ('static-dpi','breathing-dpi') else 'O efeito percorre suas próprias cores.' if self.mode_key in ('neon','color-breathing') else 'LED desligado; as cores são preservadas.' if self.mode_key=='off' else 'Cor global usada nos modos Estático e Respiração.')
  if hasattr(self,'pbuttons'):
   for key,b in self.pbuttons.items():b.setEnabled(self.store_ok and not self.busy and (self.selected_id is not None or key=='new') and (self.loaded or key in ('duplicate','rename','delete')))
   self.profile_list.setEnabled(not self.busy);self.reload_button.setEnabled(not self.busy)
 def guard(self,fn):
  try:return fn()
  except (OSError,ValueError,RuntimeError) as exc:self.message.setText(str(exc))
 def run(self,operation):
  if self.busy:return
  self.busy=True;self.set_enabled();self.message.setText('Comunicando com o X11…');self.task=Task(operation)
  self.task.signals.result.connect(self.result);self.task.signals.error.connect(self.error);QThreadPool.globalInstance().start(self.task)
 def result(self,data):
  self.busy=False;self.display(data);self.set_enabled()
  if self.close_pending:self.close()
 def error(self,error):
  self.busy=False;self.loaded=False;self.last_result={'status':'error','error':error};self.connection.setText('○  Sem conexão');self.message.setText(error);self.set_enabled()
  if self.close_pending:self.close()
 def refresh(self):self.run(lambda:self.backend.status(include_lighting=True))
 def display(self,data):
  self.syncing=True
  try:
   self.loaded=True;self.last_result=data;self.connection.setText('●  Conectado · 2.4 GHz');self.choose_polling(data['polling_hz']);config=data['configuration'];stage=config.get('active_stage_candidate')
   if stage in range(1,7):self.stage_group.button(stage).setChecked(True)
   for i,item in enumerate(config['stages'][:6]):
    values=item['dpi_candidates'];self.dpi_entries[i].setText(str(values[0]) if len(values)==1 else ' / '.join(map(str,values)))
    if len(values)==1 and values[0] in self.dpi_indices:self.dpi_sliders[i].setValue(self.dpi_indices[values[0]])
    self.colors[i]='#%02x%02x%02x'%tuple(item['rgb_candidate'])
   lighting=data.get('lighting')
   if lighting:
    self.mode_key=lighting.get('mode_key');self.have_speed=lighting.get('speed') in range(1,6);self.speed_dirty=False
    if self.have_speed:self.speed.setValue(lighting['speed']);self.speed_value=lighting['speed']
    self.speed_label.setText(str(self.speed_value)+' / 5' if self.have_speed else 'Preservar');self.global_color=lighting['global_color'];self.stat_labels[2].setText('Iluminação  '+lighting['mode_name'])
   active=config['stages'][stage-1]['dpi_candidate'] if stage in range(1,7) else None
   self.stat_labels[0].setText('DPI ativo  '+(str(active) if active else '—'));self.stat_labels[1].setText('Polling  '+str(data['polling_hz'])+' Hz');self.paint_colors()
  finally:self.syncing=False
  status=data['status'];self.message.setText('Configuração confirmada pela releitura. Cópia anterior salva.' if status=='verified' else 'O mouse respondeu com diferenças. Consulte o diagnóstico.' if status=='verification_mismatch' else 'Esses valores já estavam configurados.' if status=='unchanged' else 'Configurações carregadas. Escolha seus ajustes e clique em Aplicar.')
  if data.get('saved_profile_name') and status in ('verified','unchanged'):self.message.setText('Perfil “'+data['saved_profile_name']+'” confirmado no mouse.')
  self.set_enabled()
 def apply_polling(self):
  hz=self.polling_value;self.guard(lambda:self.run(lambda:self.backend.set_polling(hz)))
 def apply_dpi(self):
  def action():
   from attack_shark_x11 import encode_dpi
   stage=self.stage_group.checkedId();dpis={i+1:int(v.text()) for i,v in enumerate(self.dpi_entries)};colors=dict(enumerate(self.colors,1))
   for v in dpis.values():encode_dpi(v)
   self.run(lambda:self.backend.set_profile(stage=stage,dpis=dpis,colors=colors,preserve_lighting=True))
  self.guard(action)
 def apply_lighting(self):
  mode=self.mode_key;speed=self.speed_value if mode in ('breathing','neon','color-breathing','breathing-dpi') and (self.have_speed or self.speed_dirty) else None;color=self.global_color if mode in ('static','breathing') else None
  self.run(lambda:self.backend.set_lighting(mode=mode,speed=speed,rgb=color))
 def current_settings(self):
  if not self.loaded:raise ValueError('Conecte o mouse antes de salvar os ajustes.')
  return validate_settings({'stage':self.stage_group.checkedId(),'dpis':[int(v.text()) for v in self.dpi_entries],'colors':list(self.colors),'polling_hz':self.polling_value,'lighting':{'mode':self.mode_key,'speed':self.speed_value if self.have_speed or self.speed_dirty else None,'color':self.global_color}})
 def reload_profiles(self,select_id=None):
  # clicked(bool) must not be interpreted as an ID.
  if isinstance(select_id,bool):select_id=None
  try:self.items=self.store.list();self.store_ok=True
  except (OSError,ValueError) as exc:self.items=[];self.store_ok=False;self.message.setText(str(exc))
  previous=select_id or self.selected_id;block=QSignalBlocker(self.profile_list);self.profile_list.clear();self.profile_list.addItems([p['name'] for p in self.items]);index=next((i for i,p in enumerate(self.items) if p['id']==previous),0);self.profile_list.setCurrentRow(index if self.items else -1);del block;self.profile_selected()
 def profile_selected(self,index=None):
  index=self.profile_list.currentRow();item=self.items[index] if 0<=index<len(self.items) else None;self.selected_id=item['id'] if item else None
  text='Crie seu primeiro perfil a partir dos ajustes atuais.\n\nConecte o X11 para carregar as configurações.'
  if item:
   s=item['settings'];light=s['lighting'];text=item['name']+'\n\nPolling: %s Hz · Estágio ativo: %s\n\n'%(s['polling_hz'],s['stage'])
   text+='\n'.join('DPI %s: %s  %s     |     DPI %s: %s  %s'%(i+1,s['dpis'][i],s['colors'][i],i+2,s['dpis'][i+1],s['colors'][i+1]) for i in (0,2,4))
   text+='\n\nIluminação: '+self.modes[light['mode']][1]+'\nCor global: '+light['color']+' · Velocidade: '+(str(light['speed']) if light['speed'] is not None else 'preservar')
  elif not self.store_ok:text='Não foi possível ler os perfis. O arquivo foi preservado. Corrija o arquivo e atualize a lista.'
  self.summary.setPlainText(text);self.set_enabled()
 def create_profile(self,name):
  item=self.store.create(name,self.current_settings());self.reload_profiles(item['id']);self.message.setText('Perfil salvo neste computador. Mouse não alterado.');return item
 def new_profile(self):
  name,ok=QInputDialog.getText(self,'Criar perfil','Nome do perfil (salva os ajustes exibidos):')
  if ok:self.create_profile(name)
 def duplicate_profile(self):
  item=self.store.get(self.selected_id);name,ok=QInputDialog.getText(self,'Duplicar perfil','Nome da cópia:',text=item['name'][:54]+' (cópia)')
  if ok:new=self.store.duplicate(item['id'],name);self.reload_profiles(new['id'])
 def rename_profile(self):
  item=self.store.get(self.selected_id);name,ok=QInputDialog.getText(self,'Renomear perfil','Novo nome:',text=item['name'])
  if ok:self.store.update(item['id'],name=name);self.reload_profiles(item['id'])
 def delete_profile(self):
  item=self.store.get(self.selected_id)
  if QMessageBox.question(self,'Excluir perfil','Excluir “'+item['name']+'” deste computador?')==QMessageBox.StandardButton.Yes:
   self.store.delete(item['id']);self.reload_profiles();self.message.setText('Perfil local excluído. Mouse não alterado.')
 def save_profile(self):
  item=self.store.get(self.selected_id);settings=self.current_settings()
  if QMessageBox.question(self,'Atualizar perfil','Substituir “'+item['name']+'” pelos ajustes atuais da tela?')==QMessageBox.StandardButton.Yes:
   self.store.update(item['id'],settings=settings);self.reload_profiles(item['id']);self.message.setText('Perfil atualizado neste computador. Mouse não alterado.')
 def load_profile(self):
  if not self.loaded:raise ValueError('Conecte o mouse para editar este perfil.')
  item=self.store.get(self.selected_id);s=item['settings'];self.syncing=True
  try:
   self.stage_group.button(s['stage']).setChecked(True);self.choose_polling(s['polling_hz'])
   for i,value in enumerate(s['dpis']):self.dpi_entries[i].setText(str(value));self.dpi_sliders[i].setValue(self.dpi_indices[value])
   self.colors=list(s['colors']);self.mode_key=s['lighting']['mode'];self.global_color=s['lighting']['color'];self.have_speed=s['lighting']['speed'] is not None;self.speed_dirty=False
   if self.have_speed:self.speed.setValue(s['lighting']['speed']);self.speed_value=s['lighting']['speed']
   self.speed_label.setText(str(self.speed_value)+' / 5' if self.have_speed else 'Preservar');self.paint_colors()
  finally:self.syncing=False
  self.set_enabled();self.message.setText('“'+item['name']+'” carregado para edição. Mouse não alterado.')
 def apply_saved(self):
  if not self.loaded:raise ValueError('Conecte o mouse para aplicar um perfil.')
  item=self.store.get(self.selected_id)
  def operation():
   result=self.backend.apply_saved_profile(item['settings']);result['saved_profile_name']=item['name'];return result
  self.run(operation)
 def show_details(self):
  dialog=QDialog(self);dialog.setWindowTitle('Diagnóstico');dialog.resize(760,480);l=column(dialog,20);text=QTextEdit();text.setReadOnly(True);data=json.dumps(self.last_result,ensure_ascii=False,indent=2);text.setPlainText(data);l.addWidget(text);l.addWidget(Button('Copiar diagnóstico',self.theme,lambda:QApplication.clipboard().setText(data)));dialog.exec()
 def closeEvent(self,event):
  if self.busy:self.close_pending=True;self.message.setText('Concluindo a operação antes de fechar…');event.ignore()
  else:event.accept()


def launch(backend):
 app=QApplication.instance() or QApplication([]);app.setApplicationName('Tubarão Atacante');app.setStyle('Fusion')
 window=ModernApplication(backend);window.show();return app.exec()
