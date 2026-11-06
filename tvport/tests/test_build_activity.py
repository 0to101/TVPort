"""Exercise sleep protection through real process success, failure and cancellation."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]

@unittest.skipUnless(sys.platform == 'darwin', 'macOS Swift required')
class BuildActivityTests(unittest.TestCase):
    def test_process_lifetime(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            checks = root / 'Checks.swift'
            checks.write_text(r'''
import Foundation
@main struct Checks {
    static func main() throws {
        assert(BuildActivity.options.contains(.idleSystemSleepDisabled))
        assert(!BuildActivity.options.contains(.idleDisplaySleepDisabled))
        func exercise(_ arguments: [String], cancel: Bool = false, missing: Bool = false) throws {
            let ended = DispatchSemaphore(value: 0)
            let activity = BuildActivity(begin: { NSObject() }, end: { _ in ended.signal() })
            let process = Process()
            process.executableURL = URL(fileURLWithPath: missing ? "/missing-tvport-test" : "/bin/sh")
            process.arguments = arguments
            do {
                try BuildActivity.run(process, activity: activity)
                assert(!missing)
                if cancel {
                    assert(ended.wait(timeout: .now() + 0.1) == .timedOut)
                    process.terminate()
                }
                process.waitUntilExit()
            } catch { assert(missing) }
            assert(ended.wait(timeout: .now() + 5) == .success)
            activity.end()
            assert(ended.wait(timeout: .now() + 0.05) == .timedOut, "Activity must end exactly once")
        }
        try exercise(["-c", "exit 0"])
        try exercise(["-c", "exit 1"])
        try exercise(["-c", "exec sleep 30"], cancel: true)
        try exercise([], missing: true)
        // Successive queue jobs each acquire and release their own activity.
        try exercise(["-c", "exit 0"])
        try exercise(["-c", "exit 0"])
        print("PASS: success, failure, cancellation, launch failure, queued jobs, and display sleep allowed")
    }
}
''')
            executable = root / 'check'
            subprocess.run(['swiftc', '-parse-as-library', str(REPO / 'tvport/app/Sources/BuildActivity.swift'), str(checks), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True, timeout=20)
