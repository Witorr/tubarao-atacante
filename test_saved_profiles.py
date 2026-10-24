import contextlib,copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import attack_shark_x11 as core
from x11_profiles import ProfileStore,validate_settings,clean_name
from test_lighting import LightingReceiver
SETTINGS={'stage':2,'dpis':[1600,3750,4000,6000,9000,22000],
 'colors':['#ff0000','#79c400','#0000ff','#ffff00','#00ffff','#ff00ff'],
 'polling_hz':500,'lighting':{'mode':'breathing','speed':4,'color':'#9c59ff'}}

class StoreTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.store=ProfileStore(Path(self.tmp.name)/'config')
 def test_roundtrip_crud_duplicate(self):
  self.assertEqual(self.store.list(),[])
  a=self.store.create('Trabalho',SETTINGS);b=self.store.duplicate(a['id'],'Jogos')
  self.assertNotEqual(a['id'],b['id']);self.assertEqual(b['settings'],SETTINGS)
  s=copy.deepcopy(SETTINGS);s['polling_hz']=125
  self.store.update(a['id'],settings=s,name='Mesa')
  self.assertEqual(ProfileStore(self.store.directory).get(a['id'])['settings']['polling_hz'],125)
  self.assertEqual(self.store.get(b['id'])['settings']['polling_hz'],500)
  self.store.delete(a['id']);self.assertEqual(len(self.store.list()),1)
 def test_names_unicode_unique_and_safe_paths(self):
  a=self.store.create(' Mesa ',SETTINGS)
  for name in ['mesa','Ｍｅｓａ']:
   with self.assertRaises(ValueError):self.store.create(name,SETTINGS)
  self.store.create('../../outro',SETTINGS)
  self.assertEqual(set(p.name for p in self.store.directory.iterdir()),{'profiles.json','profiles.lock'})
  self.store.update(a['id'],name='MESA')
 def test_invalid_names(self):
  for name in ['', ' ', 'x\ny','x\0y','a'*65,23]:
   with self.subTest(name=name),self.assertRaises(ValueError):clean_name(name)
 def test_return_values_are_copies(self):
  a=self.store.create('Teste',SETTINGS);a['settings']['dpis'][0]=50
  self.store.list()[0]['settings']['dpis'][1]=50
  self.assertEqual(self.store.get(a['id'])['settings']['dpis'],SETTINGS['dpis'])
 def test_atomic_failure_preserves_old_file(self):
  a=self.store.create('Teste',SETTINGS);before=self.store.path.read_bytes()
  with patch('x11_profiles.os.replace',side_effect=OSError('disk full')):
   with self.assertRaises(OSError):self.store.update(a['id'],name='Outro')
  self.assertEqual(self.store.path.read_bytes(),before)
  self.assertFalse(list(self.store.directory.glob('*.tmp')))
 def test_private_permissions(self):
  self.store.create('Teste',SETTINGS)
  self.assertEqual(self.store.path.stat().st_mode&0o777,0o600)
  self.assertEqual(self.store.directory.stat().st_mode&0o777,0o700)
 def test_corrupt_or_future_file_preserved(self):
  for data in ['{bad',json.dumps({'schema':2,'profiles':[]}),json.dumps([])]:
   self.store.directory.mkdir(exist_ok=True);self.store.path.write_text(data)
   with self.assertRaises(ValueError):self.store.create('Teste',SETTINGS)
   self.assertEqual(self.store.path.read_text(),data)
 def test_invalid_stored_settings(self):
  self.store.create('Teste',SETTINGS);data=json.loads(self.store.path.read_text())
  data['profiles'][0]['settings']['polling_hz']=999
  self.store.path.write_text(json.dumps(data))
  with self.assertRaises(ValueError):self.store.list()
 def test_two_instances_no_lost_distinct_records(self):
  other=ProfileStore(self.store.directory)
  self.store.create('Um',SETTINGS);other.create('Dois',SETTINGS)
  self.assertEqual(len(self.store.list()),2)
 def test_missing_record_does_not_delete_others(self):
  self.store.create('Um',SETTINGS)
  with self.assertRaises(ValueError):self.store.delete('missing')
  self.assertEqual(len(self.store.list()),1)

class PresetTransactionTests(unittest.TestCase):
 def setUp(self):
  self.receiver=LightingReceiver();self.backup=Mock(return_value='/private/backup.json')
  self.session=Mock(side_effect=lambda:contextlib.nullcontext(self.receiver))
  self.app=core.X11(session_factory=self.session,backup_fn=self.backup)
 def test_full_settings_order_verification_and_noop(self):
  before=dict(self.receiver.frames);result=self.app.apply_saved_profile(SETTINGS)
  self.assertEqual(result['status'],'verified')
  self.assertEqual([f[0] for f in self.receiver.writes],[4,5,6])
  self.assertEqual(result['polling_hz'],500)
  self.assertEqual(result['configuration']['active_stage_candidate'],2)
  self.assertEqual(result['lighting']['speed'],4)
  self.assertEqual(self.receiver.frames[5][9:11],before[5][9:11])
  self.assertEqual(self.backup.call_args.args[2:],(before[4],before[6],before[5]))
  self.receiver.writes.clear();self.backup.reset_mock()
  self.assertEqual(self.app.apply_saved_profile(SETTINGS)['status'],'unchanged')
  self.assertEqual(self.receiver.writes,[]);self.backup.assert_not_called()
 def test_invalid_preset_before_hardware_access(self):
  for key,value in [('stage',True),('dpis',[1]*6),('colors',['bad']*6),('polling_hz',True),('lighting',{'mode':[],'speed':1,'color':'ffffff'})]:
   s=copy.deepcopy(SETTINGS);s[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):self.app.apply_saved_profile(s)
  self.session.assert_not_called()
 def test_invalid_frames_before_write(self):
  self.receiver.frames[5]=bytes(15)
  with self.assertRaises(ValueError):self.app.apply_saved_profile(SETTINGS)
  self.assertFalse(self.receiver.writes);self.backup.assert_not_called()
 def test_backup_failure_prevents_write(self):
  self.backup.side_effect=OSError('disk full')
  with self.assertRaises(OSError):self.app.apply_saved_profile(SETTINGS)
  self.assertFalse(self.receiver.writes)
 def test_mismatch_and_partial_failure_no_retry(self):
  self.receiver.reject_05=True
  self.assertEqual(self.app.apply_saved_profile(SETTINGS)['status'],'verification_mismatch')
  self.assertEqual(len(self.receiver.writes),3)
  self.receiver.writes.clear();self.receiver.disconnect_on_05=True
  with self.assertRaisesRegex(RuntimeError,'/private/backup.json'):self.app.apply_saved_profile(SETTINGS)
  self.assertEqual([f[0] for f in self.receiver.writes],[4,5])
 def test_unknown_speed_preserved(self):
  s=copy.deepcopy(SETTINGS);s['lighting']['speed']=None
  before=self.receiver.frames[5][4];self.app.apply_saved_profile(s)
  self.assertEqual(self.receiver.frames[5][4],before)
 def test_polling_only_skips_other_reports(self):
  self.app.apply_saved_profile(SETTINGS);self.receiver.writes.clear()
  s=copy.deepcopy(SETTINGS);s['polling_hz']=125;self.app.apply_saved_profile(s)
  self.assertEqual([f[0] for f in self.receiver.writes],[6])
