"""Portable offscreen tests for the Qt migration. No hardware required."""
import contextlib,os,tempfile,unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
 from PySide6.QtCore import Qt,QPoint
 from PySide6.QtGui import QColor,QPalette
 from PySide6.QtTest import QTest
 from PySide6.QtWidgets import QApplication
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
