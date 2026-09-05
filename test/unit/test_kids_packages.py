import hashlib
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('kids_iso_stage', ROOT / 'builder/stage-kids-packages.py')
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)
sys.path.insert(0, str(ROOT / 'configs/airootfs/usr/share/omarchy-iso'))
sys.modules.setdefault('orchestrator.archinstall_adapter', types.ModuleType('orchestrator.archinstall_adapter'))
from orchestrator import phases_impl


class KidsPackagesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.source, self.mirror, self.share = (self.path / name for name in ('source', 'mirror', 'share'))
        self.source.mkdir()
        self.packages = {}
        for name in stage.NAMES:
            filename = name + '.pkg.tar.zst'
            content = name.encode()
            (self.source / filename).write_bytes(content)
            version = '4.0.0.kids-42' if name.endswith(('base', 'settings')) else '0.1.0-42'
            self.packages[name] = dict(file=filename, pkgname=name, pkgver=version, arch='any',
                                       sha256=hashlib.sha256(content).hexdigest())
        self.release = dict(source='a' * 40, dirty=False, packages=self.packages)

    def build(self):
        (self.source / 'release.json').write_text(json.dumps(self.release))
        def metadata(command, **kwargs):
            name = Path(command[2]).name.removesuffix('.pkg.tar.zst')
            return '\n'.join(f'{key} = {self.packages[name][key]}' for key in ('pkgname', 'pkgver', 'arch'))
        with patch.object(stage.subprocess, 'check_output', side_effect=metadata), patch.object(stage.subprocess, 'run') as extract:
            stage.stage(self.source, self.mirror, self.share)
        return extract

    def test_exact_release_is_bundled_and_cached_on_target(self):
        extract = self.build()
        self.assertEqual(len(list(self.mirror.glob('*.pkg.tar.zst'))), 7)
        self.assertIn(str(self.source / 'omarchy-kids-base.pkg.tar.zst'), extract.call_args.args[0])
        ctx = types.SimpleNamespace(target=self.path / 'target')
        with patch.object(phases_impl, 'ISO_SHARE', self.share):
            phases_impl._stage_kids_packages(ctx, self.mirror)
        cache = ctx.target / 'var/cache/omarchy-kids/packages'
        self.assertEqual(json.loads((cache / 'release.json').read_text()), self.release)
        self.assertEqual(len(list(cache.glob('*.pkg.tar.zst'))), 7)
        self.assertTrue(all(file.stat().st_mode & 0o022 == 0 for file in cache.iterdir()))

    def test_missing_changed_and_mixed_packages_fail_before_staging(self):
        for mutation in ('missing', 'checksum', 'identity', 'revision', 'dirty', 'source', 'architecture'):
            with self.subTest(mutation=mutation):
                original = json.loads(json.dumps(self.release))
                if mutation == 'missing':
                    del self.packages['omarchy-kids-school']
                elif mutation == 'dirty':
                    self.release['dirty'] = True
                elif mutation == 'source':
                    self.release['source'] = 'main'
                else:
                    key, value = {'checksum': ('sha256', 'wrong'), 'identity': ('pkgname', 'other'),
                                  'revision': ('pkgver', '0.1.0-43'), 'architecture': ('arch', 'aarch64')}[mutation]
                    self.packages['omarchy-kids-core'][key] = value
                with self.assertRaises(ValueError):
                    self.build()
                self.assertFalse(self.mirror.exists())
                self.release = original
                self.packages = self.release['packages']

    def test_changed_media_is_rejected_on_install(self):
        self.build()
        (self.mirror / 'omarchy-kids-core.pkg.tar.zst').write_bytes(b'bad media')
        with patch.object(phases_impl, 'ISO_SHARE', self.share):
            with self.assertRaisesRegex(RuntimeError, 'checksum'):
                phases_impl._stage_kids_packages(types.SimpleNamespace(target=self.path / 'target'), self.mirror)

    def test_ordinary_iso_does_not_create_a_kids_cache(self):
        with patch.object(phases_impl, 'ISO_SHARE', self.share):
            phases_impl._stage_kids_packages(types.SimpleNamespace(target=self.path / 'target'), self.mirror)
        self.assertFalse((self.path / 'target').exists())


if __name__ == '__main__':
    unittest.main()
