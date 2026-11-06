"""Exercise notification delivery/fallback without touching system permissions or saves."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]


@unittest.skipUnless(sys.platform == 'darwin', 'macOS UserNotifications required')
class SaveNotifications(unittest.TestCase):
    def test_success_denial_and_delivery_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checks = root / 'Checks.swift'
            checks.write_text(r'''
import Foundation
import UserNotifications

enum Failure: Error { case unavailable }
final class FakeClient: SaveNotificationClient {
    var allowed = true
    var permissionFails = false
    var deliveryFails = false
    var requests: [UNNotificationRequest] = []
    func authorize() async throws -> Bool {
        if permissionFails { throw Failure.unavailable }
        return allowed
    }
    func add(_ request: UNNotificationRequest) async throws {
        if deliveryFails { throw Failure.unavailable }
        requests.append(request)
    }
}

@main struct Checks {
    @MainActor static func main() async {
        let client = FakeClient()
        let notifier = SaveRestoreNotifications(client: client)
        let completion = SaveRestoreCompletion(game: "Game 1", player: "Player 2", device: "Living Room", files: 3)
        var delivered = await notifier.notify(completion)
        assert(delivered && client.requests.count == 1)
        let request = client.requests[0]
        assert(request.content.title == "Save restored to Apple TV")
        assert(request.content.body.contains("Game 1 · Player 2"))
        assert(request.content.body.contains("3 files transferred and verified on Living Room"))
        assert(request.trigger == nil)
        delivered = await notifier.notify(completion)
        assert(delivered && client.requests[0].identifier != client.requests[1].identifier)
        client.allowed = false
        delivered = await notifier.notify(completion)
        assert(!delivered && client.requests.count == 2)
        client.permissionFails = true
        delivered = await notifier.notify(completion)
        assert(!delivered && client.requests.count == 2)
        client.permissionFails = false; client.allowed = true; client.deliveryFails = true
        delivered = await notifier.notify(completion)
        assert(!delivered && client.requests.count == 2)
        assert(SaveRestoreCompletion(game: "Game", player: "Original", device: "TV", files: 1).body.contains("1 file transferred"))
        print("PASS: verified-save notification content, unique events, permission denial and delivery fallback")
    }
}
''')
            executable = root / 'check'
            subprocess.run(['swiftc', '-parse-as-library',
                            str(REPO / 'tvport/app/Sources/SaveRestoreNotifications.swift'),
                            str(checks), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
