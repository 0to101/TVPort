import Foundation

/// Requests retain the chosen device, signing team and build options when queued.
struct QueuedBuild: Equatable {
    let gameID: String
    let name: String
    let arguments: [String]
    let install: Bool
}

/// The active request remains reserved until its process has finished.
struct BuildQueue {
    private(set) var active: QueuedBuild?
    private(set) var pending: [QueuedBuild] = []
    private(set) var paused = false

    mutating func enqueue(_ request: QueuedBuild) {
        guard active?.gameID != request.gameID,
              !pending.contains(where: { $0.gameID == request.gameID }) else { return }
        pending.append(request)
    }

    mutating func next() -> QueuedBuild? {
        guard active == nil, !paused, !pending.isEmpty else { return nil }
        active = pending.removeFirst()
        return active
    }

    mutating func finish(succeeded: Bool) {
        active = nil
        if !succeeded { paused = true }
    }

    mutating func pause() { paused = true }
    mutating func resume() { paused = false }
    mutating func remove(_ gameID: String) { pending.removeAll { $0.gameID == gameID } }
    func position(_ gameID: String) -> Int? {
        pending.firstIndex(where: { $0.gameID == gameID }).map { $0 + 1 }
    }
}
