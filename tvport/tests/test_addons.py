"""External package metadata and build wiring, without game files or keys."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, PropertyMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import backend
sys.path.insert(0, str(backend.REPO / 'scripts'))
import inspect_game_addons as addons

APP = 0x010020D01AD24000
BASE = [[('Application', APP, 0)]]


class AddonMetadata(unittest.TestCase):
    def test_uses_metadata_not_filename(self):
        result = addons.validate_records(BASE, [(Path('misleading [v0].nsp'), [('Patch', APP + 0x800, 65536), ('AddOnContent', APP + 0x1001, 2)])])
        self.assertEqual([a['kind'] for a in result['addons']], ['Update', 'DLC'])
        self.assertEqual(result['addons'][0]['version'], 65536)

    def test_rejects_wrong_game_base_and_unreadable_packages(self):
        for content in [[('Patch', APP + 0x2800, 0)], [('AddOnContent', APP + 0x3001, 0)], [('Application', APP, 0)], []]:
            with self.subTest(content=content), self.assertRaises(ValueError):
                addons.validate_records(BASE, [(Path('DLC.nsp'), content)])
        with self.assertRaises(ValueError):
            addons.validate_records(BASE, [], '0100000000000000')

    def test_external_folder_filters_appledouble_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            real = root / 'DLC.NSP'; real.touch()
            (root / '._DLC.NSP').touch()
            (root / 'notes.txt').touch()
            self.assertEqual(addons.source_files([root, real]), [real])
            with self.assertRaises(ValueError):
                addons.source_files([root / 'missing'])


class BuildAttachments(unittest.TestCase):
    def test_changed_inputs_get_separate_profiles_and_can_switch_back(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / 'base'; source.mkdir()
            data = root / 'settings'; data.mkdir()
            build = source / f'{APP:016X}_build'; build.mkdir()
            (source / 'base.nsp').write_bytes(b'base')
            keys = root / 'test.keys'; keys.touch()
            legacy = build / 'profile' / f'{APP:016X}'
            legacy.mkdir(parents=True)
            (legacy / 'game.tsv').write_text('name\tBase game\n')
            with patch.object(backend, 'DATA', data), patch.dict(backend.os.environ, {'TVPORT_DEFAULT_BUILD_FOLDER': ''}), patch.object(backend.Game, 'prepared', new_callable=PropertyMock, return_value=True), patch.object(backend, 'emit'):
                game = backend.Game(source)
                base_signature = game.input_signature()
                game.save_state(source_signature=base_signature)
                update = root / 'update.nsp'; update.write_bytes(b'update')
                (data / 'library.json').write_text(json.dumps([{'folder': str(source), 'addons': [{'path': str(update)}]}]))
                game = backend.Game(source)
                update_signature = game.input_signature()
                expected = build / 'profiles' / update_signature

                def prepare(command, **kwargs):
                    chosen = Path(command[command.index('--profile-out') + 1])
                    self.assertEqual(chosen, expected)
                    target = chosen / game.title_id
                    target.mkdir(parents=True, exist_ok=True)
                    (target / 'game.tsv').write_text('name\tUpdated game\n')

                with patch.object(backend, 'stream', side_effect=prepare):
                    updated = backend.prepare_game(game, keys, '', sys.executable)
                self.assertEqual(updated.profile_root, expected)
                self.assertEqual(updated.profile_value('name'), 'Updated game')
                self.assertEqual(backend.profile_env(updated)['DM_GAMES_DIR'], str(expected))
                self.assertEqual((legacy / 'game.tsv').read_text(), 'name\tBase game\n')

                # A failed preparation must not change the last successful profile.
                state = updated.state()
                update.write_bytes(b'different update')
                with patch.object(backend, 'stream', side_effect=backend.Failure('test failure')):
                    with self.assertRaises(backend.Failure):
                        backend.prepare_game(backend.Game(source), keys, '', sys.executable)
                self.assertEqual(backend.Game(source).state(), state)

                # Removing the update selects the preserved original survey again.
                (data / 'library.json').write_text('[]')
                with patch.object(backend, 'stream') as stream:
                    original = backend.prepare_game(backend.Game(source), keys, '', sys.executable)
                command = stream.call_args.args[0]
                self.assertEqual(Path(command[command.index('--profile-out') + 1]), build / 'profile')
                self.assertEqual(original.profile_value('name'), 'Base game')
                self.assertEqual(original.state()['source_signature'], base_signature)

    def test_signature_removal_manifest_and_packaging(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / 'base'; source.mkdir()
            data = root / 'settings'; data.mkdir()
            build = source / f'{APP:016X}_build'; build.mkdir()
            (source / 'base.nsp').write_bytes(b'base')
            dlc = root / 'external.nsp'; dlc.write_bytes(b'dlc')
            with patch.object(backend, 'DATA', data), patch.dict(backend.os.environ, {'TVPORT_DEFAULT_BUILD_FOLDER': ''}):
                game = backend.Game(source)
                original = game.input_signature()
                (data / 'library.json').write_text(json.dumps([{'folder': str(source), 'addons': [{'path': str(dlc)}]}]))
                game = backend.Game(source)
                self.assertNotEqual(original, game.input_signature())
                dlc.unlink()
                with self.assertRaises(backend.Failure): game.input_signature()
                game.addons = []
                self.assertEqual(original, game.input_signature())
                for version in ('v0', 'v65536'): (build / f'patched_{version}').mkdir()
                manifest = build / 'prepared-content.json'
                manifest.write_text(json.dumps({'package': 'v0', 'dlc': False}))
                self.assertEqual(game.package, 'v0')  # Removed update must not be reused.
                (build / 'aoc').mkdir()  # Old DLC remains cached after detaching.
                args = argparse.Namespace(fps=False, mode='handheld', texture_cap=512, players='', render_scale=1, no_thermal_cap=False, fps_target=0, swap_ab_xy=False, swap_ab=None, swap_xy=None, art=None, art_scale=0, art_x=0, art_y=0, shelf_art=root / 'cover.png', shelf_scale=2, shelf_x=-1, shelf_y=1)
                with patch.object(backend, 'restore_tables'), patch.object(backend, 'write_env', return_value=root / 'env'), patch.object(backend, 'stream') as stream:
                    for active in (False, True):
                        manifest.write_text(json.dumps({'package': 'v0', 'dlc': active}))
                        backend.generate_project(game, args, 'TEST', 'test.game', sys.executable)
                        env = stream.call_args.kwargs['env']
                        self.assertEqual(env['AOC'], str(build / 'aoc') if active else '')
                        self.assertEqual(env['DM_TOP_SHELF_ART'], str(args.shelf_art))
                        self.assertEqual(env['DM_SHELF_CROP_SCALE'], '2')
