"""Exercise transfers against a local device double: never write to a real Apple TV."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import struct
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from save_import import SaveImporter, stored_save_hash


class Failure(Exception):
    pass


class Device:
    Failure = Failure
    bundle = 'dev.tvport.team.g010085001a17c000'
    app_path = '/private/var/containers/Bundle/Application/test/DmIOS.app'

    def __init__(self, root):
        self.DATA = root / 'data'
        self.remote = root / 'device'
        (self.remote / 'Library/Caches').mkdir(parents=True)
        self.running = False
        self.fail_copy = False
        self.corrupt_copy = False
        self.fail_backup = False
        self.writes = []
        self.write_had_backup = []

    def devicectl_json(self, *args, timeout=None):
        args = list(args)
        def arg(flag): return args[args.index(flag) + 1]
        if args[:3] == ['device', 'info', 'apps']:
            return {'result': {'apps': [
                dict(bundleIdentifier=self.bundle, name='Test Game', version='1', containerAccessible=True, url='file://' + self.app_path + '/'),
                dict(bundleIdentifier='com.example.unrelated', name='Unrelated', containerAccessible=True, url='file:///apps/Music.app/'),
                dict(bundleIdentifier='com.example.game', name='Store Game', containerAccessible=False, url='file:///apps/StoreGame.app/') ]}}
        if args[:3] == ['device', 'info', 'processes']:
            return {'result': {'runningProcesses': [dict(processIdentifier=12, executable='file://' + self.app_path + '/DmIOS')] if self.running else []}}
        if args[:3] == ['device', 'process', 'terminate']:
            self.running = False
            return {'result': {}}
        if args[:3] == ['device', 'info', 'files']:
            files = []
            base = self.remote / arg('--subdirectory')
            entries = base.iterdir() if '--no-recurse' in args else base.rglob('*')
            for p in entries:
                st = p.stat()
                files.append(dict(relativePath=p.relative_to(base).as_posix(),
                                  metadata=dict(size=st.st_size, lastModDate=st.st_mtime_ns), resources=dict(isDirectory=p.is_dir())))
            return {'result': {'files': files}}
        if args[:2] == ['device', 'copy']:
            direction = args[2]
            src = Path(arg('--source')); dst = Path(arg('--destination'))
            if direction == 'from':
                src = self.remote / src
                if self.fail_backup:
                    raise Failure('Backup interrupted')
            else:
                dst = self.remote / dst
                self.writes.append(str(dst))
                self.write_had_backup.append(any(json.loads(p.read_text()).get('backup_ready') for p in (self.DATA / 'save-imports').glob('*/record.json')))
            if src.is_dir():
                if dst.exists() and '--remove-existing-content' in args:
                    shutil.rmtree(dst)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(src, dst, dirs_exist_ok=True)
                if direction == 'to' and self.corrupt_copy:
                    self.corrupt_copy = False
                    next(p for p in dst.rglob('*') if p.is_file()).write_bytes(b'bad bytes')
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            if direction == 'to' and self.fail_copy:
                self.fail_copy = False
                raise Failure('Interrupted after partial write')
            return {'result': {}}
        raise AssertionError(args)


def packed_save(contents=b'original persistent save'):
    path = b'save/data.bin'
    header = struct.pack('<BBHHHQq', 2, 0, len(path), 0, 0, len(contents), 123)
    digest = hashlib.sha256(header[:16] + path + contents).hexdigest()[:32]
    raw = b'DMSYNC1\n' + struct.pack('<II', 1, 1) + digest.encode() + struct.pack('<q', 123) + b'010085001A17C000'.ljust(24, b'\0') + b'test'.ljust(64, b'\0')
    raw += header + path + contents + b'DMSYNCE\n'
    lib = ctypes.CDLL('/usr/lib/libcompression.dylib')
    encode = lib.compression_encode_buffer
    encode.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_int]
    encode.restype = ctypes.c_size_t
    out = ctypes.create_string_buffer(len(raw) + 65536)
    size = encode(out, len(out), raw, len(raw), None, 0x801)
    assert size
    return b'DMZ2' + struct.pack('<Q', len(raw)) + out.raw[:size], digest


class Saves(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.device = Device(self.root)
        self.tool = SaveImporter(self.device)
        self.source = self.root / 'Ryujinx save'
        self.source.mkdir()
        (self.source / 'data.bin').write_bytes(b'new Mac progress')
        old = self.device.remote / 'Library/Caches/save'
        old.mkdir()
        (old / 'data.bin').write_bytes(b'original TV progress')
        (old / 'obsolete.bin').write_bytes(b'remove on import')
        other = self.device.remote / 'Library/Caches/save.p-other'
        other.mkdir()
        (other / 'data.bin').write_bytes(b'other player')

    def tearDown(self):
        self.tmp.cleanup()

    def transfer(self):
        return self.tool.transfer('tv', self.device.bundle, 'save', self.source)

    def test_import_backs_up_first_replaces_and_can_restore_both_directions(self):
        self.device.running = True
        result = self.transfer()
        self.assertFalse(self.device.running)
        self.assertTrue(all(self.device.write_had_backup))
        before = Path(result['backup'])
        self.assertEqual((before / 'data.bin').read_bytes(), b'original TV progress')
        live = self.device.remote / 'Library/Caches/save'
        self.assertFalse((live / 'obsolete.bin').exists())
        self.assertEqual((live / 'data.bin').read_bytes(), b'new Mac progress')
        self.assertEqual((self.device.remote / 'Library/Caches/save.p-other/data.bin').read_bytes(), b'other player')
        self.assertEqual((self.source / 'data.bin').read_bytes(), b'new Mac progress')
        first = self.tool.history('tv', self.device.bundle)[0]
        self.tool.restore('tv', self.device.bundle, first['id'])
        self.assertEqual((live / 'data.bin').read_bytes(), b'original TV progress')
        self.assertTrue((live / 'obsolete.bin').exists())
        newest = self.tool.history('tv', self.device.bundle)[0]
        self.tool.restore('tv', self.device.bundle, newest['id'])
        self.assertEqual((live / 'data.bin').read_bytes(), b'new Mac progress')

    def test_failed_backup_never_writes_device(self):
        self.device.fail_backup = True
        with self.assertRaises(Failure): self.transfer()
        self.assertEqual(self.device.writes, [])
        self.assertEqual(self.tool.history('tv', self.device.bundle), [])

    def test_missing_file_listing_is_not_treated_as_empty(self):
        with patch.object(self.tool, 'query', return_value={}):
            with self.assertRaisesRegex(Failure, 'no file listing'):
                self.tool.listing('tv', self.device.bundle)
        self.assertEqual(self.device.writes, [])

    def test_partial_copy_and_failed_verification_roll_back(self):
        for failure in ('fail_copy', 'corrupt_copy'):
            setattr(self.device, failure, True)
            with self.assertRaisesRegex(Failure, 'original save was restored'): self.transfer()
            live = self.device.remote / 'Library/Caches/save'
            self.assertEqual((live / 'data.bin').read_bytes(), b'original TV progress')
            self.assertTrue((live / 'obsolete.bin').exists())

    def test_export_is_read_only_and_available_for_restore(self):
        result = self.tool.export('tv', self.device.bundle, 'save')
        self.assertEqual(Path(result['backup']).name, 'Save Files')
        self.assertEqual(self.device.writes, [])
        self.assertEqual(Path(result['backup']).joinpath('data.bin').read_bytes(), b'original TV progress')
        self.assertEqual(self.tool.history('tv', self.device.bundle)[0]['status'], 'exported')

    def test_local_import_keeps_independent_copies_without_contacting_tv(self):
        with patch.object(self.device, 'devicectl_json', side_effect=AssertionError('Local import contacted TV')):
            first = self.tool.store_import('tv', self.device.bundle, 'save', self.source, 'Test Game')
            second = self.tool.store_import('tv', self.device.bundle, 'save', self.source, 'Test Game')
            self.assertNotEqual(first['backup'], second['backup'])
            self.assertEqual(len(self.tool.history('tv', self.device.bundle)), 2)
            self.assertEqual(self.tool.history('tv', self.device.bundle)[0]['status'], 'imported-copy')
            self.assertEqual(Path(first['backup']).joinpath('data.bin').read_bytes(), b'new Mac progress')
            (self.source / 'data.bin').write_bytes(b'changed later')
            self.assertEqual(Path(first['backup']).joinpath('data.bin').read_bytes(), b'new Mac progress')
        self.assertEqual(self.device.writes, [])
        self.assertEqual((self.device.remote / 'Library/Caches/save/data.bin').read_bytes(), b'original TV progress')

    def test_failed_local_import_does_not_publish_partial_copy(self):
        with patch('save_import.shutil.copy2', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.tool.store_import('tv', self.device.bundle, 'save', self.source, 'Test Game')
        self.assertEqual(self.tool.history('tv', self.device.bundle), [])
        self.assertEqual(list(self.tool.home.iterdir()), [])

    def test_restore_local_import_to_another_existing_player_preserves_original(self):
        imported = self.tool.store_import('tv', self.device.bundle, 'save', self.source, 'Test Game')
        result = self.tool.restore('tv', self.device.bundle, Path(imported['backup']).parent.name, 'save.p-other')
        self.assertEqual((self.device.remote / 'Library/Caches/save/data.bin').read_bytes(), b'original TV progress')
        self.assertEqual((self.device.remote / 'Library/Caches/save.p-other/data.bin').read_bytes(), b'new Mac progress')
        self.assertEqual(Path(result['backup']).joinpath('data.bin').read_bytes(), b'other player')
        self.assertEqual(Path(imported['backup']).joinpath('data.bin').read_bytes(), b'new Mac progress')
        with self.assertRaisesRegex(Failure, 'existing player'):
            self.tool.restore('tv', self.device.bundle, Path(imported['backup']).parent.name, 'save.p-missing')

    def test_saved_games_and_history_work_without_device_access(self):
        self.tool.export('tv', self.device.bundle, 'save')
        self.tool.export('tv', self.device.bundle, 'save.p-other')
        with patch.object(self.device, 'devicectl_json', side_effect=AssertionError('Offline browsing contacted the TV')):
            catalog = self.tool.saved_games('tv')
            self.assertEqual([g['id'] for g in catalog['apps']], [self.device.bundle])
            self.assertEqual(catalog['apps'][0]['version'], '1')
            self.assertEqual(catalog['devices'][0]['id'], 'tv')
            self.assertEqual(len(self.tool.history('tv', self.device.bundle)), 2)
            self.assertEqual(self.tool.saved_games('another-tv')['apps'], [])
            self.assertEqual(self.tool.saved_games()['devices'][0]['id'], 'tv')

    def test_saved_games_read_legacy_cloud_records_and_ignore_incomplete_backups(self):
        self.device.ICLOUD = self.root / 'iCloud'; self.device.ICLOUD.mkdir()
        cloud = SaveImporter(self.device, icloud=True)
        result = cloud.export('tv', self.device.bundle, 'save')
        folder = Path(result['backup']); folder.rename(folder.parent / 'before')
        record = folder.parent / 'record.json'
        data = json.loads(record.read_text()); data.pop('version'); data.pop('title_id')
        record.write_text(json.dumps(data))
        broken = cloud.home / 'broken'; broken.mkdir(); (broken / 'record.json').write_text('[]')
        with patch.object(self.device, 'devicectl_json', side_effect=AssertionError('TV must not be queried')):
            local = SaveImporter(self.device)
            self.assertEqual(len(local.saved_games('tv')['apps']), 1)
            data['backup_ready'] = False; record.write_text(json.dumps(data))
            self.assertEqual(local.saved_games('tv')['apps'], [])

    def test_legacy_before_folder_is_renamed_and_still_restores(self):
        result = self.tool.export('tv', self.device.bundle, 'save')
        folder = Path(result['backup'])
        folder.rename(folder.parent / 'before')
        history = self.tool.history('tv', self.device.bundle)
        self.assertEqual(history[0]['folder'], str(folder))
        self.assertTrue((folder / 'data.bin').is_file())
        self.assertFalse((folder.parent / 'before').exists())
        self.tool.restore('tv', self.device.bundle, history[0]['id'])
        self.assertEqual((self.device.remote / 'Library/Caches/save/data.bin').read_bytes(), b'original TV progress')

    def test_icloud_backups_remain_visible_and_restorable_when_setting_changes(self):
        local = self.tool.export('tv', self.device.bundle, 'save')
        self.device.ICLOUD = self.root / 'iCloud'
        self.device.ICLOUD.mkdir()
        cloud = SaveImporter(self.device, icloud=True)
        result = cloud.export('tv', self.device.bundle, 'save')
        self.assertTrue(Path(result['backup']).is_relative_to(self.device.ICLOUD))
        self.assertEqual(len(cloud.history('tv', self.device.bundle)), 2)
        self.assertEqual(self.device.writes, [])
        # Turning iCloud off must not hide the backup or prevent restoring it.
        local_tool = SaveImporter(self.device, icloud=False)
        self.assertEqual(len(local_tool.history('tv', self.device.bundle)), 2)
        restored = local_tool.restore('tv', self.device.bundle, Path(result['backup']).parent.name)
        self.assertTrue(Path(restored['backup']).is_relative_to(self.device.DATA))
        # Turning it back on makes the pre-restore backup in iCloud, even for an older local backup.
        restored = cloud.restore('tv', self.device.bundle, Path(local['backup']).parent.name)
        self.assertTrue(Path(restored['backup']).is_relative_to(self.device.ICLOUD))

    def test_icloud_unavailable_keeps_backups_local_without_creating_cloud_root(self):
        self.device.ICLOUD = self.root / 'unavailable-iCloud'
        tool = SaveImporter(self.device, icloud=True)
        result = tool.export_all('tv')
        self.assertFalse(tool.icloud_available)
        self.assertEqual(result['errors'], [])
        self.assertTrue(all(Path(item['backup']).is_relative_to(self.device.DATA) for item in result['saved']))
        self.assertFalse(self.device.ICLOUD.exists())
        self.assertEqual(self.device.writes, [])

    def test_backup_all_includes_all_games_and_player_slots_and_skips_empty(self):
        apps = self.tool.apps('tv')
        second = dict(apps[0], id='org.nxnative.second', name='Second Game')
        with patch.object(self.tool, 'apps', return_value=apps + [second]):
            result = self.tool.export_all('tv')
        self.assertEqual(len(result['saved']), 4)
        self.assertEqual(result['files'], 6)
        self.assertEqual(result['skipped'], 2)
        self.assertEqual(result['errors'], [])
        self.assertEqual(len(self.tool.history('tv', self.device.bundle)), 2)
        self.assertEqual(len(self.tool.history('tv', second['id'])), 2)
        self.assertEqual(self.device.writes, [])

    def test_backup_all_reports_failures_and_keeps_other_successful_backups(self):
        export = self.tool.export
        def fail_one(device, bundle, slot, **kwargs):
            if slot == 'save':
                raise Failure('Connection interrupted')
            return export(device, bundle, slot, **kwargs)
        with patch.object(self.tool, 'export', side_effect=fail_one):
            result = self.tool.export_all('tv')
        self.assertEqual(len(result['saved']), 1)
        self.assertEqual(len(result['errors']), 1)
        self.assertIn('Connection interrupted', result['errors'][0])
        self.assertEqual(self.tool.history('tv', self.device.bundle)[0]['slot'], 'save.p-other')
        self.assertEqual(self.device.writes, [])

    def test_backup_all_finds_persistent_only_player_slots(self):
        packed, _ = packed_save()
        prefs = self.device.remote / ('Library/Preferences/' + self.device.bundle + '.plist')
        prefs.parent.mkdir(parents=True)
        prefs.write_bytes(plistlib.dumps({'dmsave:save.p-missing/010085001A17C000/save.dmsync': packed}))
        result = self.tool.export_all('tv')
        self.assertEqual(result['errors'], [])
        saved = next(item for item in result['saved'] if item['slot'] == 'save.p-missing')
        self.assertEqual((Path(saved['backup']) / 'data.bin').read_bytes(), b'original persistent save')
        self.assertEqual(self.device.writes, [])

    def test_rejects_links_wrong_app_and_wrong_backup_owner(self):
        (self.source / 'link').symlink_to(self.source / 'data.bin')
        with self.assertRaises(Failure): self.transfer()
        (self.source / 'link').unlink()
        with self.assertRaises(Failure): self.tool.transfer('tv', 'com.example.unrelated', 'save', self.source)
        with self.assertRaises(Failure): self.tool.transfer('tv', self.device.bundle, '../save', self.source)
        self.assertEqual(self.device.writes, [])
        self.transfer()
        history = self.tool.history('tv', self.device.bundle)
        with self.assertRaises(Failure): self.tool.restore('different-tv', self.device.bundle, history[0]['id'])
        with self.assertRaises(Failure): self.tool.restore('tv', self.device.bundle, '../outside')

    def test_empty_and_wrapper_sources_are_rejected(self):
        empty = self.root / 'empty'; empty.mkdir()
        with self.assertRaises(Failure): self.tool.source(empty)
        (self.source / 'save').mkdir()
        with self.assertRaises(Failure): self.tool.source(self.source)

    def test_apps_and_player_slots(self):
        apps = self.tool.apps('tv')
        self.assertEqual([a['name'] for a in apps if a['compatible']], ['Test Game'])
        self.assertEqual(apps[0]['title_id'], '010085001A17C000')
        slots = self.tool.targets('tv', self.device.bundle)
        self.assertIn('save.p-other', [s['id'] for s in slots])

    @unittest.skipUnless(sys.platform == 'darwin', 'Apple compression')
    def test_persistent_original_survives_cache_purge_and_sets_sync_baseline(self):
        packed, digest = packed_save()
        self.assertEqual(stored_save_hash(packed), digest)
        prefs = self.device.remote / ('Library/Preferences/' + self.device.bundle + '.plist')
        prefs.parent.mkdir(parents=True)
        prefs.write_bytes(plistlib.dumps({'dmsave:save/010085001A17C000/save.dmsync': packed}))
        shutil.rmtree(self.device.remote / 'Library/Caches/save')
        result = self.transfer()
        self.assertEqual((Path(result['backup']) / 'data.bin').read_bytes(), b'original persistent save')
        self.assertEqual((self.device.remote / 'Library/Caches/save.sync').read_text(), 'base\t' + digest + '\n')
        self.assertEqual(self.tool.history('tv', self.device.bundle)[0]['files'], 1)

    @unittest.skipUnless(sys.platform == 'darwin', 'Apple compression')
    def test_export_recovers_persistent_save_when_cache_is_empty(self):
        packed, _ = packed_save()
        prefs = self.device.remote / ('Library/Preferences/' + self.device.bundle + '.plist')
        prefs.parent.mkdir(parents=True)
        prefs.write_bytes(plistlib.dumps({'dmsave:save/010085001A17C000/save.dmsync': packed}))
        shutil.rmtree(self.device.remote / 'Library/Caches/save')
        result = self.tool.export('tv', self.device.bundle, 'save')
        self.assertEqual((Path(result['backup']) / 'data.bin').read_bytes(), b'original persistent save')
        self.assertEqual(self.device.writes, [])

    def test_empty_directories_are_kept(self):
        (self.source / 'empty-slot').mkdir()
        self.transfer()
        self.assertTrue((self.device.remote / 'Library/Caches/save/empty-slot').is_dir())
        result = self.tool.export('tv', self.device.bundle, 'save')
        self.assertTrue((Path(result['backup']) / 'empty-slot').is_dir())

    @unittest.skipUnless(sys.platform == 'darwin', 'Apple compression')
    def test_damaged_persistent_save_blocks_import(self):
        prefs = self.device.remote / ('Library/Preferences/' + self.device.bundle + '.plist')
        prefs.parent.mkdir(parents=True)
        prefs.write_bytes(plistlib.dumps({'dmsave:save/010085001A17C000/save.dmsync': b'bad'}))
        with self.assertRaises(Failure): self.transfer()
        self.assertEqual(self.device.writes, [])
