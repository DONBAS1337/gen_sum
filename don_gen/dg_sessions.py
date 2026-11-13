# -*- coding: utf-8 -*-
"""Shift trash, restore and explicit purge. Never touches native slots or auth."""
from __future__ import unicode_literals
import io,json,os,re,time,uuid
import dg_atomic

def _id(value):
    if not isinstance(value,(str,type(u''))) or not re.match(r'\A[a-f0-9]{32}\Z',value):raise ValueError('Invalid shift identifier')
    return value

def _base(root):
    root=os.path.realpath(os.path.abspath(root));base=os.path.join(root,'_rpg')
    if os.path.normcase(os.path.realpath(base))!=os.path.normcase(base) or _link(base):raise ValueError('Save directory must not be redirected')
    return base

def _link(path):
    if os.path.islink(path) or getattr(os.path,'isjunction',lambda p:False)(path):return True
    if os.name=='nt' and os.path.lexists(path):
        import ctypes
        flags=ctypes.windll.kernel32.GetFileAttributesW(type(u'')(path))
        return flags!=-1 and bool(flags&0x400)
    return False

def _inside(base,path):
    base=os.path.realpath(base);resolved=os.path.realpath(path)
    if not os.path.normcase(resolved).startswith(os.path.normcase(base+os.sep)) or _link(path):raise ValueError('Shift path escapes its directory')
    part=base
    for name in os.path.relpath(path,base).split(os.sep):
        part=os.path.join(part,name)
        if _link(part):raise ValueError('Redirected shift path')
    return path

def _tree(base,path):
    _inside(base,path)
    if not os.path.exists(path):return
    if os.path.isdir(path):
        for folder,dirs,files in os.walk(path,followlinks=False):
            _inside(base,folder)
            for name in dirs+files:_inside(base,os.path.join(folder,name))

def _write(path,value):
    temporary=path+'.'+uuid.uuid4().hex+'.tmp'
    try:
        with io.open(temporary,'w',encoding='utf-8') as f:
            f.write(json.dumps(value,ensure_ascii=False,sort_keys=True));f.flush();os.fsync(f.fileno())
        dg_atomic.replace(temporary,path)
    finally:
        if os.path.isfile(temporary):os.unlink(temporary)

def removed(root,game_id):
    base=_base(root);path=_inside(base,os.path.join(base,'_removed',_id(game_id)+'.json'))
    return os.path.isfile(path)

def _parts(base,game_id):
    return [('state.json',os.path.join(base,game_id+'.json')),
            ('backup.json',os.path.join(base,game_id+'.json.bak')),
            ('assets',os.path.join(base,'assets',game_id)),
            ('branches',os.path.join(base,'_branches',game_id))]

def trash(root,game_id):
    import dg_rpg
    game_id=_id(game_id);base=_base(root)
    if removed(root,game_id):raise ValueError(u'Эта смена уже удалена из списка.')
    state=dg_rpg.load(root,game_id)
    parts=[(name,path) for name,path in _parts(base,game_id) if os.path.lexists(path)]
    for name,path in parts:_tree(base,path)
    folder=_inside(base,os.path.join(base,'_trash',uuid.uuid4().hex));_tree(base,os.path.dirname(folder))
    os.makedirs(folder)
    manifest={'version':1,'key':os.path.basename(folder),'id':game_id,'name':state['hero']['name'],
              'day':state['day'],'duration':state['duration'],'finished':state['finished'],
              'deleted_at':time.time(),'parts':[name for name,path in parts],'status':'moving'}
    _write(os.path.join(folder,'manifest.json'),manifest);moved=[]
    try:
        for name,path in parts:
            dg_atomic.retry(lambda path=path,name=name:os.rename(path,os.path.join(folder,name)));moved.append((name,path))
        marker=_inside(base,os.path.join(base,'_removed',game_id+'.json'));parent=os.path.dirname(marker)
        if not os.path.isdir(parent):os.makedirs(parent)
        _write(marker,{'id':game_id,'key':manifest['key'],'purged':False})
        manifest['status']='deleted';_write(os.path.join(folder,'manifest.json'),manifest)
    except Exception:
        for name,path in reversed(moved):
            source=os.path.join(folder,name)
            if os.path.exists(source) and not os.path.exists(path):dg_atomic.retry(lambda source=source,path=path:os.rename(source,path))
        marker=os.path.join(base,'_removed',game_id+'.json')
        if os.path.isfile(marker):os.unlink(marker)
        manifest['status']='rolled_back';_write(os.path.join(folder,'manifest.json'),manifest)
        raise
    return manifest['key']

def _read(root,key):
    base=_base(root);folder=_inside(base,os.path.join(base,'_trash',_id(key)));_tree(base,folder)
    with io.open(os.path.join(folder,'manifest.json'),'r',encoding='utf-8') as f:m=json.load(f)
    if not isinstance(m,dict) or m.get('version')!=1 or m.get('key')!=key or m.get('status')!='deleted':raise ValueError('Invalid trashed shift')
    _id(m.get('id'))
    if not isinstance(m.get('name'),(str,type(u''))) or len(m['name'])>100 or type(m.get('day')) is not int or type(m.get('duration')) is not int or type(m.get('finished')) is not bool or not isinstance(m.get('deleted_at'),(int,float)):raise ValueError('Invalid shift metadata')
    if not isinstance(m.get('parts'),list) or not m['parts'] or len(m['parts'])!=len(set(m['parts'])) or any(n not in ('state.json','backup.json','assets','branches') for n in m['parts']):raise ValueError('Invalid shift contents')
    if set(os.listdir(folder))-set(m['parts']+['manifest.json']):raise ValueError('Unexpected files in shift trash')
    return base,folder,m

def deleted(root):
    base=_base(root);folder=_inside(base,os.path.join(base,'_trash'))
    if not os.path.isdir(folder):return []
    rows=[]
    for key in os.listdir(folder):
        if not re.match(r'\A[a-f0-9]{32}\Z',key):continue
        try:
            unused,unused2,m=_read(root,key);rows.append(m)
        except (IOError,OSError,ValueError,KeyError,TypeError):continue
    return sorted(rows,key=lambda r:r['deleted_at'],reverse=True)

def restore(root,key):
    base,folder,m=_read(root,key);dest=dict(_parts(base,m['id']))
    with io.open(os.path.join(folder,'state.json'),'r',encoding='utf-8') as f:state=json.load(f)
    __import__('dg_rpg').validate(state)
    if state['id']!=m['id']:raise ValueError('Shift identity mismatch')
    for name in m['parts']:
        _tree(base,dest[name])
        if os.path.lexists(dest[name]):raise ValueError(u'Смена с таким идентификатором уже существует. Ничего не перезаписано.')
        if not os.path.exists(os.path.join(folder,name)):raise ValueError(u'В корзине отсутствует часть смены.')
    moved=[]
    try:
        for name in m['parts']:
            parent=os.path.dirname(dest[name])
            if not os.path.isdir(parent):os.makedirs(parent)
            dg_atomic.retry(lambda name=name:os.rename(os.path.join(folder,name),dest[name]));moved.append(name)
        marker=_inside(base,os.path.join(base,'_removed',m['id']+'.json'))
        if os.path.isfile(marker):dg_atomic.retry(lambda:os.unlink(marker))
    except Exception:
        for name in reversed(moved):
            if os.path.exists(dest[name]):dg_atomic.retry(lambda name=name:os.rename(dest[name],os.path.join(folder,name)))
        raise
    os.unlink(os.path.join(folder,'manifest.json'));os.rmdir(folder)
    return m['id']

def purge(root,key):
    base,folder,m=_read(root,key)
    # Preserve a small tombstone: a native slot must not recreate a purged shift.
    marker=_inside(base,os.path.join(base,'_removed',m['id']+'.json'))
    if not os.path.isdir(os.path.dirname(marker)):os.makedirs(os.path.dirname(marker))
    _write(marker,{'id':m['id'],'key':key,'purged':True})
    _tree(base,folder)
    for directory,dirs,files in os.walk(folder,topdown=False,followlinks=False):
        for name in files:
            path=_inside(base,os.path.join(directory,name))
            if path==os.path.join(folder,'manifest.json'):continue
            dg_atomic.retry(lambda path=path:os.unlink(path))
        for name in dirs:
            path=_inside(base,os.path.join(directory,name));dg_atomic.retry(lambda path=path:os.rmdir(path))
    dg_atomic.retry(lambda:os.unlink(os.path.join(folder,'manifest.json')))
    os.rmdir(folder)
    return m['id']
