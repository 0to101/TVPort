import Foundation

/// Prevent idle system sleep for the backend's lifetime, including cancellation cleanup.
/// Display sleep remains allowed; an idle app or paused queue holds no activity.
final class BuildActivity: @unchecked Sendable {
    static let options: ProcessInfo.ActivityOptions = [.userInitiatedAllowingIdleSystemSleep, .idleSystemSleepDisabled]
    private let lock = NSLock()
    private var token: NSObjectProtocol?
    private let endActivity: (NSObjectProtocol) -> Void

    init(begin: () -> NSObjectProtocol = {
        ProcessInfo.processInfo.beginActivity(options: BuildActivity.options,
                                             reason: "TVPort is preparing, building or installing games")
    }, end: @escaping (NSObjectProtocol) -> Void = { ProcessInfo.processInfo.endActivity($0) }) {
        token = begin()
        endActivity = end
    }

    func end() {
        lock.lock()
        let finished = token
        token = nil
        lock.unlock()
        if let finished { endActivity(finished) }
    }

    deinit { end() }

    static func run(_ process: Process, activity: BuildActivity = BuildActivity()) throws {
        process.terminationHandler = { _ in activity.end() }
        do { try process.run() }
        catch {
            activity.end()
            process.terminationHandler = nil
            throw error
        }
    }
}
