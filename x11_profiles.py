"""Local named presets. Semantic settings only; no arbitrary HID packets."""
import copy
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import tempfile
import unicodedata
import uuid


def clean_name(name):
    if not isinstance(name,str):raise ValueError('Informe um nome para o perfil.')
    name=unicodedata.normalize('NFKC',name).strip()
    if not 1<=len(name)<=64 or any(unicodedata.category(c).startswith('C') for c in name):
        raise ValueError('O nome deve ter de 1 a 64 caracteres, sem caracteres de controle.')
    return name


def validate_settings(data):
    from attack_shark_x11 import encode_dpi, parse_rgb, stage_index, LIGHTING_MODES
    if not isinstance(data,dict) or set(data)!={'stage','dpis','colors','polling_hz','lighting'}:
        raise ValueError('Configuração de perfil incompleta ou não reconhecida.')
    stage_index(data['stage'])
    if type(data['polling_hz']) is not int or data['polling_hz'] not in (125,250,500,1000):
        raise ValueError('Polling inválido no perfil.')
    if not isinstance(data['dpis'],list) or len(data['dpis'])!=6:
        raise ValueError('O perfil deve conter seis valores de DPI.')
    for value in data['dpis']:encode_dpi(value)
    if not isinstance(data['colors'],list) or len(data['colors'])!=6:
        raise ValueError('O perfil deve conter seis cores.')
    colors=['#'+parse_rgb(c).hex() for c in data['colors']]
    light=data['lighting']
    if not isinstance(light,dict) or set(light)!={'mode','speed','color'} or not isinstance(light['mode'],str) or light['mode'] not in LIGHTING_MODES:
        raise ValueError('Iluminação não reconhecida no perfil.')
    speed=light['speed']
    if speed is not None and (type(speed) is not int or not 1<=speed<=5):
        raise ValueError('Velocidade inválida no perfil.')
    return {'stage':data['stage'],'dpis':list(data['dpis']),'colors':colors,
            'polling_hz':data['polling_hz'],'lighting':{'mode':light['mode'],'speed':speed,
                                                       'color':'#'+parse_rgb(light['color']).hex()}}


class ProfileStore:
    def __init__(self,directory=None):
        base=Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config')).expanduser()
        self.directory=Path(directory) if directory is not None else base/'tubarao-atacante'
        self.path=self.directory/'profiles.json'

    @contextmanager
    def locked(self):
        self.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        fd=os.open(self.directory/'profiles.lock',os.O_CREAT|os.O_RDWR|os.O_CLOEXEC|os.O_NOFOLLOW,0o600)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX)
            yield
        finally:os.close(fd)

    def _read(self):
        if not self.path.exists():return {'schema':1,'profiles':[]}
        try:
            if self.path.stat().st_size>2_000_000:raise ValueError('Arquivo de perfis muito grande.')
            data=json.loads(self.path.read_text(encoding='utf-8'))
            if type(data.get('schema')) is not int or data['schema']!=1 or set(data)!={'schema','profiles'} or not isinstance(data['profiles'],list):
                raise ValueError('Formato de perfis não reconhecido.')
            ids=set();names=set()
            for item in data['profiles']:
                if set(item)!={'id','name','created_at','updated_at','settings'}:raise ValueError('Registro de perfil inválido.')
                if str(uuid.UUID(item['id']))!=item['id']:raise ValueError('Identificador inválido.')
                name=clean_name(item['name'])
                if name!=item['name'] or item['id'] in ids or name.casefold() in names:raise ValueError('Perfis duplicados ou inválidos.')
                ids.add(item['id']);names.add(name.casefold())
                for field in ('created_at','updated_at'):datetime.fromisoformat(item[field])
                item['settings']=validate_settings(item['settings'])
            return data
        except (ValueError,TypeError,KeyError,AttributeError) as exc:
            raise ValueError('Não foi possível ler profiles.json. O arquivo foi preservado. '+str(exc)) from exc

    def _write(self,data):
        fd,path=tempfile.mkstemp(prefix='.profiles-',suffix='.tmp',dir=self.directory)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as stream:
                json.dump(data,stream,ensure_ascii=False,indent=2);stream.write('\n')
                stream.flush();os.fsync(stream.fileno())
            os.replace(path,self.path)
            dir_fd=os.open(self.directory,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(dir_fd)
            finally:os.close(dir_fd)
        finally:
            if os.path.exists(path):os.unlink(path)

    def list(self):
        with self.locked():return copy.deepcopy(self._read()['profiles'])

    def get(self,profile_id):
        with self.locked():return copy.deepcopy(self._find(self._read(),profile_id))

    @staticmethod
    def _find(data,profile_id):
        for item in data['profiles']:
            if item['id']==profile_id:return item
        raise ValueError('O perfil não existe mais. Atualize a lista.')

    @staticmethod
    def _unique(data,name,except_id=None):
        if any(p['name'].casefold()==name.casefold() and p['id']!=except_id for p in data['profiles']):
            raise ValueError('Já existe um perfil com esse nome.')

    def create(self,name,settings):
        name=clean_name(name);settings=validate_settings(settings)
        with self.locked():
            data=self._read();self._unique(data,name)
            now=datetime.now(timezone.utc).isoformat()
            item={'id':str(uuid.uuid4()),'name':name,'created_at':now,'updated_at':now,'settings':settings}
            data['profiles'].append(item);self._write(data);return copy.deepcopy(item)

    def update(self,profile_id,settings=None,name=None):
        if settings is not None:settings=validate_settings(settings)
        if name is not None:name=clean_name(name)
        with self.locked():
            data=self._read();item=self._find(data,profile_id)
            if name is not None:self._unique(data,name,profile_id);item['name']=name
            if settings is not None:item['settings']=settings
            item['updated_at']=datetime.now(timezone.utc).isoformat()
            self._write(data);return copy.deepcopy(item)

    def duplicate(self,profile_id,name):
        return self.create(name,self.get(profile_id)['settings'])

    def delete(self,profile_id):
        with self.locked():
            data=self._read();self._find(data,profile_id)
            data['profiles']=[p for p in data['profiles'] if p['id']!=profile_id]
            self._write(data)
