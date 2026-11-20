"""Installer safety: preserve custom data and resolve compatible mod artifacts."""
import hashlib
import base64
import gzip
import subprocess
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('server_install', Path(__file__).resolve().parents[2] / 'infra/minecraft/install-server.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def release(name='lithium', version='v1', content=b'jar'):
    return {'project_id': name, 'id': version, 'name': name, 'version_number': version,
            'game_versions': ['26.3'], 'loaders': ['fabric'], 'date_published': '2026-11-20',
            'version_type': 'release', 'dependencies': [],
            'files': [{'primary': True, 'filename': name + '-' + version + '.jar',
                       'url': 'https://example.test/mod.jar',
                       'hashes': {'sha512': hashlib.sha512(content).hexdigest()}}]}


class InstallSafetyTests(unittest.TestCase):
    def test_complete_bootstrap_fits_ec2_and_has_valid_bash_syntax(self):
        repo = Path(__file__).resolve().parents[2]
        script = (repo / 'infra/minecraft/user-data.sh.tftpl').read_text()
        values = {'version': '26.3', 'fabric_loader_version': '0.19.5',
                  'fabric_installer_version': '1.1.1', 'fabric_api_version': '0.166.2+26.3',
                  'aws_region': 'us-east-1'}
        files = {'installer': 'infra/minecraft/install-server.py',
                 'monitor': 'backend/minecraft_proxy/activity_monitor.py',
                 'activity': 'backend/minecraft_proxy/activity.py',
                 'protocol': 'backend/minecraft_proxy/protocol.py'}
        for key, filename in files.items():
            values[key + '_gzip'] = base64.b64encode(gzip.compress((repo / filename).read_bytes(), mtime=0)).decode()
        for key, value in values.items():
            script = script.replace('${' + key + '}', value)
        self.assertNotIn('${', script)
        self.assertLessEqual(len(script.encode()), 16384)
        subprocess.run(['bash', '-n'], input=script, text=True, check=True)

    def test_settings_are_idempotent_and_preserve_custom_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'server.properties').write_text('motd=Custom title\nview-distance=16\nlevel-name=my-world\n')
            (root / 'config').mkdir()
            (root / 'config/c2me.toml').write_text('globalExecutorParallelism = 8 # old\n[custom]\nsetting = true\n')
            installer.tune_configs(root)
            first = {p.name: p.read_bytes() for p in (root / 'server.properties', root / 'config/c2me.toml')}
            installer.tune_configs(root)
            self.assertEqual(first, {p.name: p.read_bytes() for p in (root / 'server.properties', root / 'config/c2me.toml')})
            self.assertIn('motd=Custom title', first['server.properties'].decode())
            self.assertIn('level-name=my-world', first['server.properties'].decode())
            self.assertIn('view-distance=8', first['server.properties'].decode())
            self.assertEqual(first['c2me.toml'], b'globalExecutorParallelism = 1\n[custom]\nsetting = true\n')

    def test_new_c2me_key_precedes_existing_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'config').mkdir()
            (root / 'config/c2me.toml').write_text('[custom]\nvalue = 2\n')
            installer.tune_configs(root)
            self.assertTrue((root / 'config/c2me.toml').read_text().startswith('globalExecutorParallelism = 1\n[custom]'))

    def test_krypton_skips_beta_but_required_mod_cannot_be_missing(self):
        beta = dict(release('krypton'), version_type='beta')
        with patch.object(installer, 'document', return_value=[beta]):
            self.assertIsNone(installer.choose('krypton', '26.3', '0.166.2+26.3'))
        with patch.object(installer, 'document', return_value=[]):
            with self.assertRaises(RuntimeError):
                installer.choose('lithium', '26.3', '0.166.2+26.3')

    def test_fabric_api_is_pinned_and_incompatible_versions_are_rejected(self):
        pin = dict(release('fabric-api'), version_number='0.166.2+26.3')
        newer = dict(pin, version_number='0.170.0+26.3', date_published='2026-11-21')
        with patch.object(installer, 'document', return_value=[newer, pin]):
            self.assertEqual(installer.choose('fabric-api', '26.3', '0.166.2+26.3'), pin)
        with patch.object(installer, 'document', return_value=[dict(pin, game_versions=['26.2'])]):
            with self.assertRaises(RuntimeError):
                installer.choose('fabric-api', '26.3', '0.166.2+26.3')

    def test_upgrade_and_rerun_keep_one_managed_jar_and_preserve_custom_jars(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'mods').mkdir()
            custom = root / 'mods/custom.jar'
            custom.write_bytes(b'custom')
            with patch.object(installer, 'PROJECTS', ('lithium',)), patch.object(installer, 'fetch', return_value=b'jar'):
                for version in ('v1', 'v2', 'v2'):
                    with patch.object(installer, 'choose', return_value=release(version=version)):
                        installer.install_mods(root, '26.3', '0.166.2+26.3')
            self.assertEqual(sorted(p.name for p in (root / 'mods').glob('*.jar')), ['custom.jar', 'lithium-v2.jar'])
            self.assertEqual(custom.read_bytes(), b'custom')

    def test_failed_checksum_preserves_previous_install(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(installer, 'PROJECTS', ('lithium',)), patch.object(installer, 'choose', return_value=release()), patch.object(installer, 'fetch', return_value=b'jar'):
                installer.install_mods(root, '26.3', '0.166.2+26.3')
            before = (root / 'mods/.portfolio-managed.json').read_bytes()
            with patch.object(installer, 'PROJECTS', ('lithium',)), patch.object(installer, 'choose', return_value=release(version='v2')), patch.object(installer, 'fetch', return_value=b'corrupt'):
                with self.assertRaises(RuntimeError):
                    installer.install_mods(root, '26.3', '0.166.2+26.3')
            self.assertEqual((root / 'mods/.portfolio-managed.json').read_bytes(), before)
            self.assertTrue((root / 'mods/lithium-v1.jar').exists())

    def test_required_dependencies_are_installed(self):
        parent = release()
        parent['dependencies'] = [{'dependency_type': 'required', 'version_id': 'dependency'}]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(installer, 'PROJECTS', ('lithium',)), patch.object(installer, 'choose', return_value=parent), patch.object(installer, 'document', return_value=release('dependency')), patch.object(installer, 'fetch', return_value=b'jar'):
                installer.install_mods(root, '26.3', '0.166.2+26.3')
            self.assertEqual(len(list((root / 'mods').glob('*.jar'))), 2)
