import SwiftUI
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
                if targeted && !library.isBusy {
                    RoundedRectangle(cornerRadius: 10)
                        .strokeBorder(Color.accentColor, style: StrokeStyle(lineWidth: 2, dash: [6]))
                        .allowsHitTesting(false)
                        .accessibilityHidden(true)
                }
            }
            .dropDestination(for: URL.self) { urls, _ in
                guard !library.isBusy, urls.contains(where: \.isFileURL) else { return false }
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
                HStack {
                    Text("Updates & DLC").font(.headline)
                    Spacer()
                    Button("Add Files…") { choosingFiles = true }.disabled(library.isBusy)
                }
                if library.checkingAddonGame == game.id {
                    HStack { ProgressView().controlSize(.small); Text("Checking game compatibility…") }
                } else {
                    Text("Drag and drop updates or DLC here").foregroundStyle(.secondary)
                }
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
                            .buttonStyle(.borderless).disabled(library.isBusy)
                            .help("Remove this attachment; the original file is kept")
                            .accessibilityLabel("Remove \(addon.name)")
                    }
                }
                if !(game.addons ?? []).isEmpty {
                    Text("Files stay in their original folders. Build & Install applies your changes.")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 10))
            .fileImporter(isPresented: $choosingFiles, allowedContentTypes: [.item], allowsMultipleSelection: true) { result in
                if case .success(let urls) = result { library.attachAddons(urls, to: game.id) }
            }
        }
    }
}
