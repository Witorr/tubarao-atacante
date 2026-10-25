import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from x11_recording import Recording
from x11_macros import validate_macro, summary, MAX_STEPS


class RecordingTests(unittest.TestCase):
 def setUp(self):
  self.now=10.;self.r=Recording(clock=lambda:self.now);self.r.start()
 def test_chord_timing_and_mouse_sequence(self):
  self.r.record({'action':'press','key':'LeftCtrl'})
  self.r.record({'action':'press','key':'C'});self.now+=.5
  self.r.record({'action':'release','key':'C'});self.r.record({'action':'release','key':'LeftCtrl'})
  self.r.record({'action':'mouse_press','button':'back'});self.r.record({'action':'mouse_release','button':'back'})
  self.r.record({'action':'wheel','axis':'vertical','delta':120});self.r.stop()
  data={'steps':self.r.steps,'repeats':1,'mode':'once'}
  self.assertEqual(summary(data)['delay_ms'],500)
  self.assertEqual(self.r.steps[2],{'action':'wait','ms':500})
 def test_stop_closes_held_actions_with_elapsed_time(self):
  self.r.record({'action':'press','key':'A'});self.r.record({'action':'mouse_press','button':'left'});self.now+=.25;self.r.stop()
  self.assertEqual(self.r.steps[2],{'action':'wait','ms':250})
  self.assertEqual(self.r.steps[-1],{'action':'release','key':'A'})
  self.assertIn('Solturas finais',self.r.reason)
  validate_macro({'steps':self.r.steps,'repeats':1})
 def test_auto_repeat_duplicates_and_stray_releases_ignored(self):
  self.r.record({'action':'release','key':'A'});self.r.record({'action':'press','key':'A'});self.r.record({'action':'press','key':'A'});self.r.stop()
  self.assertEqual(len(self.r.steps),2)
 def test_long_pause_split_and_bounded_stop(self):
  self.r.record({'action':'press','key':'A'});self.now+=61
  self.r.record({'action':'release','key':'A'});self.r.stop()
  self.assertEqual([s['ms'] for s in self.r.steps if s['action']=='wait'],[60000,1000])
 def test_step_limit_stops_without_unbalanced_keys(self):
  for _ in range(MAX_STEPS):
   self.r.record({'action':'press','key':'A'});self.r.record({'action':'release','key':'A'})
  self.assertFalse(self.r.active);self.assertLessEqual(len(self.r.steps),MAX_STEPS)
  validate_macro({'steps':self.r.steps,'repeats':1})
 def test_start_replaces_previous_take_and_stopped_ignores_input(self):
  self.r.record({'action':'press','key':'A'});self.r.stop();before=copy.deepcopy(self.r.steps)
  self.r.record({'action':'press','key':'B'});self.assertEqual(before,self.r.steps)
  self.r.start();self.assertEqual(self.r.steps,[])
 def test_custom_keys_mouse_wheel_and_modes(self):
  steps=[{'action':'press','key':'QtKey:59'},{'action':'release','key':'QtKey:59'},
   {'action':'mouse_press','button':'forward'},{'action':'mouse_release','button':'forward'},
   {'action':'wheel','axis':'horizontal','delta':-120}]
  for mode in ('once','repeat','hold','toggle'):
   self.assertEqual(validate_macro({'steps':steps,'repeats':2,'mode':mode})['mode'],mode)
  for bad in [{'steps':steps,'repeats':1,'mode':'unknown'},
    {'steps':[{'action':'wheel','axis':'z','delta':120}],'repeats':1},
    {'steps':[{'action':'wheel','axis':'vertical','delta':True}],'repeats':1},
    {'steps':[{'action':'mouse_release','button':'left'}],'repeats':1},
    {'steps':[{'action':'press','key':'QtKey:33554431'}],'repeats':1}]:
   with self.subTest(bad=bad),self.assertRaises(ValueError):validate_macro(bad)

try:
 from PySide6.QtCore import Qt,QPoint,QPointF,QEvent
 from PySide6.QtGui import QWheelEvent,QKeyEvent
 from PySide6.QtWidgets import QApplication,QDialog
 from PySide6.QtTest import QTest
 from x11_macro_recorder import RecordingDialog
 HAS_QT=True
except ImportError:HAS_QT=False

@unittest.skipUnless(HAS_QT,'PySide6 não instalado')
class CaptureTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def setUp(self):
  self.d=RecordingDialog();self.d.show();QTest.qWait(20);self.d.start();QTest.qWait(10)
 def tearDown(self):self.d.reject();self.d.deleteLater();QTest.qWait(10)
 def test_real_keyboard_mouse_wheel_and_escape_recorded(self):
  QTest.keyClick(self.d.surface,Qt.Key.Key_C,Qt.KeyboardModifier.ControlModifier)
  QTest.mouseClick(self.d.surface,Qt.MouseButton.BackButton,pos=QPoint(40,40))
  event=QWheelEvent(QPointF(30,30),QPointF(30,30),QPoint(),QPoint(0,120),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
  self.app.sendEvent(self.d.surface,event);QTest.keyClick(self.d.surface,Qt.Key.Key_Escape);self.d.surface.finish()
  steps=self.d.recorder.steps;validate_macro({'steps':steps,'repeats':1})
  self.assertTrue(any(s.get('key')=='LeftCtrl' for s in steps))
  self.assertTrue(any(s.get('button')=='back' for s in steps))
  self.assertTrue(any(s['action']=='wheel' for s in steps))
  self.assertTrue(any(s.get('key')=='Escape' for s in steps));self.assertFalse(self.d.recorder.active)
 def test_punctuation_tab_and_no_autorepeat(self):
  for action in (QEvent.Type.KeyPress,QEvent.Type.KeyRelease):
   self.app.sendEvent(self.d.surface,QKeyEvent(action,Qt.Key.Key_Semicolon,Qt.KeyboardModifier.NoModifier,';'))
  self.app.sendEvent(self.d.surface,QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_A,Qt.KeyboardModifier.NoModifier,'a',True))
  QTest.keyClick(self.d.surface,Qt.Key.Key_Tab);self.d.surface.finish()
  steps=self.d.recorder.steps
  self.assertTrue(any(s.get('key')=='QtKey:59' for s in steps))
  self.assertTrue(any(s.get('key')=='Tab' for s in steps));self.assertFalse(any(s.get('key')=='A' for s in steps))
  validate_macro({'steps':steps,'repeats':1})
 def test_focus_loss_stops_and_closes_pressed_keys(self):
  QTest.keyPress(self.d.surface,Qt.Key.Key_A)
  self.app.sendEvent(self.d.surface,QEvent(QEvent.Type.FocusOut))
  self.assertFalse(self.d.recorder.active)
  self.assertEqual(self.d.recorder.steps[-1],{'action':'release','key':'A'})
 def test_input_after_stop_not_captured(self):
  self.d.surface.finish();QTest.keyClick(self.d.surface,Qt.Key.Key_B)
  self.assertEqual(self.d.recorder.steps,[])

class RecordingStoreTests(unittest.TestCase):
 def test_save_and_assign_is_one_atomic_write(self):
  import tempfile
  from pathlib import Path
  from unittest.mock import patch
  from x11_macros import MacroStore
  with tempfile.TemporaryDirectory() as folder:
   store=MacroStore(folder)
   macro={'steps':[{'action':'mouse_press','button':'left'},{'action':'mouse_release','button':'left'}],'repeats':1,'mode':'toggle'}
   item=store.save('Clique',macro,button=4)
   self.assertEqual(store.assignments()['4'],item['id'])
   before=store.path.read_bytes()
   with patch('x11_macros.os.replace',side_effect=OSError('disk full')):
    with self.assertRaises(OSError):store.save('Outro',macro,button=5)
   self.assertEqual(store.path.read_bytes(),before)
   self.assertEqual(len(store.list()),1);self.assertIsNone(store.assignments()['5'])
 def test_schema_two_and_legacy_repetitions_survive(self):
  import tempfile,json
  from x11_macros import MacroStore
  with tempfile.TemporaryDirectory() as folder:
   store=MacroStore(folder);macro={'steps':[{'action':'press','key':'C'},{'action':'release','key':'C'}],'repeats':4}
   item=store.save('Anterior',macro,button=4)
   data=json.loads(store.path.read_text());data['schema']=2;store.path.write_text(json.dumps(data));before=store.path.read_bytes()
   self.assertEqual(store.list()[0]['macro'],macro);self.assertEqual(before,store.path.read_bytes())
   store.save('Anterior',dict(macro,mode='repeat'),item['id'])
   self.assertEqual(store.assignments()['4'],item['id']);self.assertEqual(json.loads(store.path.read_text())['schema'],3)
