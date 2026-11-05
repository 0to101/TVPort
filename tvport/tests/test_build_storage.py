"""Build locations and non-destructive relocation, using small temporary fixtures."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import backend


class BuildStorage(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.data = self.root / 'app-data'; self.data.mkdir()
        self.source = self.root / 'Game'; self.source.mkdir()
        self.destination = self.root / 'Builds'; self.destination.mkdir()
        self.build = self.source / '0100000000010000_build'; self.build.mkdir()
        (self.build / 'tvport.json').write_text(json.dumps({'bundle_id': 'org.original.game'}))
        (self.build / 'save-backups').mkdir()
        (self.build / 'save-backups/progress').write_bytes(b'backup')
        self.addCleanup(patch.stopall)
        patch.object(backend, 'DATA', self.data).start()
        patch.dict(os.environ, {'TVPORT_DEFAULT_BUILD_FOLDER': ''}).start()

    def settings(self, **settings):
        (self.data / 'library.json').write_text(json.dumps([dict(folder=str(self.source), **settings)]))

    def test_default_keeps_existing_build_beside_source(self):
        game = backend.Game(self.source)
        self.assertEqual(game.build_parent, self.source)
        self.assertEqual(game.build, self.build)

    def test_per_game_override_wins_over_global_default(self):
        os.environ['TVPORT_DEFAULT_BUILD_FOLDER'] = str(self.root / 'global')
        self.settings(buildFolder=str(self.destination))
        game = backend.Game(self.source)
        self.assertEqual(game.storage_root, self.destination)
        self.assertEqual(game.build_parent.parent, self.destination)
        self.assertEqual(game.build, self.build)

    def test_original_files_choice_ignores_default_folder(self):
        os.environ['TVPORT_DEFAULT_BUILD_FOLDER'] = str(self.destination)
        self.settings(buildNextToOriginal=True)
        game = backend.Game(self.source)
        self.assertEqual(game.storage_root, self.source)
        self.assertEqual(game.build_parent, self.source)

    def test_settings_choice_uses_current_default_not_old_custom_folder(self):
        self.settings(buildNextToOriginal=False, buildFolder=str(self.root / 'old-custom'))
        for folder in (self.destination, self.root / 'new-default'):
            os.environ['TVPORT_DEFAULT_BUILD_FOLDER'] = str(folder)
            self.assertEqual(backend.Game(self.source).storage_root, folder)

    def test_settings_choice_falls_back_to_original_when_unset(self):
        self.settings(buildNextToOriginal=False)
        self.assertEqual(backend.Game(self.source).build_parent, self.source)

    def test_global_default_isolates_games_with_the_same_folder_name(self):
        os.environ['TVPORT_DEFAULT_BUILD_FOLDER'] = str(self.destination)
        second = self.root / 'another/Game'; second.mkdir(parents=True)
        self.assertNotEqual(backend.Game(self.source).build_parent, backend.Game(second).build_parent)

    def test_copy_preserves_original_backups_and_installed_app_identity(self):
        self.settings(buildFolder=str(self.destination))
        moved = backend.relocate_build(backend.Game(self.source))
        self.assertEqual(moved.build.parent, moved.build_parent)
        self.assertEqual((moved.build / 'save-backups/progress').read_bytes(), b'backup')
        self.assertEqual((self.build / 'save-backups/progress').read_bytes(), b'backup')
        self.assertEqual(moved.bundle_id('NEWTEAM'), 'org.original.game')
        self.assertEqual(backend.Game(self.source).build, moved.build)

    def test_failed_copy_leaves_original_and_no_partial_final_build(self):
        self.settings(buildFolder=str(self.destination))
        game = backend.Game(self.source)
        with patch.object(backend.shutil, 'copytree', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(backend.Failure, 'original is unchanged'):
                backend.relocate_build(game)
        self.assertEqual((self.build / 'save-backups/progress').read_bytes(), b'backup')
        self.assertEqual(list(game.build_parent.iterdir()), [])

    def test_unavailable_drive_is_not_recreated(self):
        self.settings(buildFolder=str(self.root / 'disconnected-drive'))
        game = backend.Game(self.source)
        with self.assertRaisesRegex(backend.Failure, 'unavailable'):
            backend.relocate_build(game)
        self.assertFalse(game.storage_root.exists())

    def test_previous_custom_build_remains_discoverable_after_default_changes(self):
        self.settings(buildFolder=str(self.destination))
        moved = backend.relocate_build(backend.Game(self.source))
        self.settings(lastBuildPath=str(moved.build))
        another = self.root / 'new-default'; another.mkdir()
        os.environ['TVPORT_DEFAULT_BUILD_FOLDER'] = str(another)
        game = backend.Game(self.source)
        self.assertEqual(game.build, moved.build)
        self.assertEqual(game.storage_root, another)
