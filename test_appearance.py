import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from x11_appearance import load_preference,save_preference,preferences_path,system_theme,DARK

class AppearanceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  env=patch.dict(os.environ,{'XDG_CONFIG_HOME':self.tmp.name,'GTK_THEME':''});env.start();self.addCleanup(env.stop)
 def test_preference_roundtrip_and_private_file(self):
  self.assertEqual(load_preference(),'system')
  for value in ('dark','light','system'):
   save_preference(value);self.assertEqual(load_preference(),value)
  self.assertEqual(preferences_path().stat().st_mode&0o777,0o600)
  with self.assertRaises(ValueError):save_preference('invalid')
 def test_invalid_preferences_fall_back_to_system(self):
  path=preferences_path();path.parent.mkdir(parents=True)
  for text in ('{bad','[]','null','{"theme":"invalid"}'):
   path.write_text(text);self.assertEqual(load_preference(),'system')
 def test_failed_write_preserves_preference(self):
  save_preference('dark')
  with patch('x11_appearance.os.replace',side_effect=OSError('disk full')):
   with self.assertRaises(OSError):save_preference('light')
  self.assertEqual(load_preference(),'dark')
 def test_portal_dark_and_light(self):
  with patch('x11_appearance.shutil.which',return_value='/bin/gdbus'):
   for value,expected in ((1,'dark'),(2,'light')):
    with patch('x11_appearance.subprocess.run',return_value=subprocess.CompletedProcess([],0,f'(<uint32 {value}>,)','')):
     self.assertEqual(system_theme(),expected)
 def test_kde_color_fallback(self):
  config=Path(self.tmp.name)/'kdeglobals'
  with patch('x11_appearance.shutil.which',return_value=None):
   for rgb,expected in (('40,42,54','dark'),('240,240,240','light')):
    config.write_text('[Colors:Window]\nBackgroundNormal='+rgb)
    self.assertEqual(system_theme(),expected)
 def test_gtk_and_default_fallback(self):
  with patch('x11_appearance.shutil.which',return_value=None):
   self.assertEqual(system_theme(),'light')
   with patch.dict(os.environ,{'GTK_THEME':'Dracula:dark'}):self.assertEqual(system_theme(),'dark')
 def test_timeout_does_not_crash(self):
  with patch('x11_appearance.shutil.which',return_value='/bin/tool'),patch('x11_appearance.subprocess.run',side_effect=subprocess.TimeoutExpired('tool',1)):
   self.assertEqual(system_theme(),'light')
 def test_dracula_text_contrast(self):
  def luminance(color):
   values=[int(color[i:i+2],16)/255 for i in (1,3,5)]
   return sum((v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4)*k for v,k in zip(values,(.2126,.7152,.0722)))
  for a,b in (('TEXT','BG'),('TEXT','CARD'),('MUTED','CARD'),('ACCENT','ON_PRIMARY')):
   light,dark=sorted((luminance(DARK[a]),luminance(DARK[b])),reverse=True)
   self.assertGreaterEqual((light+.05)/(dark+.05),4.5)
