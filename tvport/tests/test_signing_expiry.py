"""Check actual-profile expiry formatting independently of the clock and locale."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]

@unittest.skipUnless(sys.platform == 'darwin', 'macOS Swift required')
class SigningExpiryTests(unittest.TestCase):
    def test_countdown_expiry_and_local_date(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            checks = root / 'Checks.swift'
            checks.write_text(r'''
import Foundation
@main struct Checks {
    static func main() {
        let expiry = SigningExpiry("2027-01-22T21:55:00+00:00")!
        let zone = TimeZone(secondsFromGMT: 3600)!
        func label(_ seconds: Double) -> String {
            expiry.label(at: expiry.date.addingTimeInterval(-seconds), timeZone: zone)
        }
        assert(label(3 * 86400 + 300) == "Expires in 3 days, Friday 22, 22:55")
        assert(label(86400) == "Expires in 1 day, Friday 22, 22:55")
        assert(label(23 * 3600) == "Expires in 23 hours, Friday 22, 22:55")
        assert(label(3600) == "Expires in 1 hour, Friday 22, 22:55")
        assert(label(120) == "Expires in 2 minutes, Friday 22, 22:55")
        assert(label(60) == "Expires in 1 minute, Friday 22, 22:55")
        assert(label(1) == "Expires in less than a minute, Friday 22, 22:55")
        assert(label(0) == "Expired, Friday 22, 22:55")
        assert(label(-1) == label(0))
        assert(SigningExpiry(nil) == nil && SigningExpiry("bad-date") == nil)
        assert(SigningExpiry("2027-01-22T21:55:00.000Z")!.date == expiry.date)
        assert(SigningExpiry("2027-01-22T22:55:00+01:00")!.date == expiry.date)
        let lateZone = TimeZone(secondsFromGMT: 10800)!
        assert(expiry.label(at: expiry.date, timeZone: lateZone) == "Expired, Saturday 23, 00:55")
        assert(label(100 * 86400).hasPrefix("Expires in 100 days"))
        print("PASS: countdown boundaries, expired/missing dates, actual validity, local time and date rollover")
    }
}
''')
            executable = root / 'check'
            subprocess.run(['swiftc', '-parse-as-library', str(REPO / 'tvport/app/Sources/SigningExpiry.swift'), str(checks), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
