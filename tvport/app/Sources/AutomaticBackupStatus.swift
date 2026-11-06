import SwiftUI

/// Shared status so a background backup never looks like an unresponsive app.
struct AutomaticBackupStatus: View {
    @EnvironmentObject var library: Library

    var body: some View {
        if library.automaticallyBackingUp {
            HStack(alignment: .top, spacing: 10) {
                ProgressView().controlSize(.small)
                VStack(alignment: .leading, spacing: 3) {
                    Text("Backing up saves from Apple TV…").fontWeight(.medium)
                    Text(library.buildQueue.pending.isEmpty
                         ? "You can browse saved copies or add a build to the queue. Save transfers wait until backup finishes."
                         : "\(library.buildQueue.pending.count) in queue. Builds start after backup finishes; saved copies are available to browse.")
                        .foregroundStyle(.secondary)
                }
                Spacer(minLength: 0)
            }
            .padding(10).background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 8))
        } else if let notice = library.automaticBackupNotice {
            Label(notice, systemImage: "exclamationmark.triangle")
                .foregroundStyle(.secondary)
        }
    }
}
