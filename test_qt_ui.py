"""Portable offscreen tests for the Qt migration. No hardware required."""
import contextlib,os,tempfile,unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
 from PySide6.QtCore import Qt,QPoint
 from PySide6.QtGui import QColor,QPalette
 from PySide6.QtTest import QTest
 from PySide6.QtWidgets import QApplication,QMessageBox
 from x11_ui import ModernApplication,Button
 HAS_QT=True
except ImportError:HAS_QT=False
import attack_shark_x11 as core
from test_lighting import LightingReceiver

@unittest.skipUnless(HAS_QT,'PySide6 não instalado; testes de backend continuam disponíveis.')
class QtInterfaceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.app=QApplication.instance() or QApplication([]);cls.app.setStyle('Fusion')
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  env=patch.dict(os.environ,{'XDG_CONFIG_HOME':self.tmp.name});env.start();self.addCleanup(env.stop)
  system=patch('x11_ui.system_theme',return_value='light');system.start();self.addCleanup(system.stop)
  self.receiver=LightingReceiver();self.backend=core.X11(session_factory=lambda:contextlib.nullcontext(self.receiver),backup_fn=lambda *args:'/simulated/backup.json')
  self.w=ModernApplication(self.backend);self.w.show();QTest.qWait(40)
 def tearDown(self):self.w.close();self.w.deleteLater();QTest.qWait(30)
 def finish(self):
  for _ in range(200):
   QTest.qWait(5)
   if not self.w.busy:return
  self.fail('Operação não terminou')
 def test_connection_and_async_read(self):
  self.assertFalse(self.w.profile_apply.isEnabled())
  self.w.refresh();self.finish();self.assertTrue(self.w.loaded)
  self.assertTrue(self.w.profile_apply.isEnabled());self.assertFalse(self.receiver.writes)
 def test_local_profiles_then_explicit_apply(self):
  self.w.display(self.backend.status(include_lighting=True));item=self.w.create_profile('Teste')
  s=item['settings'];s['polling_hz']=500;self.w.store.update(item['id'],settings=s);self.w.reload_profiles(item['id'])
  before=dict(self.receiver.frames);self.w.load_profile();self.assertEqual(before,self.receiver.frames)
  self.assertIn('1000',self.w.stat_labels[1].text())
  self.w.apply_saved();self.finish();self.assertEqual(self.w.last_result['status'],'verified');self.assertEqual(self.w.last_result['polling_hz'],500)
 def test_whole_theme_and_switch_have_intermediate_states(self):
  samples=[];self.w.theme.animation.valueChanged.connect(lambda value:samples.append(float(value)))
  QTest.mouseClick(self.w.switch,Qt.MouseButton.LeftButton);QTest.qWait(90)
  self.assertGreater(self.w.switch.position,0);self.assertLess(self.w.switch.position,1)
  self.assertNotIn(self.w.theme.color('BG').name(),('#f3f6fb','#282a36'))
  QTest.qWait(400);self.assertEqual(self.w.theme.color('BG').name(),'#282a36')
  self.assertEqual(self.w.dpi_entries[0].palette().color(QPalette.Text).name(),'#f8f8f2')
  self.assertGreaterEqual(len(set(samples)),5)
 def test_rapid_reversal_preserves_current_position(self):
  self.w.select_theme('dark');QTest.qWait(100);position=self.w.switch.position
  self.w.select_theme('light');self.assertAlmostEqual(position,self.w.switch.position,delta=.03)
  QTest.qWait(400);self.assertEqual(self.w.switch.position,0)
 def test_appearance_does_not_change_hardware_or_drafts(self):
  self.w.display(self.backend.status(include_lighting=True));self.w.dpi_entries[0].setText('800');before=dict(self.receiver.frames);colors=list(self.w.colors)
  self.w.select_theme('dark');QTest.qWait(400);self.w.select_theme('light');QTest.qWait(400)
  self.assertEqual(self.receiver.frames,before);self.assertEqual(self.w.dpi_entries[0].text(),'800');self.assertEqual(self.w.colors,colors)
 def test_switch_keyboard_enter(self):
  QTest.keyClick(self.w.switch,Qt.Key.Key_Return);QTest.qWait(400);self.assertTrue(self.w.switch.isChecked())
 def test_layout_controls_visible_at_minimum_size(self):
  self.w.resize(1000,760);QTest.qWait(40)
  for key,page in self.w.pages.items():
   self.w.show_page(key);QTest.qWait(20)
   for button in page.findChildren(Button):
    if button.isVisible():self.assertLessEqual(button.mapTo(page,QPoint(0,0)).y()+button.height(),page.height()+1,(key,button.text()))
 def test_button_edges_are_blended(self):
  button=self.w.nav['dpi'];self.w.show_page('dpi');QTest.qWait(30);image=button.grab().toImage()
  colors={image.pixelColor(x,y).rgb() for y in range(1,12) for x in range(1,14)}
  self.assertGreater(len(colors),5)
 def test_macros_work_offline_without_receiver_access(self):
  page=self.w.macros;self.w.show_page('macros')
  self.assertFalse(self.w.loaded)
  with patch.object(self.backend,'status',side_effect=AssertionError('hardware access')):
   page.name.setText('Copiar');page.add({'action':'press','key':'C'})
   with self.assertRaises(ValueError):page.save()
   page.add({'action':'wait','ms':100});page.add({'action':'release','key':'C'})
   item=page.save();self.assertEqual(len(page.store.list()),1)
   page.new();page.list.setCurrentRow(0)
   self.assertEqual(page.macro_id,item['id']);self.assertEqual(len(page.steps),3)
  self.assertFalse(self.receiver.writes);self.assertFalse(self.w.loaded)
 def test_macro_reorder_remove_and_cancel_preserve_draft(self):
  page=self.w.macros;page.name.setText('Teste')
  page.add({'action':'press','key':'C'});page.add({'action':'release','key':'C'});page.save()
  page.table.selectRow(1);page.move(-1);self.assertEqual(page.steps[0]['action'],'release')
  page.remove_step();self.assertEqual(len(page.steps),1)
  with patch('x11_macro_ui.QMessageBox.question',return_value=QMessageBox.StandardButton.Cancel):
   page.new();self.assertEqual(len(page.steps),1)
   self.assertFalse(self.w.close())
  page.dirty=False
 def test_button_map_click_and_keyboard_assign_saved_macros(self):
  from PySide6.QtWidgets import QDialog
  from test_macros import MACRO
  self.w.show_page('macros');view=self.w.macros.assignments
  item=view.store.save('Minha sequência',MACRO)
  def choose(dialog):
   dialog.macros.setCurrentRow(0);dialog.assign_selected();return QDialog.DialogCode.Accepted
  with patch('x11_button_map.AssignmentDialog.exec',new=choose):
   QTest.mouseClick(view.map.calls[4],Qt.MouseButton.LeftButton)
  self.assertEqual(view.store.assignments()['4'],item['id'])
  with patch('x11_button_map.AssignmentDialog.exec',new=choose):
   view.map.calls[5].setFocus();QTest.keyClick(view.map.calls[5],Qt.Key.Key_Space)
  self.assertEqual(view.store.assignments()['5'],item['id']);self.assertFalse(self.receiver.writes)
 def test_number_hotspot_cancel_preserves_bindings(self):
  from PySide6.QtWidgets import QDialog
  self.w.show_page('macros');view=self.w.macros.assignments
  before=view.store.assignments();_,points=view.map.geometry_data()
  with patch('x11_button_map.AssignmentDialog.exec',return_value=QDialog.DialogCode.Rejected) as dialog:
   QTest.mouseClick(view.map,Qt.MouseButton.LeftButton,pos=points[3].toPoint())
  dialog.assert_called_once();self.assertEqual(before,view.store.assignments())
 def test_button_map_and_editor_fit_minimum_window(self):
  self.w.resize(1000,760);self.w.show_page('macros');QTest.qWait(30)
  scene=self.w.macros.assignments.map
  for a,b in ((1,4),(4,5),(2,3)):
   self.assertFalse(scene.calls[a].geometry().intersects(scene.calls[b].geometry()))
  for call in scene.calls.values():self.assertTrue(scene.rect().contains(call.geometry()))
  self.w.macros.show_view(1);QTest.qWait(30)
  editor=self.w.macros
  self.assertLess(editor.table.geometry().bottom(),editor.record_button.parentWidget().geometry().top())

 def test_create_from_map_record_save_and_assign_without_dropdown(self):
  from PySide6.QtWidgets import QDialog,QComboBox
  from test_macros import MACRO
  from x11_button_map import AssignmentDialog
  self.w.show_page('macros');page=self.w.macros
  dialog=AssignmentDialog(4,[],None)
  self.assertEqual(dialog.findChildren(QComboBox),[]);dialog.close()
  def create(dialog):dialog.create();return QDialog.DialogCode.Accepted
  with patch('x11_button_map.AssignmentDialog.exec',new=create):
   QTest.mouseClick(page.assignments.map.calls[4],Qt.MouseButton.LeftButton)
  self.assertEqual(page.views.currentIndex(),1);self.assertEqual(page.target_button,4)
  self.assertEqual(page.findChildren(QComboBox),[])
  page.name.setText('Minha gravação');page.insert_recording(MACRO['steps'])
  page.mode_buttons['hold'].setChecked(True);self.assertEqual(page.data()['mode'],'hold')
  item=page.save();self.assertEqual(page.store.assignments()['4'],item['id'])
  self.assertEqual(page.store.list()[0]['macro']['mode'],'hold');self.assertFalse(self.receiver.writes)
 def test_edit_delay_and_cancel_recording_preserve_draft(self):
  from PySide6.QtWidgets import QDialog
  page=self.w.macros;page.add({'action':'wait','ms':100});page.table.selectRow(0)
  with patch('x11_macro_ui.QInputDialog.getInt',return_value=(500,True)):page.edit_event()
  self.assertEqual(page.steps[0]['ms'],500)
  before=list(page.steps)
  with patch('x11_macro_ui.RecordingDialog.exec',return_value=QDialog.DialogCode.Rejected):page.record()
  self.assertEqual(before,page.steps);page.dirty=False
 def test_save_copy_missing_releases_offers_completion_and_updates_map(self):
  self.w.show_page('macros');page=self.w.macros;page.begin_for_button(4);page.name.setText('Copiar')
  page.add({'action':'press','key':'LeftCtrl'});page.add({'action':'press','key':'C'})
  with patch('x11_macro_ui.QMessageBox.question',return_value=QMessageBox.StandardButton.Yes) as confirmation:
   QTest.mouseClick(page.save_button,Qt.MouseButton.LeftButton)
  confirmation.assert_called_once()
  self.assertEqual(len(page.store.list()),1);self.assertEqual(page.views.currentIndex(),0)
  item=page.store.list()[0];self.assertEqual(page.store.assignments()['4'],item['id'])
  self.assertEqual([s['action'] for s in item['macro']['steps']],['press','press','release','release'])
  self.assertEqual(page.assignments.map.calls[4].assignment,'Copiar')
  self.assertFalse(page.dirty);self.assertFalse(self.receiver.writes)
 def test_cancel_shortcut_completion_keeps_draft_and_assignment_empty(self):
  page=self.w.macros;page.begin_for_button(4);page.name.setText('Copiar')
  page.add({'action':'press','key':'LeftCtrl'});page.add({'action':'press','key':'C'})
  before=page.data()
  with patch('x11_macro_ui.QMessageBox.question',return_value=QMessageBox.StandardButton.Cancel):page.request_save()
  self.assertEqual(before,page.data());self.assertEqual(page.store.list(),[])
  self.assertIsNone(page.store.assignments()['4']);page.dirty=False
 def test_save_failure_shows_error_and_preserves_draft(self):
  from test_macros import MACRO
  page=self.w.macros;page.name.setText('Teste');page.insert_recording(MACRO['steps'])
  with patch.object(page.store,'save',side_effect=OSError('Disco cheio')),patch('x11_macro_ui.QMessageBox.warning') as warning:
   page.request_save()
  warning.assert_called_once();self.assertTrue(page.dirty)
  self.assertIn('Macro não salva',self.w.message.text());self.assertEqual(page.store.list(),[]);page.dirty=False
