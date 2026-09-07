import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('update', Path(__file__).resolve().parents[1] / 'scripts/ensure_latest.py')
update = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update)

class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.remote = self.base / 'remote'
        self.remote.mkdir()
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        for name in ('SKILL.md', 'scripts/ensure_latest.py', 'references/user-execution.md',
                     'references/local-sources/manifest.json',
                     'references/local-sources/meeting-review-alignment-full-transcript.txt'):
            self.write(self.remote / name, 'version one\n')
        self.commit()
        self.install = self.base / '安装目录'
        self.write(self.install/'SKILL.md', 'old skill')
        self.write(self.install/'references/stale.md', 'old rule')
        self.write(self.install/'references/legacy/.git/config', 'preserved repository metadata')
        self.write(self.install/'.local/settings.json', '{"owner":"colleague"}')

    def tearDown(self):
        def clear_readonly(func, path, exc):
            import os, stat
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(self.base, onerror=clear_readonly)
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.remote, check=True, capture_output=True).stdout.decode().strip()

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-m', 'test update')

    def update(self):
        return update.ensure_latest(self.install, str(self.remote))

    def test_install_latest_drift_new_commit_and_removal(self):
        result = self.update()
        self.assertEqual(result['status'], 'updated')
        self.assertEqual((Path(result['backup'])/'SKILL.md').read_text(), 'old skill')
        self.assertFalse((self.install/'references/stale.md').exists())
        self.assertTrue((self.install/'references/legacy/.git/config').exists())
        self.assertEqual(json.loads((self.install/'.local/settings.json').read_text())['owner'], 'colleague')
        self.assertEqual(self.update()['status'], 'latest')
        self.write(self.install/'references/user-execution.md', 'local change')
        self.assertEqual(self.update()['status'], 'updated')
        self.write(self.remote/'SKILL.md', 'version two')
        self.write(self.remote/'references/new.md', 'new content')
        self.commit()
        newer = self.update()
        self.assertNotEqual(newer['commit'], result['commit'])
        self.assertEqual((self.install/'SKILL.md').read_text(), 'version two')
        (self.remote/'references/new.md').unlink()
        self.commit()
        self.assertEqual(self.update()['removedFiles'], 1)

    def test_fetch_failure_preserves_files(self):
        self.update()
        before = (self.install/'SKILL.md').read_bytes()
        with self.assertRaises(RuntimeError):
            update.ensure_latest(self.install, str(self.base/'missing'))
        self.assertEqual((self.install/'SKILL.md').read_bytes(), before)
        self.assertFalse((self.install/'.local/update.lock').exists())

    def test_partial_write_rolls_back(self):
        self.update()
        self.write(self.remote/'SKILL.md', 'v2')
        self.write(self.remote/'references/new.md', 'v2')
        self.commit()
        copy = shutil.copy2
        def fail(src, dst, *args, **kwargs):
            if Path(src).name == 'new.md' and 'stage' in Path(src).parts:
                raise OSError('injected write failure')
            return copy(src, dst, *args, **kwargs)
        with patch.object(update.shutil, 'copy2', side_effect=fail):
            with self.assertRaises(OSError): self.update()
        self.assertEqual((self.install/'SKILL.md').read_text(), 'version one\n')
        self.assertFalse((self.install/'references/new.md').exists())
        self.assertFalse((self.install/'.local/transaction.json').exists())

    def test_interrupted_update_and_lock_block(self):
        self.write(self.install/'.local/transaction.json', '{}')
        with self.assertRaisesRegex(RuntimeError, 'Interrupted'): self.update()
        (self.install/'.local/transaction.json').unlink()
        self.write(self.install/'.local/update.lock', '')
        with self.assertRaisesRegex(RuntimeError, 'already running'): self.update()

    def test_path_escape_blocks(self):
        for name in ('../oops', '/absolute', 'C:/secret', '.git/config', '.local/settings.json', 'refs/../../oops'):
            with self.assertRaises(RuntimeError): update.safe_path(self.install, name)

    def test_incomplete_remote_blocks(self):
        (self.remote/'references/user-execution.md').unlink()
        self.commit()
        with self.assertRaisesRegex(RuntimeError, 'lacks required'): self.update()
        self.assertEqual((self.install/'SKILL.md').read_text(), 'old skill')

if __name__ == '__main__':
    unittest.main()
