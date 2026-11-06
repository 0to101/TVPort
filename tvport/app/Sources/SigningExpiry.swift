import Foundation

/// Read the profile's actual expiration, rather than assuming seven days from install.
struct SigningExpiry {
    let date: Date

    init?(_ timestamp: String?) {
        guard let timestamp else { return nil }
        let parser = ISO8601DateFormatter()
        parser.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = parser.date(from: timestamp) { self.date = date; return }
        parser.formatOptions = [.withInternetDateTime]
        guard let date = parser.date(from: timestamp) else { return nil }
        self.date = date
    }

    func label(at now: Date, timeZone: TimeZone = .autoupdatingCurrent) -> String {
        let remaining = date.timeIntervalSince(now)
        let relative: String
        if remaining <= 0 { relative = "Expired" }
        else if remaining >= 86_400 {
            let days = Int(remaining / 86_400)
            relative = "Expires in \(days) day\(days == 1 ? "" : "s")"
        } else if remaining >= 3_600 {
            let hours = Int(remaining / 3_600)
            relative = "Expires in \(hours) hour\(hours == 1 ? "" : "s")"
        } else if remaining >= 60 {
            let minutes = Int(remaining / 60)
            relative = "Expires in \(minutes) minute\(minutes == 1 ? "" : "s")"
        } else { relative = "Expires in less than a minute" }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = timeZone
        formatter.dateFormat = "EEEE d, HH:mm"
        return "\(relative), \(formatter.string(from: date))"
    }
}
