"""Offline macro editor: no receiver, input injection or execution backend."""
import copy
from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import (QWidget,QLineEdit,QListWidget,
 QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QMessageBox,QStackedWidget,QRadioButton,QButtonGroup,QDialog,QInputDialog)
from x11_macros import MAX_STEPS,MAX_REPEATS,MAX_DELAY_MS,MacroStore,summary,MODES,validate_macro,complete_macro,IncompleteMacroError
from x11_macro_recorder import RecordingDialog,step_value
from x11_number_field import NumberField


class MacroPage(QWidget):
 def __init__(self,window):
  from x11_ui import Button,Text,row,column
  super().__init__();self.window=window;self.store=MacroStore()
  self.items=[];self.steps=[];self.macro_id=None;self.dirty=False;self.loading=False;self.target_button=None
  from x11_button_map import ButtonAssignments
  outer=column(self,0,8);toolbar=QWidget();r=row(toolbar,8)
  self.map_button=Button('Botões do mouse',window.theme,lambda:self.show_view(0));r.addWidget(self.map_button)
  self.editor_button=Button('Editar macros',window.theme,lambda:self.show_view(1));r.addWidget(self.editor_button);r.addStretch();outer.addWidget(toolbar)
  self.views=QStackedWidget();outer.addWidget(self.views,1)
  self.assignments=ButtonAssignments(window,self.store,self.begin_for_button);self.views.addWidget(self.assignments)
  editor_page=QWidget();self.views.addWidget(editor_page)
  layout=row(editor_page,16);card,left=window.card('Minhas macros','Salvas neste computador.',230);layout.addWidget(card)
  self.list=QListWidget();self.list.setAccessibleName('Macros salvas');self.list.currentRowChanged.connect(self.select);left.addWidget(self.list,1)
  left.addWidget(Button('Nova macro',window.theme,self.new))
  self.delete_button=Button('Excluir macro',window.theme,self.delete);left.addWidget(self.delete_button)
  left.addWidget(Button('Atualizar lista',window.theme,self.reload))
  card,editor=window.card('Grave, revise e salve sua macro');layout.addWidget(card,1)
  fields=QWidget();r=row(fields,8)
  self.name=QLineEdit();self.name.setPlaceholderText('Nome da macro');self.name.setAccessibleName('Nome da macro');self.name.setMaxLength(64);r.addWidget(self.name,1)
  r.addWidget(Text('Repetições',window.theme,9));self.repeats=NumberField(window.theme);self.repeats.setFixedWidth(130);self.repeats.setRange(1,MAX_REPEATS);self.repeats.setAccessibleName('Repetições');r.addWidget(self.repeats);editor.addWidget(fields)
  self.name.textChanged.connect(self.changed);self.repeats.valueChanged.connect(self.changed)
  modes=QWidget();r=row(modes,6);self.mode_group=QButtonGroup(self);self.mode_buttons={}
  for value,label in MODES.items():
   radio=QRadioButton(label);radio.setAccessibleName('Execução: '+label);self.mode_group.addButton(radio);self.mode_buttons[value]=radio;r.addWidget(radio);radio.toggled.connect(self.mode_changed)
  self.mode_buttons['once'].setChecked(True);editor.addWidget(modes)
  self.table=QTableWidget(0,2);self.table.setAccessibleName('Passos da macro');self.table.setHorizontalHeaderLabels(['Ação','Tecla / atraso'])
  self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
  self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
  self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.table.setShowGrid(False);self.table.setMinimumHeight(65);editor.addWidget(self.table,1)
  builder=QWidget();r=row(builder,6)
  self.record_button=Button('Gravar ações',window.theme,self.record);r.addWidget(self.record_button)
  self.delay=NumberField(window.theme);self.delay.setRange(1,MAX_DELAY_MS);self.delay.setValue(100);self.delay.setSuffix(' ms');self.delay.setAccessibleName('Atraso em milissegundos');r.addWidget(self.delay,1)
  r.addWidget(Button('Inserir atraso',window.theme,lambda:self.add({'action':'wait','ms':self.delay.value()})));editor.addWidget(builder)
  order=QWidget();r=row(order,6)
  self.up=Button('Subir',window.theme,lambda:self.move(-1));self.down=Button('Descer',window.theme,lambda:self.move(1));self.remove=Button('Remover',window.theme,self.remove_step)
  self.edit_button=Button('Editar evento',window.theme,self.edit_event)
  for button in (self.up,self.down,self.remove,self.edit_button):r.addWidget(button)
  self.save_button=Button('Salvar macro',window.theme,self.request_save,True);r.addWidget(self.save_button);editor.addWidget(order)
  self.table.itemSelectionChanged.connect(self.update_actions)
  self.state=Text('',window.theme,9,role='MUTED');self.state.setWordWrap(True);editor.addWidget(self.state)
  self.reload();self.render();self.show_view(0)
 def show_view(self,index):
  self.views.setCurrentIndex(index);self.map_button.selected=index==0;self.editor_button.selected=index==1;self.map_button.update();self.editor_button.update()
  if index==0:self.assignments.refresh()
 def mode_changed(self,*_):
  self.repeats.setEnabled(self.mode_buttons['repeat'].isChecked())
  if hasattr(self,'state') and any(b.isChecked() for b in self.mode_buttons.values()):self.changed()
 def data(self):return {'steps':copy.deepcopy(self.steps),'repeats':self.repeats.value(),'mode':next(k for k,b in self.mode_buttons.items() if b.isChecked())}
 def begin_for_button(self,number):
  if self.new() is False:return
  self.target_button=number;self.show_view(1);self.save_button.setText(f'Salvar → botão {number}')
  self.window.message.setText(f'Crie e grave a macro para o botão {number}.')
 def record(self):
  dialog=RecordingDialog(self)
  if dialog.exec()==QDialog.DialogCode.Accepted:self.insert_recording(dialog.recorder.steps)
 def insert_recording(self,steps):
  if len(self.steps)+len(steps)>MAX_STEPS:
   self.window.message.setText(f'A gravação excederia o limite de {MAX_STEPS} eventos.');return
  row=self.table.currentRow();index=row+1 if row>=0 else len(self.steps)
  self.steps[index:index]=copy.deepcopy(steps);self.dirty=True;self.render(index)
 def edit_event(self):
  index=self.table.currentRow()
  if not 0<=index<len(self.steps):return
  current=self.steps[index]
  if current['action']=='wait':
   value,ok=QInputDialog.getInt(self,'Editar atraso','Atraso em milissegundos:',current['ms'],1,MAX_DELAY_MS)
   if not ok:return
   step={'action':'wait','ms':value}
  else:
   dialog=RecordingDialog(self);dialog.setWindowTitle('Regravar evento selecionado')
   if dialog.exec()!=QDialog.DialogCode.Accepted:return
   step=next((copy.deepcopy(s) for s in dialog.recorder.steps if s['action']!='wait'),None)
   if step is None:return
   release=current['action'] in ('release','mouse_release')
   if step['action'] in ('press','release'):step['action']='release' if release else 'press'
   elif step['action'] in ('mouse_press','mouse_release'):step['action']='mouse_release' if release else 'mouse_press'
  self.steps[index]=step;self.dirty=True;self.render(index)
 def changed(self,*_):
  if not self.loading:self.dirty=True;self.update_summary()
 def update_summary(self):
  try:
   info=summary(self.data());text=f"{info['steps']} passos · {info['repeats']} repetição(ões) · {info['delay_ms']} ms de atrasos"
  except ValueError as exc:text=str(exc)
  self.state.setText(('Alterações não salvas · ' if self.dirty else '')+text)
 def discard(self):
  if not self.dirty:return True
  return QMessageBox.question(self,'Alterações não salvas','Descartar as alterações desta macro?',QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)==QMessageBox.StandardButton.Discard
 def reload(self):
  # Refreshing the saved list never replaces the current draft.
  try:self.items=self.store.list()
  except (ValueError,OSError) as exc:self.window.message.setText(str(exc));return
  block=QSignalBlocker(self.list);self.list.clear();self.list.addItems([m['name'] for m in self.items]);self.list.setCurrentRow(next((i for i,m in enumerate(self.items) if m['id']==self.macro_id),-1));del block
  self.update_actions()
  self.assignments.refresh()
 def select(self,index):
  if not 0<=index<len(self.items):return
  if not self.discard():
   block=QSignalBlocker(self.list);self.list.setCurrentRow(next((i for i,m in enumerate(self.items) if m['id']==self.macro_id),-1));del block;return
  item=self.items[index];self.loading=True;self.macro_id=item['id'];self.target_button=None;self.save_button.setText('Salvar macro');self.name.setText(item['name']);self.repeats.setValue(item['macro']['repeats']);self.mode_buttons[item['macro'].get('mode','repeat' if item['macro']['repeats']>1 else 'once')].setChecked(True);self.steps=copy.deepcopy(item['macro']['steps']);self.loading=False;self.dirty=False;self.render()
 def new(self):
  if not self.discard():return False
  self.loading=True;self.macro_id=None;self.target_button=None;self.save_button.setText('Salvar macro');self.name.clear();self.steps=[];self.repeats.setValue(1);self.mode_buttons['once'].setChecked(True)
  block=QSignalBlocker(self.list);self.list.setCurrentRow(-1);del block
  self.loading=False;self.dirty=False;self.render();self.name.setFocus()
 def add(self,step):
  if len(self.steps)>=MAX_STEPS:self.window.message.setText(f'Limite do editor: {MAX_STEPS} passos.');return
  index=self.table.currentRow();index=index+1 if index>=0 else len(self.steps);self.steps.insert(index,step);self.dirty=True;self.render(index)
 def remove_step(self):
  index=self.table.currentRow()
  if 0<=index<len(self.steps):self.steps.pop(index);self.dirty=True;self.render(min(index,len(self.steps)-1))
 def move(self,direction):
  index=self.table.currentRow();target=index+direction
  if 0<=index<len(self.steps) and 0<=target<len(self.steps):self.steps[index],self.steps[target]=self.steps[target],self.steps[index];self.dirty=True;self.render(target)
 def render(self,selected=-1):
  labels={'press':'Pressionar tecla','release':'Soltar tecla','wait':'Aguardar (ms)','mouse_press':'Pressionar botão','mouse_release':'Soltar botão','wheel':'Rolar'};self.table.setRowCount(len(self.steps))
  for i,step in enumerate(self.steps):
   self.table.setItem(i,0,QTableWidgetItem(labels[step['action']]))
   self.table.setItem(i,1,QTableWidgetItem(step_value(step)))
  if selected>=0:self.table.selectRow(selected)
  self.update_actions();self.update_summary()
 def update_actions(self):
  row=self.table.currentRow();selected=0<=row<len(self.steps)
  self.up.setEnabled(selected and row>0);self.down.setEnabled(selected and row+1<len(self.steps));self.remove.setEnabled(selected);self.edit_button.setEnabled(selected);self.delete_button.setEnabled(self.macro_id is not None)
 def save(self):
  item=self.store.save(self.name.text(),self.data(),self.macro_id,button=self.target_button);self.macro_id=item['id'];self.loading=True;self.name.setText(item['name']);self.loading=False;self.dirty=False;self.reload();self.update_summary()
  self.window.message.setText(f'Macro salva e associada localmente ao botão {self.target_button}. Ainda não aplicada ao mouse.' if self.target_button else 'Macro salva neste computador.');return item
 def request_save(self):
  try:
   try:validate_macro(self.data())
   except IncompleteMacroError:
    candidate=complete_macro(self.data())
    releases=candidate['steps'][len(self.steps):]
    names=', '.join(step_value(step) for step in releases)
    answer=QMessageBox.question(self,'Concluir combinação e salvar?',
     'A sequência contém teclas ou botões pressionados sem soltura.\n\n'
     f'Adicionar as solturas de {names}, nessa ordem, ao final e salvar a macro?',
     QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)
    if answer!=QMessageBox.StandardButton.Yes:return
    self.steps=candidate['steps'];self.dirty=True;self.render()
   item=self.save()
   self.state.setText('Macro salva localmente. A execução no mouse ainda não está disponível.')
   if self.target_button is not None:
    self.show_view(0);self.assignments.map.calls[self.target_button].setFocus()
   return item
  except (ValueError,OSError) as exc:
   self.window.message.setText('Macro não salva: '+str(exc))
   QMessageBox.warning(self,'Macro não salva',str(exc))
 def delete(self):
  if self.macro_id is None:return
  if QMessageBox.question(self,'Excluir macro','Excluir esta macro, suas atribuições locais e descartar a edição?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
  def operation():
   self.store.delete(self.macro_id);self.dirty=False;self.new();self.reload();self.window.message.setText('Macro local excluída.')
  self.window.guard(operation)
