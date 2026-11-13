# -*- coding: utf-8 -*-
import ast,copy,json,os,sys,tempfile,textwrap,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'don_gen'))
import dg_rpg,dg_sessions,dg_checkpoints

class ShiftManagement(unittest.TestCase):
    def fixture(self,folder):
        s=dg_rpg.new_game('Старая смена',24,30,camp_life=True);dg_rpg.save(folder,s);dg_rpg.save(folder,s)
        base=Path(folder)/'_rpg';assets=base/'assets'/s['id'];assets.mkdir(parents=True);(assets/'cg.png').write_bytes(b'owned artwork')
        branches=base/'_branches'/s['id'];branches.mkdir(parents=True);(branches/('b'*64+'.json')).write_text(json.dumps(s),encoding='utf-8')
        return s

    def test_trash_hides_only_selected_shift_and_restore_keeps_all_data(self):
        with tempfile.TemporaryDirectory() as root:
            s=self.fixture(root);other=dg_rpg.new_game('Другая смена',23,14);dg_rpg.save(root,other)
            for name in ('auth.json','native.save','classic-story.txt'):(Path(root)/name).write_bytes(b'untouched')
            key=dg_sessions.trash(root,s['id'])
            self.assertEqual([r['id'] for r in dg_rpg.list_games(root)],[other['id']]);self.assertTrue(dg_sessions.removed(root,s['id']))
            self.assertEqual(dg_sessions.deleted(root)[0]['key'],key)
            self.assertEqual(dg_sessions.restore(root,key),s['id']);self.assertFalse(dg_sessions.removed(root,s['id']))
            self.assertEqual(dg_rpg.load(root,s['id']),s);self.assertEqual(dg_sessions.deleted(root),[])
            self.assertEqual((Path(root)/'_rpg/assets'/s['id']/'cg.png').read_bytes(),b'owned artwork')
            self.assertTrue((Path(root)/'_rpg/_branches'/s['id']/('b'*64+'.json')).exists())
            for name in ('auth.json','native.save','classic-story.txt'):self.assertEqual((Path(root)/name).read_bytes(),b'untouched')

    def test_purge_removes_payload_but_old_native_snapshot_cannot_resurrect_it(self):
        with tempfile.TemporaryDirectory() as root:
            s=self.fixture(root);key=dg_sessions.trash(root,s['id']);dg_sessions.purge(root,key)
            self.assertEqual(dg_sessions.deleted(root),[]);self.assertFalse((Path(root)/'_rpg/_trash'/key).exists())
            self.assertTrue(dg_sessions.removed(root,s['id']))
            with self.assertRaises(ValueError):dg_checkpoints.restore(root,s)
            with self.assertRaises(ValueError):dg_rpg.save(root,s)
            self.assertFalse((Path(root)/'_rpg'/(s['id']+'.json')).exists())

    def test_native_after_load_redirects_removed_shift_without_loading_or_writing(self):
        with tempfile.TemporaryDirectory() as root:
            s=self.fixture(root);dg_sessions.trash(root,s['id'])
            source=(Path(__file__).resolve().parents[1]/'don_gen/dg_rpg.rpy').read_text(encoding='utf-8')
            tree=ast.parse(textwrap.dedent(source.split('init 1001 python:\n',1)[1].split('\ndefault ',1)[0]))
            node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='dg_rpg_after_load')
            store=SimpleNamespace(dg_rpg_state=s,dg_rpg_active=True,dg_rpg_pending_turn={'old':True})
            api=SimpleNamespace(game=SimpleNamespace(context=lambda:SimpleNamespace(current='old'),script=SimpleNamespace(lookup=lambda value:SimpleNamespace(filename='game/mods/don_gen/dg_rpg.rpy'))),jump=Mock(),notify=Mock())
            opened=Mock();ns=dict(store=store,renpy=api,dg_rpg=dg_rpg,dg_rpg_root=lambda:root,dg_rpg_open=opened)
            exec(compile(ast.Module(body=[node],type_ignores=[]),'actual_removed_resume','exec'),ns);ns['dg_rpg_after_load']()
            opened.assert_not_called();api.jump.assert_called_once_with('dg_rpg_picker_label');self.assertIsNone(store.dg_rpg_state)

    def test_traversal_and_invalid_identifiers_never_change_anything(self):
        with tempfile.TemporaryDirectory() as root:
            s=self.fixture(root)
            for bad in ('../auth','a'*32+'\n','',None):
                for method in (dg_sessions.trash,dg_sessions.restore,dg_sessions.purge):
                    with self.assertRaises(ValueError):method(root,bad)
            self.assertEqual(dg_rpg.load(root,s['id']),s)

    def test_failed_move_rolls_back_to_the_original_shift(self):
        with tempfile.TemporaryDirectory() as root:
            s=self.fixture(root);original=os.rename;calls=[0]
            def move(source,target):
                calls[0]+=1
                if calls[0]==2:raise OSError('simulated disk failure')
                return original(source,target)
            with patch.object(dg_sessions.os,'rename',side_effect=move):
                with self.assertRaises(OSError):dg_sessions.trash(root,s['id'])
            self.assertEqual(dg_rpg.load(root,s['id']),s);self.assertFalse(dg_sessions.removed(root,s['id']));self.assertEqual(dg_sessions.deleted(root),[])

    def test_restore_refuses_to_overwrite_existing_files(self):
        with tempfile.TemporaryDirectory() as root:
            s=self.fixture(root);key=dg_sessions.trash(root,s['id'])
            target=Path(root)/'_rpg'/(s['id']+'.json');target.write_bytes(b'new data')
            with self.assertRaises(ValueError):dg_sessions.restore(root,key)
            self.assertEqual(target.read_bytes(),b'new data');self.assertTrue(dg_sessions.deleted(root))

    def test_redirected_assets_cannot_delete_files_outside_the_shift(self):
        with tempfile.TemporaryDirectory() as root,tempfile.TemporaryDirectory() as outside:
            s=dg_rpg.new_game('Связь',24,30);dg_rpg.save(root,s)
            (Path(outside)/'keep.txt').write_bytes(b'outside')
            assets=Path(root)/'_rpg/assets';assets.mkdir()
            link=assets/s['id']
            try:os.symlink(outside,str(link),target_is_directory=True)
            except (OSError,NotImplementedError):
                if os.name!='nt':self.skipTest('Symlinks unavailable')
                import base64,subprocess
                command="New-Item -ItemType Junction -Path '%s' -Target '%s' | Out-Null"%(str(link).replace("'","''"),outside.replace("'","''"))
                encoded=base64.b64encode(command.encode('utf-16le')).decode('ascii')
                result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',encoded],capture_output=True,creationflags=0x08000000)
                if result.returncode:self.skipTest('Directory links unavailable')
            try:
                with self.assertRaises(ValueError):dg_sessions.trash(root,s['id'])
                self.assertEqual((Path(outside)/'keep.txt').read_bytes(),b'outside');self.assertEqual(dg_rpg.load(root,s['id']),s)
            finally:
                if link.is_symlink():link.unlink()
                elif os.path.lexists(str(link)):os.rmdir(str(link))

    def test_tampered_trash_identity_cannot_restore_under_another_id(self):
        with tempfile.TemporaryDirectory() as root:
            s=self.fixture(root);key=dg_sessions.trash(root,s['id']);path=Path(root)/'_rpg/_trash'/key/'manifest.json'
            manifest=json.loads(path.read_text(encoding='utf-8'));manifest['id']='a'*32;path.write_text(json.dumps(manifest),encoding='utf-8')
            with self.assertRaises(ValueError):dg_sessions.restore(root,key)
            self.assertFalse((Path(root)/'_rpg'/('a'*32+'.json')).exists())

if __name__=='__main__':unittest.main()
