"""Map transfer safety: archives cannot change binaries or escape the world."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('world_remote', Path(__file__).resolve().parents[2] / 'scripts/minecraft-world-remote.py')
world = importlib.util.module_from_spec(spec)
spec.loader.exec_module(world)


class MapTransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'server'
        self.root.mkdir()
        self.transfer = Path(self.temp.name) / 'transfers'
        self.transfer.mkdir()
        self.hold = Path(self.temp.name) / 'hold.json'
        self.hold.write_text(json.dumps({'token': 'owner'}))
        (self.root / 'server.properties').write_text('level-name=custom-map\n')
        self.original = self.root / 'custom-map'
        self.original.mkdir()
        (self.original / 'level.dat').write_bytes(b'original')
        for name, value in [('ROOT', self.root), ('TRANSFER', self.transfer), ('HOLD', self.hold)]:
            patcher = patch.object(world, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(world, 'active', return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def archive(self, entries):
        path = self.transfer / 'import.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            for key, value in entries.items():
                archive.writestr(key, value)
        return path

    def test_only_map_directory_is_selected(self):
        self.assertEqual(world.world(), self.original)
        for name in ('../elsewhere', '.', '/etc', 'nested/map'):
            (self.root / 'server.properties').write_text('level-name=' + name)
            with self.assertRaises(RuntimeError):
                world.world()

    def test_rejects_traversal_and_non_world_files_without_touching_map(self):
        for entries in ({'world/level.dat': b'new', '../server.jar': b'bad'}, {'world/level.dat': b'new', 'mods/mod.jar': b'bad'}, {'level.dat': b'new'}):
            path = self.archive(entries)
            with self.assertRaises(RuntimeError):
                world.restore(str(path), 'owner')
            self.assertEqual((self.original / 'level.dat').read_bytes(), b'original')

    def test_rejects_symlink_zip_entry(self):
        path = self.archive({'world/level.dat': b'new'})
        info = zipfile.ZipInfo('world/link')
        info.create_system = 3
        info.external_attr = 0o120777 << 16
        with zipfile.ZipFile(path, 'a') as archive:
            archive.writestr(info, '/etc/passwd')
        with self.assertRaises(RuntimeError):
            world.restore(str(path), 'owner')

    def test_successful_restore_retains_previous_map_and_server_files(self):
        path = self.archive({'world/level.dat': b'new', 'world/DIM-1/region/r.0.0.mca': b'nether'})
        (self.root / 'server.jar').write_bytes(b'custom-binary')
        with patch.object(world.os, 'chown'), patch.object(world.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=1000, pw_gid=1000)):
            world.restore(str(path), 'owner')
        self.assertEqual((self.original / 'level.dat').read_bytes(), b'new')
        self.assertEqual((self.original / 'DIM-1/region/r.0.0.mca').read_bytes(), b'nether')
        self.assertEqual((self.root / 'server.jar').read_bytes(), b'custom-binary')
        previous = list(self.root.glob('.world-before-import-*'))
        self.assertEqual(len(previous), 1)
        self.assertEqual((previous[0] / 'level.dat').read_bytes(), b'original')

    def test_backup_includes_only_map_and_all_dimensions(self):
        (self.original / 'DIM-1').mkdir()
        (self.original / 'DIM-1/region.mca').write_bytes(b'nether')
        (self.root / 'server.jar').write_bytes(b'not-a-map')
        account = SimpleNamespace(pw_uid=1000, pw_gid=1000)
        with patch.object(world.os, 'chown'), patch.object(world.pwd, 'getpwnam', return_value=account):
            world.backup('owner')
        archives = list(self.transfer.glob('*.zip'))
        self.assertEqual(len(archives), 1)
        with zipfile.ZipFile(archives[0]) as archive:
            self.assertEqual(set(archive.namelist()), {'world/level.dat', 'world/DIM-1/region.mca'})
            self.assertIsNone(archive.testzip())

    def test_another_transfer_cannot_take_or_release_maintenance_hold(self):
        with self.assertRaises(RuntimeError):
            world.require_paused('other')
        with self.assertRaises(RuntimeError):
            world.resume('other')
        with self.assertRaises(RuntimeError):
            world.pause('other')
        self.assertTrue(self.hold.exists())
