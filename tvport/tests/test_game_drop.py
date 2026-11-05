"""Run the Swift drop resolver against real temporary files and directories."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]


@unittest.skipUnless(sys.platform == 'darwin', 'macOS Foundation required')
class GameDrop(unittest.TestCase):
    def test_game_files_folders_and_rejected_items(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checks = root / 'main.swift'
            checks.write_text(r'''
import Foundation
let root = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
let folder = root.appendingPathComponent("External Drive/Games with spaces/Spel åäö #1", isDirectory: true)
try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
let files = ["Game.NSP", "Game.xci", "Update.nsz", "DLC.xcz"].map { folder.appendingPathComponent($0) }
for file in files { try Data("fixture".utf8).write(to: file) }
for file in files {
    assert(GameDropImport.folders(from: [file]) == [folder.standardizedFileURL])
}
assert(GameDropImport.folders(from: [folder] + files) == [folder.standardizedFileURL])
let second = root.appendingPathComponent("Other Game", isDirectory: true)
try FileManager.default.createDirectory(at: second, withIntermediateDirectories: true)
assert(GameDropImport.folders(from: [files[0], second]) == [folder.standardizedFileURL, second.standardizedFileURL])
let image = folder.appendingPathComponent("Cover.png")
try Data().write(to: image)
let package = root.appendingPathComponent("Unrelated.app", isDirectory: true)
try FileManager.default.createDirectory(at: package, withIntermediateDirectories: true)
assert(GameDropImport.folders(from: [image, package, folder.appendingPathComponent("Missing.nsp"),
    URL(string: "https://example.com/game.nsp")!]).isEmpty)
for file in files {
    let data = try Data(contentsOf: file)
    assert(data == Data("fixture".utf8))
}
print("PASS: game files, folders, duplicate folders, multiple folders, spaces, Unicode and invalid items")
''')
            executable = root / 'check'
            subprocess.run(['swiftc', str(REPO / 'tvport/app/Sources/GameDropImport.swift'),
                            str(checks), '-o', str(executable)], check=True)
            subprocess.run([str(executable), str(root)], check=True)


if __name__ == '__main__':
    unittest.main()
