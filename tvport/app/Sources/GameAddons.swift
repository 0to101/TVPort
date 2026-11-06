import SwiftUI
import AppKit
import UniformTypeIdentifiers

struct GameAddon: Codable, Hashable, Identifiable {
    let path: String
    let kind: String
    let title_id: String
    let version: Int
    var id: String { title_id }
    var name: String { URL(fileURLWithPath: path).lastPathComponent }
}

struct GameAddonCheck: Decodable {
    let title_id: String
    let addons: [GameAddon]
}

struct GameAddonDropTarget: ViewModifier {
    @EnvironmentObject var library: Library
    let gameID: Game.ID
    @State private var targeted = false

    func body(content: Content) -> some View {
        content
            .contentShape(Rectangle())
            .overlay {
                if targeted && library.canEditAddons {
                    RoundedRectangle(cornerRadius: 10)
                        .strokeBorder(Color.accentColor, style: StrokeStyle(lineWidth: 2, dash: [6]))
                        .allowsHitTesting(false)
                        .accessibilityHidden(true)
                }
            }
            .dropDestination(for: URL.self) { urls, _ in
                guard library.canEditAddons, urls.contains(where: \.isFileURL) else { return false }
                library.attachAddons(urls, to: gameID)
                return true
            } isTargeted: { targeted = $0 }
    }
}

struct GameAddonsCard: View {
    @EnvironmentObject var library: Library
    @State private var choosingFiles = false

    var body: some View {
        if let game = library.current {
            VStack(alignment: .leading, spacing: 10) {
                Button("Add Files…") { chooseFiles(for: game.id) }
                    .disabled(!library.canEditAddons || choosingFiles)
                if library.checkingAddonGame == game.id {
                    HStack { ProgressView().controlSize(.small); Text("Checking game compatibility…") }
                } else {
                    Text("Drag and drop updates or DLC here").foregroundStyle(.secondary)
                }
                Label("Updates & DLC support is under development and may cause games to crash.", systemImage: "exclamationmark.triangle")
                    .foregroundStyle(.orange)
                    .fixedSize(horizontal: false, vertical: true)
                ForEach(game.addons ?? []) { addon in
                    HStack(alignment: .top) {
                        Image(systemName: addon.kind == "Update" ? "arrow.down.circle" : "puzzlepiece.extension")
                        VStack(alignment: .leading, spacing: 3) {
                            Text(addon.name).lineLimit(2)
                            Text("\(addon.kind) · Revision \(addon.version)").font(.caption).foregroundStyle(.secondary)
                            Text(addon.path).font(.caption).foregroundStyle(.secondary).lineLimit(1).truncationMode(.middle).help(addon.path)
                            if !FileManager.default.fileExists(atPath: addon.path) {
                                Label("File unavailable — reconnect its drive", systemImage: "exclamationmark.triangle").foregroundStyle(.orange)
                            }
                        }
                        Spacer()
                        Button { library.removeAddon(addon, from: game.id) } label: { Image(systemName: "minus.circle") }
                            .buttonStyle(.borderless).disabled(!library.canEditAddons)
                            .help("Remove this attachment; the original file is kept")
                            .accessibilityLabel("Remove \(addon.name)")
                    }
                }
                if !(game.addons ?? []).isEmpty {
                    Text("Files stay in their original folders. Build & Install applies your changes.")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private func chooseFiles(for gameID: Game.ID) {
        guard library.canEditAddons, !choosingFiles else { return }
        // Present directly: this card sits inside SettingsForm's keys importer.
        // Keep the destination captured even if the selected game changes.
        let panel = NSOpenPanel()
        panel.title = "Add Updates & DLC"
        panel.message = "Choose NSP, XCI, NSZ or XCZ files, or a folder containing updates and DLC."
        panel.prompt = "Add Files"
        panel.canChooseFiles = true
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = true
        panel.allowedContentTypes = ["nsp", "xci", "nsz", "xcz"].compactMap { UTType(filenameExtension: $0) }
        choosingFiles = true
        let completion: (NSApplication.ModalResponse) -> Void = { response in
            choosingFiles = false
            guard response == .OK else { return }
            library.attachAddons(panel.urls, to: gameID)
        }
        if let window = NSApp.keyWindow {
            panel.beginSheetModal(for: window, completionHandler: completion)
        } else {
            panel.begin(completionHandler: completion)
        }
    }
}
