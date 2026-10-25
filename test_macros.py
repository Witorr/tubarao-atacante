import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from x11_macros import MacroStore, validate_macro, summary, MAX_STEPS

MACRO={'steps':[{'action':'press','key':'LeftCtrl'},
 {'action':'press','key':'C'},{'action':'wait','ms':50},
 {'action':'release','key':'C'},{'action':'release','key':'LeftCtrl'}],'repeats':2}

class MacroValidationTests(unittest.TestCase):
 def test_chord_and_duration(self):
  result=validate_macro(MACRO);result['steps'].clear()
  self.assertEqual(len(MACRO['steps']),5)
  self.assertEqual(summary(MACRO),{'steps':5,'repeats':2,'delay_ms':100})
 def test_unbalanced_sequences(self):
  for steps in [[{'action':'release','key':'C'}],
    [{'action':'press','key':'C'}],
    [{'action':'press','key':'C'},{'action':'press','key':'C'},{'action':'release','key':'C'}],
    [{'action':'wait','ms':100}]]:
   with self.subTest(steps=steps),self.assertRaises(ValueError):validate_macro({'steps':steps,'repeats':1})
 def test_schema_and_non_integer_values(self):
  for invalid in [None,[],{},dict(MACRO,raw_hex='04'),dict(MACRO,repeats=True),dict(MACRO,repeats=0),dict(MACRO,repeats=101),dict(MACRO,steps=[]),dict(MACRO,steps=MACRO['steps']*MAX_STEPS)]:
   with self.subTest(value=invalid),self.assertRaises(ValueError):validate_macro(invalid)
 def test_arbitrary_actions_keys_and_payloads_rejected(self):
  for step in [{'action':'shell','command':'anything'},{'action':'press','key':[]},
    {'action':'press','key':'UNKNOWN'},{'action':'press','key':'C','hex':'04'},
    {'action':'wait','ms':True},{'action':'wait','ms':-1},{'action':'wait','ms':60001}]:
   with self.subTest(step=step),self.assertRaises(ValueError):validate_macro({'steps':[step]+MACRO['steps'],'repeats':1})
 def test_total_duration_bound(self):
  macro=copy.deepcopy(MACRO);macro['steps'][2]['ms']=60000;macro['repeats']=100
  with self.assertRaises(ValueError):validate_macro(macro)

class MacroStoreTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.store=MacroStore(Path(self.tmp.name)/'config')
 def test_roundtrip_rename_delete_and_independence(self):
  self.assertEqual(self.store.list(),[])
  item=self.store.save(' Copiar ',MACRO);self.assertEqual(item['name'],'Copiar')
  self.assertEqual(MacroStore(self.store.directory).list()[0]['macro'],MACRO)
  item['macro']['steps'].clear();self.assertEqual(self.store.list()[0]['macro'],MACRO)
  self.store.save('Outro',MACRO,item['id']);self.assertEqual(self.store.list()[0]['name'],'Outro')
  self.store.delete(item['id']);self.assertEqual(self.store.list(),[])
 def test_name_collision_and_missing_record(self):
  self.store.save('Copiar',MACRO)
  for name in ['copiar','Ｃｏｐｉａｒ']:
   with self.assertRaises(ValueError):self.store.save(name,MACRO)
  before=self.store.path.read_bytes()
  with self.assertRaises(ValueError):self.store.save('Outro',MACRO,'missing')
  with self.assertRaises(ValueError):self.store.delete('missing')
  self.assertEqual(before,self.store.path.read_bytes())
 def test_private_atomic_write_and_profiles_untouched(self):
  self.store.directory.mkdir();profiles=self.store.directory/'profiles.json';profiles.write_bytes(b'profile sentinel')
  item=self.store.save('Copiar',MACRO);before=self.store.path.read_bytes()
  self.assertEqual(self.store.path.stat().st_mode&0o777,0o600)
  with patch('x11_macros.os.replace',side_effect=OSError('disk full')):
   with self.assertRaises(OSError):self.store.save('Outro',MACRO,item['id'])
  self.assertEqual(before,self.store.path.read_bytes());self.assertEqual(profiles.read_bytes(),b'profile sentinel')
  self.assertFalse(list(self.store.directory.glob('*.tmp')))
 def test_corrupt_or_future_schema_preserved(self):
  self.store.directory.mkdir()
  for data in ['{bad','[]','null',json.dumps({'schema':True,'macros':[]}),json.dumps({'schema':2,'macros':[]}),json.dumps({'schema':1,'macros':[None]})]:
   self.store.path.write_text(data)
   with self.subTest(data=data),self.assertRaises(ValueError):self.store.save('Copiar',MACRO)
   self.assertEqual(self.store.path.read_text(),data)
 def test_invalid_stored_macro_preserved(self):
  self.store.save('Copiar',MACRO);data=json.loads(self.store.path.read_text());data['macros'][0]['macro']['steps'].pop()
  self.store.path.write_text(json.dumps(data));before=self.store.path.read_bytes()
  with self.assertRaises(ValueError):self.store.list()
  self.assertEqual(before,self.store.path.read_bytes())
 def test_separate_instances_and_xdg(self):
  other=MacroStore(self.store.directory);self.store.save('Um',MACRO);other.save('Dois',MACRO)
  self.assertEqual(len(self.store.list()),2)
  with patch.dict('os.environ',{'XDG_CONFIG_HOME':self.tmp.name}):
   self.assertEqual(MacroStore().path,Path(self.tmp.name)/'tubarao-atacante/macros.json')

class ButtonAssignmentTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.store=MacroStore(self.tmp.name)
 def test_side_button_shortcuts_persist(self):
  from x11_macros import shortcut_macro
  self.store.assign(4,'copy');self.store.assign(5,'paste')
  bindings=MacroStore(self.tmp.name).assignments()
  self.assertEqual(bindings,{'1':None,'2':None,'3':None,'4':'copy','5':'paste'})
  self.assertEqual(validate_macro(shortcut_macro('paste'))['steps'][1]['key'],'V')
 def test_all_five_custom_assignments_rename_and_delete(self):
  item=self.store.save('Teste',MACRO)
  for button in range(1,6):self.store.assign(button,item['id'])
  self.store.save('Outro nome',MACRO,item['id'])
  self.assertEqual(set(self.store.assignments().values()),{item['id']})
  self.store.delete(item['id']);self.assertEqual(set(self.store.assignments().values()),{None})
 def test_old_schema_migrates_only_on_write(self):
  self.store.save('Anterior',MACRO);data=json.loads(self.store.path.read_text());data.pop('assignments');data['schema']=1
  self.store.path.write_text(json.dumps(data));before=self.store.path.read_bytes()
  self.assertEqual(len(self.store.list()),1);self.assertEqual(set(self.store.assignments().values()),{None})
  self.assertEqual(before,self.store.path.read_bytes())
  self.store.assign(4,'copy');self.assertEqual(json.loads(self.store.path.read_text())['schema'],3)
 def test_invalid_mapping_preserves_file(self):
  self.store.assign(4,'copy');before=self.store.path.read_bytes()
  for button,value in [(True,'copy'),(0,None),(6,'paste'),(4,[]),(4,'missing')]:
   with self.subTest(button=button,value=value),self.assertRaises(ValueError):self.store.assign(button,value)
   self.assertEqual(before,self.store.path.read_bytes())
 def test_invalid_dangling_stored_binding_rejected(self):
  self.store.assign(4,'copy');data=json.loads(self.store.path.read_text());data['assignments']['5']='missing';self.store.path.write_text(json.dumps(data));before=self.store.path.read_bytes()
  with self.assertRaises(ValueError):self.store.assign(5,'paste')
  self.assertEqual(before,self.store.path.read_bytes())
 def test_two_instances_preserve_distinct_buttons(self):
  self.store.assign(4,'copy');MacroStore(self.tmp.name).assign(5,'paste')
  self.assertEqual(self.store.assignments()['4'],'copy');self.assertEqual(self.store.assignments()['5'],'paste')

class MacroCompletionTests(unittest.TestCase):
 def test_copy_shortcut_completed_in_reverse_press_order_without_mutation(self):
  from x11_macros import complete_macro,IncompleteMacroError
  draft={'steps':[{'action':'press','key':'LeftCtrl'},{'action':'press','key':'C'}],'repeats':1,'mode':'once'}
  with self.assertRaises(IncompleteMacroError):validate_macro(draft)
  result=complete_macro(draft)
  self.assertEqual(result['steps'][-2:],[{'action':'release','key':'C'},{'action':'release','key':'LeftCtrl'}])
  self.assertEqual(len(draft['steps']),2)
 def test_completion_keeps_existing_releases_and_mouse_order(self):
  from x11_macros import complete_macro
  draft={'steps':[{'action':'press','key':'LeftCtrl'},{'action':'press','key':'C'},
    {'action':'release','key':'C'},{'action':'mouse_press','button':'left'}],'repeats':1}
  result=complete_macro(draft)
  self.assertEqual(result['steps'][-2:],[{'action':'mouse_release','button':'left'},{'action':'release','key':'LeftCtrl'}])
 def test_completion_does_not_accept_malformed_events_or_exceed_limit(self):
  from x11_macros import complete_macro,MAX_STEPS
  for steps in [[{'action':'release','key':'C'}],
    [{'action':'press','key':'C'},{'action':'press','key':'C'}],
    [{'action':'press','key':'C'}]+[{'action':'wait','ms':1}]*(MAX_STEPS-1)]:
   with self.subTest(steps=steps),self.assertRaises(ValueError):complete_macro({'steps':steps,'repeats':1})
