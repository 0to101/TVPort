"""Exercise the real AppKit log's scrolling without opening a window."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]

@unittest.skipUnless(sys.platform == 'darwin', 'AppKit required')
class LogFollowTests(unittest.TestCase):
    def test_new_text_always_follows_end_and_keeps_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checks = root / 'Checks.swift'
            checks.write_text(r'''
import AppKit
@main struct Checks {
    @MainActor static func main() {
        _ = NSApplication.shared
        let view = LogTextScrollView()
        let lines = (0..<500).map { "Line \($0) — test output" }.joined(separator: "\n")
        view.setLog(lines) // Text arrives before SwiftUI gives the view a frame.
        view.frame = NSRect(x: 0, y: 0, width: 600, height: 200)
        func checkBottom() {
            view.layoutSubtreeIfNeeded()
            view.layoutSubtreeIfNeeded()
            assert(view.contentView.bounds.origin.y > 0)
            assert(view.contentView.bounds.maxY >= view.logTextView.bounds.maxY - 4,
                   "Latest log line is outside the visible area")
        }
        checkBottom()
        view.contentView.scroll(to: .zero)
        let selection = NSRange(location: 10, length: 40)
        view.logTextView.setSelectedRange(selection)
        view.setLog(lines + "\nNewest line")
        checkBottom()
        assert(view.logTextView.selectedRange() == selection)
        // The rolling log replaces its text when older lines are removed.
        view.setLog(String(lines.dropFirst(100)) + "\nNewest replacement")
        checkBottom()
        view.logTextView.selectAll(nil)
        assert(view.logTextView.selectedRange().length == (view.logTextView.string as NSString).length)
        print("PASS: initial layout, appends after scrolling up, rolling log replacement and selection")
    }
}
''')
            executable = root / 'check'
            subprocess.run(['swiftc', '-parse-as-library', str(REPO / 'tvport/app/Sources/SelectableLogView.swift'), str(checks), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True, timeout=20)
