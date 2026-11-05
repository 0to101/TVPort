"""Installed-game discovery and reversible imports of save folders."""
import ctypes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import plistlib
import re
import shutil
import stat
import struct
import time
from urllib.parse import unquote, urlparse
import uuid

SLOT = re.compile(r'^save(?:\.p-[a-z0-9-]+)?(?:_device)?$')
TITLE = re.compile(r'(?:^|[.g_-])(0100[0-9a-f]{12})(?:$|[._-])', re.I)


class SaveImporter:
    def __init__(self, backend, icloud=False):
        self.b = backend
        local = backend.DATA / 'save-imports'
        cloud = getattr(backend, 'ICLOUD', None)
        self.icloud_available = cloud is not None and cloud.is_dir()
        cloud_home = cloud / getattr(backend, 'ICLOUD_SAVES', 'TVPort Saves') / 'Managed Backups' if cloud is not None else None
        self.home = cloud_home if icloud and self.icloud_available else local
        # Keep earlier backups visible and restorable when the preference changes.
        self.roots = list(dict.fromkeys(root for root in (self.home, local, cloud_home) if root is not None))

    def fail(self, text):
        raise self.b.Failure(text)

    def query(self, *args):
        answer = self.b.devicectl_json(*args, timeout=60)
        if answer.get('error'):
            detail = answer['error'].get('userInfo', {}).get('NSLocalizedDescription', {})
            self.fail(detail.get('string') or 'The Apple TV could not complete the request. Wake it and try again.')
        if 'result' not in answer:
            self.fail('The Apple TV returned no result. Try again.')
        return answer['result']

    def apps(self, device):
        result = self.query('device', 'info', 'apps', '--device', device, '--include-all-apps')
        apps = []
        for item in result.get('apps', []):
            bundle = item.get('bundleIdentifier', '')
            if not bundle:
                continue
            path = unquote(urlparse(item.get('url', '')).path).rstrip('/')
            native = Path(path).name in ('DmIOS.app', 'NativeGameTV.app') or bundle.startswith(('dev.tvport.', 'org.nxnative.'))
            readable = item.get('containerAccessible') is True
            match = TITLE.search(bundle)
            apps.append(dict(id=bundle, name=item.get('name') or bundle, version=item.get('version') or '',
                             title_id=match.group(1).upper() if match else '', path=path,
                             compatible=native and readable,
                             reason='' if native and readable else 'This app does not expose a supported native-game save container.'))
        return sorted(apps, key=lambda a: (not a['compatible'], a['name'].casefold(), a['id']))

    def app(self, device, bundle):
        app = next((a for a in self.apps(device) if a['id'] == bundle), None)
        if not app or not app['compatible'] or not app['path'].endswith('.app'):
            self.fail('Select an installed native game with an accessible save container.')
        return app

    def listing(self, device, bundle):
        files = {}
        def read(subdirectory, recurse):
            result = self.query('device', 'info', 'files', '--device', device, '--domain-type', 'appDataContainer',
                                '--domain-identifier', bundle, '--subdirectory', subdirectory,
                                '--recurse' if recurse else '--no-recurse')
            if not isinstance(result.get('files'), list):
                self.fail('The Apple TV returned no file listing. No saves were changed.')
            prefix = subdirectory.removeprefix('Library').strip('/')
            entries = []
            for f in result.get('files', []):
                name = f.get('relativePath', '')
                if not PurePosixPath(name).parts or name.startswith('/') or any(p in ('.', '..') for p in name.split('/')):
                    self.fail('The Apple TV returned an invalid file path.')
                full = prefix + '/' + name if prefix else name
                if f.get('resources', {}).get('isSymbolicLink'):
                    self.fail('The save container contains an unsupported symbolic link.')
                files[full] = f
                entries.append((full, f))
            return entries
        # Never recurse through romfs, shaders or the rest of a game's large cache.
        roots = dict(read('Library', False))
        if 'Caches' in roots:
            for name, f in read('Library/Caches', False):
                if SLOT.fullmatch(name.removeprefix('Caches/')) and f.get('resources', {}).get('isDirectory'):
                    read('Library/' + name, True)
        if 'Preferences' in roots:
            read('Library/Preferences', True)
        return files

    def copy(self, direction, device, bundle, source, destination, replace=False):
        args = ['device', 'copy', direction, '--device', device, '--domain-type', 'appDataContainer',
                '--domain-identifier', bundle, '--source', str(source), '--destination', str(destination)]
        if replace:
            args += ['--remove-existing-content', 'true']
        self.query(*args)

    def preferences(self, device, bundle, listing, into):
        name = f'Preferences/{bundle}.plist'
        if name not in listing:
            return {}
        target = into / 'preferences.plist'
        self.copy('from', device, bundle, 'Library/' + name, target)
        try:
            return plistlib.loads(target.read_bytes())
        except (OSError, plistlib.InvalidFileException, ValueError):
            self.fail('The game preferences could not be read. No saves were changed.')

    def targets(self, device, bundle):
        import tempfile
        self.app(device, bundle)
        files = self.listing(device, bundle)
        with tempfile.TemporaryDirectory() as tmp:
            prefs = self.preferences(device, bundle, files, Path(tmp))
        slots = {'save', 'save_device'}
        # Persistent player saves can remain after tvOS has purged their cache.
        for key in prefs:
            if key.startswith('dmsave:'):
                base = key.removeprefix('dmsave:').split('/')[0]
                if SLOT.fullmatch(base):
                    slots.update((base, base + '_device'))
        for name in files:
            match = re.fullmatch(r'Preferences/tv-saves/(save(?:\.p-[a-z0-9-]+)?)_[^/]+_save\.dmsync', name)
            if match:
                slots.update((match[1], match[1] + '_device'))
        for name in files:
            parts = name.split('/')
            if len(parts) >= 2 and parts[0] == 'Caches' and SLOT.fullmatch(parts[1]):
                slots.add(parts[1])
        players = prefs.get('dmplayers', {})
        if not isinstance(players, dict):
            players = {}
        for folder in players.values():
            if isinstance(folder, str) and SLOT.fullmatch(folder):
                slots.update((folder, folder + '_device'))
        names = {v: k for k, v in players.items() if isinstance(v, str) and isinstance(k, str)}
        answer = []
        for slot in sorted(slots):
            base = slot.removesuffix('_device')
            label = names.get(base, 'Default player' if base == 'save' else base.removeprefix('save.p-'))
            if slot.endswith('_device'):
                label += ' — device/shared save'
            prefix = f'Caches/{slot}/'
            count = sum(name.startswith(prefix) and not f.get('resources', {}).get('isDirectory') for name, f in files.items())
            answer.append(dict(id=slot, name=label, files=count))
        return answer

    def source(self, folder, allow_empty=False):
        folder = Path(folder)
        if folder.is_symlink() or not folder.is_dir():
            self.fail('Choose a save folder, not an archive or a shortcut.')
        files, directories, size = [], [], 0
        for root, dirs, names in os.walk(folder, followlinks=False):
            for name in dirs + names:
                p = Path(root) / name
                mode = p.lstat().st_mode
                if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                    self.fail('Save folders cannot contain symbolic links or special files.')
            dirs[:] = [d for d in dirs if d != '__MACOSX']
            directories += [(Path(root) / d).relative_to(folder).as_posix() for d in dirs]
            for name in names:
                if name == '.DS_Store' or name.startswith('._'):
                    continue
                p = Path(root) / name
                files.append(p.relative_to(folder).as_posix())
                size += p.stat().st_size
        if not files and not allow_empty:
            self.fail('This folder has no save files. Choose the folder containing the actual save data.')
        if len(files) > 100000 or size > 8 * 1024**3:
            self.fail('The selection is too large for a save import. Choose one game’s save folder.')
        if any((folder / name).is_dir() for name in ('save', 'save_device', 'bis', 'sdcard')):
            self.fail('Choose the inner save folder containing the game files, rather than the whole backup or emulator folder.')
        return dict(folder=str(folder), files=len(files), bytes=size, paths=sorted(files), directories=sorted(directories))

    @staticmethod
    def backup_folder(work):
        folder = work / 'Save Files'
        legacy = work / 'before'
        if not folder.exists() and legacy.is_dir():
            try:
                legacy.rename(folder)
            except OSError:
                # An offline/read-only backup can still be restored under its old name.
                return folder if folder.is_dir() else legacy
        return folder

    def history(self, device, bundle):
        records = []
        seen = set()
        for p in (p for root in self.roots for p in root.glob('*/record.json')):
            try:
                r = json.loads(p.read_text())
                if p.parent.name not in seen and r['device'] == device and r['bundle'] == bundle and r.get('backup_ready') and r.get('previous_files', 0):
                    seen.add(p.parent.name)
                    records.append(dict(id=p.parent.name, date=r['date'], game=r['game'], slot=r['slot'],
                                        files=r['previous_files'], status=r['status'], folder=str(self.backup_folder(p.parent))))
            except (OSError, ValueError, KeyError):
                continue
        return sorted(records, key=lambda r: r['date'], reverse=True)

    def stop_game(self, device, app):
        processes = self.query('device', 'info', 'processes', '--device', device)
        for p in processes.get('runningProcesses', []):
            path = unquote(urlparse(str(p.get('executable', ''))).path)
            if path.startswith(app['path'] + '/'):
                pid = p.get('processIdentifier')
                if not isinstance(pid, int) or pid <= 0:
                    self.fail('Could not identify the running game. Close it on the Apple TV and try again.')
                self.query('device', 'process', 'terminate', '--device', device, '--pid', str(pid))
        # A failed termination must not allow the suspended game to overwrite the import.
        after = self.query('device', 'info', 'processes', '--device', device)
        if any(unquote(urlparse(str(p.get('executable', ''))).path).startswith(app['path'] + '/') for p in after.get('runningProcesses', [])):
            self.fail('The game is still running. Close it on the Apple TV and try again.')

    def remote_hash(self, device, bundle, slot, listing, prefs, work):
        base = slot.removesuffix('_device')
        prefix = f'dmsave:{base}/'
        candidates = [value for key, value in prefs.items() if key.startswith(prefix)]
        stored_names = {key.removeprefix('dmsave:').replace('/', '_') for key in prefs if key.startswith(prefix)}
        for name, f in listing.items():
            if name.startswith(f'Preferences/tv-saves/{base}_') and name.endswith('_save.dmsync') and Path(name).name not in stored_names and not f.get('resources', {}).get('isDirectory'):
                target = work / ('stored-' + str(len(candidates)))
                self.copy('from', device, bundle, 'Library/' + name, target)
                candidates.append(target.read_bytes())
        if not candidates:
            return ''
        if len(candidates) != 1:
            self.fail('More than one persistent save matches this slot. No saves were changed.')
        try:
            return stored_save_hash(candidates[0], into=work / 'persistent')
        except (ValueError, OSError):
            self.fail('The existing persistent save could not be validated. No saves were changed.')

    def transfer(self, device, bundle, slot, folder, restore_id=None):
        if not SLOT.fullmatch(slot):
            self.fail('Invalid destination save slot.')
        source = self.source(folder)
        app = self.app(device, bundle)
        self.home.mkdir(parents=True, exist_ok=True)
        work = self.home / uuid.uuid4().hex
        work.mkdir()
        incoming = work / 'imported'
        incoming.mkdir()
        for name in source['directories']:
            (incoming / name).mkdir(parents=True, exist_ok=True)
        # Freeze the source before touching the Apple TV; the original folder is never modified.
        for name in source['paths']:
            original = Path(folder) / name
            stamp = original.stat()
            dest = incoming / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, dest)
            after = original.stat()
            if (stamp.st_size, stamp.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                self.fail('The source save changed while it was being copied. Quit the game on your Mac and try again. No Apple TV saves were changed.')
        record = dict(device=device, bundle=bundle, game=app['name'], slot=slot, date=time.time(),
                      status='preparing', previous_files=0, backup_ready=False, restored_from=restore_id)
        def save_record():
            (work / 'record.json').write_text(json.dumps(record, indent=2))
        save_record()
        self.stop_game(device, app)
        listing = self.listing(device, bundle)
        prefs = self.preferences(device, bundle, listing, work)
        remote_hash = self.remote_hash(device, bundle, slot, listing, prefs, work)
        prefix = f'Caches/{slot}/'
        names = [n for n, f in listing.items() if n.startswith(prefix) and not f.get('resources', {}).get('isDirectory')]
        before = work / 'Save Files'
        before.mkdir()
        for name, f in listing.items():
            if name.startswith(prefix) and f.get('resources', {}).get('isDirectory'):
                (before / name[len(prefix):]).mkdir(parents=True, exist_ok=True)
        for name in names:
            dest = before / name[len(prefix):]
            dest.parent.mkdir(parents=True, exist_ok=True)
            self.copy('from', device, bundle, 'Library/' + name, dest)
            expected = listing[name].get('metadata', {}).get('size')
            if not dest.is_file() or (expected is not None and dest.stat().st_size != expected):
                self.fail('The original save could not be backed up completely. No saves were changed.')
        # tvOS may have purged Caches. Preserve the persistent original as a normal
        # restorable folder too, rather than treating that case as "no save".
        persistent = work / 'persistent' / ('save_device' if slot.endswith('_device') else 'save')
        if not names and persistent.is_dir():
            shutil.copytree(persistent, before, dirs_exist_ok=True)
        after = self.listing(device, bundle)
        relevant = lambda data: {n: f.get('metadata') for n, f in data.items() if n.startswith(prefix)}
        if relevant(listing) != relevant(after):
            self.fail('The save changed during its backup. No saves were changed. Try again.')
        sync_path = f'Library/Caches/{slot.removesuffix("_device")}.sync'
        old_sync = work / 'previous.sync'
        if sync_path.removeprefix('Library/') in listing:
            self.copy('from', device, bundle, sync_path, old_sync)
        previous_files = sum(p.is_file() for p in before.rglob('*'))
        record.update(previous_files=previous_files, backup_ready=True, status='backed-up')
        save_record()
        # The persisted save is the baseline, so the runtime pushes the imported data
        # instead of restoring an older persistent copy over it at the next launch.
        sync = work / 'import.sync'
        sync.write_text('base\t' + remote_hash + '\n')
        attempted = False
        try:
            attempted = True
            self.copy('to', device, bundle, incoming, f'Library/Caches/{slot}', replace=True)
            self.copy('to', device, bundle, sync, sync_path)
            self.verify(device, bundle, slot, incoming, work / 'verify')
        except Exception as error:
            if attempted:
                try:
                    self.copy('to', device, bundle, before, f'Library/Caches/{slot}', replace=True)
                    if not old_sync.exists():
                        old_sync.write_text('base\t\n')
                    self.copy('to', device, bundle, old_sync, sync_path)
                    self.verify(device, bundle, slot, before, work / 'verify-rollback')
                    record['status'] = 'rolled-back'; save_record()
                except Exception:
                    record['status'] = 'needs-restore'; save_record()
                    self.fail(f'Import stopped and automatic recovery failed. Keep the game closed. The original is in Previous Backups and at {before}.')
            self.fail(f'Import failed; the original save was restored. {error}')
        record['status'] = 'imported'; save_record()
        return dict(files=source['files'], backup=str(before) if previous_files else None,
                    message=f'{source["files"]} save files imported into {app["name"]}. Open the game on the Apple TV to use them.')

    def verify(self, device, bundle, slot, expected, into):
        listing = self.listing(device, bundle)
        prefix = f'Caches/{slot}/'
        actual = {n[len(prefix):] for n, f in listing.items() if n.startswith(prefix) and not f.get('resources', {}).get('isDirectory')}
        wanted = {p.relative_to(expected).as_posix() for p in expected.rglob('*') if p.is_file()}
        if actual != wanted:
            self.fail('The transferred file list did not match the source.')
        for name in sorted(wanted):
            out = into / name
            out.parent.mkdir(parents=True, exist_ok=True)
            self.copy('from', device, bundle, 'Library/' + prefix + name, out)
            if hashlib.sha256(out.read_bytes()).digest() != hashlib.sha256((expected / name).read_bytes()).digest():
                self.fail('A transferred save file did not match the source.')

    def restore(self, device, bundle, backup_id):
        if not re.fullmatch(r'[0-9a-f]{32}', backup_id):
            self.fail('Invalid backup.')
        work = next((root / backup_id for root in self.roots if (root / backup_id / 'record.json').is_file()), self.home / backup_id)
        try:
            record = json.loads((work / 'record.json').read_text())
        except (OSError, ValueError):
            self.fail('This backup could not be read.')
        if record.get('device') != device or record.get('bundle') != bundle or not record.get('backup_ready'):
            self.fail('This backup belongs to a different game or Apple TV.')
        return self.transfer(device, bundle, record['slot'], self.backup_folder(work), restore_id=backup_id)

    def export_all(self, device):
        apps = [app for app in self.apps(device) if app['compatible']]
        saved, errors, skipped = [], [], 0
        for app in apps:
            try:
                slots = self.targets(device, app['id'])
            except (self.b.Failure, OSError, ValueError) as error:
                errors.append(f'{app["name"]}: {error}')
                continue
            for slot in slots:
                try:
                    result = self.export(device, app['id'], slot['id'], skip_empty=True)
                    if result is None:
                        skipped += 1
                    else:
                        saved.append(dict(game=app['name'], bundle=app['id'], slot=slot['id'], **result))
                except (self.b.Failure, OSError, ValueError) as error:
                    errors.append(f'{app["name"]} — {slot["name"]}: {error}')
        games = len({item['bundle'] for item in saved})
        files = sum(item['files'] for item in saved)
        message = f'Backed up {len(saved)} save slots from {games} games ({files} files).'
        if not apps:
            message = 'No supported installed games were found.'
        if skipped:
            message += f' Skipped {skipped} empty slots.'
        if errors:
            message += f' {len(errors)} backups could not complete; see the details below.'
        return dict(files=files, backup=str(self.home) if saved else None, message=message,
                    saved=saved, errors=errors, skipped=skipped)

    def export(self, device, bundle, slot, skip_empty=False):
        if not SLOT.fullmatch(slot):
            self.fail('Invalid save slot.')
        app = self.app(device, bundle)
        files = self.listing(device, bundle)
        prefix = f'Caches/{slot}/'
        names = [n for n, f in files.items() if n.startswith(prefix) and not f.get('resources', {}).get('isDirectory')]
        work = self.home / uuid.uuid4().hex
        before = work / 'Save Files'
        before.mkdir(parents=True)
        for name, f in files.items():
            if name.startswith(prefix) and f.get('resources', {}).get('isDirectory'):
                (before / name[len(prefix):]).mkdir(parents=True, exist_ok=True)
        if not names:
            prefs = self.preferences(device, bundle, files, work)
            self.remote_hash(device, bundle, slot, files, prefs, work)
            persistent = work / 'persistent' / ('save_device' if slot.endswith('_device') else 'save')
            if persistent.is_dir():
                shutil.copytree(persistent, before, dirs_exist_ok=True)
            if not any(p.is_file() for p in before.rglob('*')):
                if skip_empty:
                    shutil.rmtree(work)
                    return None
                self.fail('This slot has no save files on the Apple TV yet.')
        for name in names:
            dest = before / name[len(prefix):]
            dest.parent.mkdir(parents=True, exist_ok=True)
            self.copy('from', device, bundle, 'Library/' + name, dest)
            expected = files[name].get('metadata', {}).get('size')
            if not dest.is_file() or (expected is not None and dest.stat().st_size != expected):
                self.fail('The copy was incomplete. Try exporting again.')
        after = self.listing(device, bundle)
        relevant = lambda data: {n: f.get('metadata') for n, f in data.items() if n.startswith(prefix)}
        if relevant(files) != relevant(after):
            self.fail('The game saved during the export. Close the game and try again.')
        count = sum(p.is_file() for p in before.rglob('*'))
        record = dict(device=device, bundle=bundle, game=app['name'], slot=slot, date=time.time(),
                      status='exported', previous_files=count, backup_ready=True)
        (work / 'record.json').write_text(json.dumps(record, indent=2))
        return dict(files=count, backup=str(before), message=f'{count} save files copied to this Mac. Use Show in Finder to open them.')


def stored_save_hash(data, into=None):
    """Validate the runtime's persisted DMZ1/DMZ2 save before using its sync baseline."""
    if not isinstance(data, bytes) or len(data) < 12 or data[:4] not in (b'DMZ1', b'DMZ2'):
        raise ValueError('Invalid stored save')
    size = int.from_bytes(data[4:12], 'little')
    if not 144 <= size <= 512 * 1024**2:
        raise ValueError('Invalid stored save size')
    lib = ctypes.CDLL('/usr/lib/libcompression.dylib')
    decode = lib.compression_decode_buffer
    decode.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_int]
    decode.restype = ctypes.c_size_t
    out = ctypes.create_string_buffer(size)
    packed = data[12:]
    if decode(out, size, packed, len(packed), None, 0x801 if data[:4] == b'DMZ2' else 0x306) != size:
        raise ValueError('Could not decode stored save')
    raw = out.raw
    if raw[:8] != b'DMSYNC1\n' or int.from_bytes(raw[8:12], 'little') != 1:
        raise ValueError('Invalid save header')
    digest = hashlib.sha256(); pos = 144; entries = []
    for _ in range(int.from_bytes(raw[12:16], 'little')):
        header = raw[pos:pos + 24]
        if len(header) != 24:
            raise ValueError('Truncated entry')
        kind, _, plen, glen, _, length, _ = struct.unpack('<BBHHHQq', header)
        pos += 24
        end = pos + plen + glen + length
        if kind not in (1, 2) or end > len(raw) or (kind == 1 and length):
            raise ValueError('Invalid entry')
        path = raw[pos:pos + plen].decode('utf-8')
        if not path.startswith(('save/', 'save_device/')) or any(p in ('', '.', '..') for p in path.split('/')) or '\x00' in path:
            raise ValueError('Invalid stored save path')
        entries.append((path, kind, raw[pos + plen:pos + plen + glen], raw[pos + plen + glen:end]))
        digest.update(header[:16]); digest.update(raw[pos:end]); pos = end
    expected = raw[16:48].decode('ascii')
    if raw[pos:] != b'DMSYNCE\n' or digest.hexdigest()[:32] != expected:
        raise ValueError('Invalid save checksum')
    if into is not None:
        for path, kind, guest, contents in entries:
            target = Path(into) / path
            if kind == 1:
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(contents)
            if guest:
                os.setxattr(target, 'org.d2rmobile.guest-name', guest)
    return expected
