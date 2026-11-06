import Foundation
import UserNotifications

struct SaveRestoreCompletion {
    let game: String
    let player: String
    let device: String
    let files: Int

    var title: String { "Save restored to Apple TV" }
    var body: String {
        "\(game) · \(player)\n\(files) \(files == 1 ? "file" : "files") transferred and verified on \(device)."
    }
}

protocol SaveNotificationClient {
    func authorize() async throws -> Bool
    func add(_ request: UNNotificationRequest) async throws
}

private struct SystemSaveNotificationClient: SaveNotificationClient {
    let center = UNUserNotificationCenter.current()

    func authorize() async throws -> Bool {
        try await center.requestAuthorization(options: [.alert, .sound])
    }

    func add(_ request: UNNotificationRequest) async throws {
        try await center.add(request)
    }
}

/// Notification failures must never turn a verified restore into a reported failure.
@MainActor
final class SaveRestoreNotifications: NSObject, UNUserNotificationCenterDelegate {
    static let shared = SaveRestoreNotifications(client: SystemSaveNotificationClient())
    private let client: any SaveNotificationClient

    init(client: any SaveNotificationClient) {
        self.client = client
        super.init()
        if let system = client as? SystemSaveNotificationClient { system.center.delegate = self }
    }

    /// False asks the caller to show an in-app confirmation instead.
    func notify(_ completion: SaveRestoreCompletion) async -> Bool {
        do {
            guard try await client.authorize() else { return false }
            let content = UNMutableNotificationContent()
            content.title = completion.title
            content.body = completion.body
            content.sound = .default
            try await client.add(UNNotificationRequest(identifier: "save-restored-\(UUID().uuidString)",
                                                       content: content, trigger: nil))
            return true
        } catch { return false }
    }

    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter,
                                            willPresent notification: UNNotification,
                                            withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .list, .sound])
    }
}
