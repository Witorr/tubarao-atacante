"""Shared palette, preference persistence and Linux theme detection."""
import configparser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

LIGHT=dict(BG='#f3f6fb',SIDE='#ffffff',CARD='#ffffff',FIELD='#edf2f8',LINE='#d6dfeb',
 TEXT='#1b2939',MUTED='#56677b',ACCENT='#1768c4',ON_PRIMARY='#ffffff',SELECTED='#dceaff',GREEN='#26724e',ERROR='#b3261e',WARNING='#8a4a00')
DARK=dict(BG='#282a36',SIDE='#353747',CARD='#353747',FIELD='#44475a',LINE='#6272a4',
 TEXT='#f8f8f2',MUTED='#c2c5d9',ACCENT='#bd93f9',ON_PRIMARY='#282a36',SELECTED='#44475a',GREEN='#50fa7b',ERROR='#ff5555',WARNING='#ffb86c')


def preferences_path():
 return Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config')).expanduser()/'tubarao-atacante/appearance.json'


def load_preference():
 try:
  data=json.loads(preferences_path().read_text())
  return data['theme'] if data.get('theme') in ('system','light','dark') else 'system'
 except (OSError,ValueError,TypeError,AttributeError,KeyError):return 'system'


def save_preference(value):
 if value not in ('system','light','dark'):raise ValueError('Tema inválido.')
 path=preferences_path();path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 fd,temp=tempfile.mkstemp(prefix='.appearance-',dir=path.parent)
 try:
  with os.fdopen(fd,'w') as stream:
   json.dump({'theme':value},stream);stream.flush();os.fsync(stream.fileno())
  os.replace(temp,path)
 finally:
  if os.path.exists(temp):os.unlink(temp)


def system_theme():
 """Prefer the appearance portal; fall back to KDE/GNOME local preferences."""
 if shutil.which('gdbus'):
  try:
   result=subprocess.run(['gdbus','call','--session','--dest','org.freedesktop.portal.Desktop',
    '--object-path','/org/freedesktop/portal/desktop','--method','org.freedesktop.portal.Settings.Read',
    'org.freedesktop.appearance','color-scheme'],capture_output=True,text=True,timeout=1)
   match=re.search(r'uint32\s+([012])',result.stdout)
   if result.returncode==0 and match and match[1]!='0':return 'dark' if match[1]=='1' else 'light'
  except (OSError,subprocess.TimeoutExpired):pass
 try:
  kde=configparser.ConfigParser(interpolation=None);kde.read(Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'kdeglobals')
  rgb=kde.get('Colors:Window','BackgroundNormal',fallback='')
  if rgb:
   r,g,b=(int(x) for x in rgb.split(',')[:3]);return 'dark' if .2126*r+.7152*g+.0722*b<128 else 'light'
  name=kde.get('General','ColorScheme',fallback='').lower()
  if name:return 'dark' if any(s in name for s in ('dark','dracula')) else 'light'
 except (OSError,ValueError,configparser.Error):pass
 if 'dark' in os.environ.get('GTK_THEME','').lower():return 'dark'
 if shutil.which('gsettings'):
  try:
   result=subprocess.run(['gsettings','get','org.gnome.desktop.interface','color-scheme'],capture_output=True,text=True,timeout=1)
   if result.returncode==0:return 'dark' if 'prefer-dark' in result.stdout else 'light'
  except (OSError,subprocess.TimeoutExpired):pass
 return 'light'


