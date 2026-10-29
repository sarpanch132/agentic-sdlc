"""Real, offline process lifetime checks; no phase tools or provider calls."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


@unittest.skipUnless(os.name == 'nt', 'Windows Job Object checks')
class ProcessTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('installer.process'), 'native process runner missing')
        from installer.process import run
        self.run_command = run
        self.temp = tempfile.TemporaryDirectory(prefix='process fixture & ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}

    def command(self, code, *args, timeout=5):
        return self.run_command([sys.executable, '-I', '-c', code, *args], cwd=self.root, env=self.env, timeout=timeout)

    def test_real_argv_environment_and_exit(self):
        result = self.command('import os,sys; print(sys.argv[1]); print(os.getenv("PRIVATE_PROVIDER_TOKEN","absent")); sys.exit(3)', 'literal & $(x) " words')
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout.splitlines(), ['literal & $(x) " words', 'absent'])

    def test_timeout_kills_descendant(self):
        marker = self.root / 'child.txt'
        child = 'import time,pathlib,sys; time.sleep(1); pathlib.Path(sys.argv[1]).write_text("alive")'
        parent = 'import subprocess,sys,time; subprocess.Popen([sys.executable,"-I","-c",sys.argv[1],sys.argv[2]]); time.sleep(10)'
        with self.assertRaises(subprocess.TimeoutExpired):
            self.command(parent, child, str(marker), timeout=.3)
        time.sleep(1.2)
        self.assertFalse(marker.exists())

    def test_parent_exit_kills_detached_child_holding_pipes(self):
        marker = self.root / 'detached.txt'
        child = 'import time,pathlib,sys; time.sleep(1); pathlib.Path(sys.argv[1]).write_text("alive")'
        parent = 'import subprocess,sys; subprocess.Popen([sys.executable,"-I","-c",sys.argv[1],sys.argv[2]],creationflags=8)'
        before = time.monotonic()
        self.assertEqual(self.command(parent, child, str(marker), timeout=3).returncode, 0)
        self.assertLess(time.monotonic() - before, 3)
        time.sleep(1.2)
        self.assertFalse(marker.exists())

    def test_output_is_drained_and_limited(self):
        with self.assertRaisesRegex(RuntimeError, 'output limit'):
            self.command('import sys; sys.stdout.write("x"*1000000); sys.stderr.write("y"*1000000)')

    def test_wrapper_is_rejected_without_execution(self):
        with self.assertRaises(ValueError):
            self.run_command(['anything.cmd'], cwd=self.root, env=self.env, timeout=1)

    def test_missing_executable_fails_cleanly(self):
        with self.assertRaises(OSError):
            self.run_command([str(self.root / 'absent.exe')], cwd=self.root, env=self.env, timeout=1)

    def test_child_is_actually_in_job(self):
        code = ('import ctypes as c; from ctypes import wintypes as w; '
                'k=c.WinDLL("kernel32",use_last_error=True); '
                'k.GetCurrentProcess.restype=w.HANDLE; '
                'k.IsProcessInJob.argtypes=[w.HANDLE,w.HANDLE,c.POINTER(w.BOOL)]; '
                'v=w.BOOL(); assert k.IsProcessInJob(k.GetCurrentProcess(),None,c.byref(v)); print(v.value)')
        self.assertEqual(self.command(code).stdout.strip(), '1')

    def test_repeated_success_and_creation_failure_do_not_leak_handles(self):
        import ctypes as c
        from ctypes import wintypes as w
        api = c.WinDLL('kernel32', use_last_error=True)
        api.GetCurrentProcess.restype = w.HANDLE
        api.GetProcessHandleCount.argtypes = [w.HANDLE, c.POINTER(w.DWORD)]
        def count():
            value = w.DWORD()
            self.assertTrue(api.GetProcessHandleCount(api.GetCurrentProcess(), c.byref(value)))
            return value.value
        self.command('pass')
        before = count()
        for _ in range(10):
            self.command('pass')
            with self.assertRaises(OSError):
                self.run_command([str(self.root / 'absent.exe')], cwd=self.root, env=self.env, timeout=1)
        self.assertLessEqual(count(), before + 2)

    def test_job_creation_failure_has_no_uncontained_fallback(self):
        import ctypes as c
        from unittest.mock import patch
        api = c.WinDLL('kernel32', use_last_error=True)
        marker = self.root / 'unexpected.txt'
        def refuse(*args):
            c.set_last_error(5)
            return None
        class DeniedJob:
            CreateJobObjectW = staticmethod(refuse)
            def __getattr__(self, name):
                return getattr(api, name)
        with patch('ctypes.WinDLL', return_value=DeniedJob()):
            with self.assertRaises(OSError):
                self.command('import pathlib,sys; pathlib.Path(sys.argv[1]).write_text("bad")', str(marker))
        self.assertFalse(marker.exists())
