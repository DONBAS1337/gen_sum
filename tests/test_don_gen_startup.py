# -*- coding: utf-8 -*-
import ast
import pathlib
import sys
import textwrap
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'don_gen'))
import dg_core

class StartupRegressions(unittest.TestCase):
    def test_both_init_blocks_have_no_function_import_collision(self):
        functions=set(); imports=set()
        for filename, marker in [('don_gen.rpy','init 1000 python:\n'),('dg_rpg.rpy','init 1001 python:\n')]:
            src=(ROOT/'don_gen'/filename).read_text(encoding='utf-8').split(marker,1)[1]
            lines=[]
            for line in src.splitlines():
                if line and not line.startswith((' ', '#')):break
                lines.append(line)
            for node in ast.parse(textwrap.dedent('\n'.join(lines))).body:
                if isinstance(node, ast.FunctionDef):functions.add(node.name)
                elif isinstance(node, (ast.Import,ast.ImportFrom)):
                    imports.update(a.asname or a.name.split('.')[0] for a in node.names)
        self.assertEqual(functions & imports,set())
        src=(ROOT/'don_gen'/'don_gen.rpy').read_text(encoding='utf-8')
        self.assertNotIn('Function(dg_audio,',src)
        self.assertEqual(src.count('Function(dg_menu_audio,'),4)

    def test_dispatcher_rejects_missing_and_malformed_chapters(self):
        good={'id':'chapter','commands':[{'op':'say','who':None,'text':'Hello'}, {'op':'play','channel':'music','key':'song'}],'choices':['Go']}
        self.assertTrue(dg_core.valid_runtime_chapter(good))
        for bad in (None,False,{},dict(good,commands=[None]),dict(good,commands=[{'op':'say'}]),dict(good,choices=False),dict(good,commands=[{'op':[] }])):
            self.assertFalse(dg_core.valid_runtime_chapter(bad))

    def test_busy_request_waits_then_starts_its_own_task(self):
        cases = (
            ('don_gen.rpy', 'dg_run', 'dg_wait_screen', 'dg_valid_chapter'),
            ('dg_rpg.rpy', 'dg_rpg_run', 'dg_rpg_wait_screen', 'dg_rpg_wait_screen'),
        )
        for filename, runner, waiter, next_definition in cases:
            with self.subTest(filename=filename):
                src = (ROOT / 'don_gen' / filename).read_text(encoding='utf-8')
                start = src.index('    def ' + runner + '(')
                end = src.index('    def ' + next_definition + '(', start + 1)
                block = textwrap.dedent(src[start:end])
                calls = []

                class App:
                    busy = True

                    def start(self, task, *args):
                        if self.busy:
                            return None
                        calls.append((task, args))
                        self.busy = True
                        return object()

                app = App()

                class Runtime:
                    pass

                Runtime.app = app

                def wait(mode):
                    calls.append(('wait', mode))
                    app.busy = False

                namespace = {'dg_runtime': Runtime, waiter: wait}
                exec(compile(block, runner, 'exec'), namespace)
                namespace[runner]('chapter', 'new-task', 1)
                self.assertEqual(calls, [('wait', 'chapter'), ('new-task', (1,)), ('wait', 'chapter')])
