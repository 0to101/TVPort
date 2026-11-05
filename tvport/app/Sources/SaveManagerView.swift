import SwiftUI
import UniformTypeIdentifiers

struct InstalledSaveGame: Decodable, Identifiable, Hashable {
    let id: String
    let name: String
    let version: String
    let title_id: String
    let compatible: Bool
    let reason: String
}

struct SaveSlot: Decodable, Identifiable {
    let id: String
    let name: String
    let files: Int
}

struct ImportedSaveBackup: Decodable, Identifiable {
    let id: String
    let date: Double
    let game: String
    let slot: String
    let files: Int
    let status: String
    let folder: String
}

private struct SaveSource: Decodable {
    let folder: String
    let files: Int
    let bytes: Int64
}

private struct SaveTransferResult: Decodable {
    let files: Int
    let backup: String?
    let message: String
    let errors: [String]?
    let icloud_available: Bool?
}

@MainActor
struct SaveManagerView: View {
    @EnvironmentObject var library: Library
    @State private var device = ""
    @State private var gameID = ""
    @State private var slot = "save"
    @State private var apps: [InstalledSaveGame] = []
    @State private var savedDevices: [AppleTV] = []
    @State private var online = false
    @State private var availableApps: Set<String> = []
    @State private var connectionNotice: String?
    @State private var slots: [SaveSlot] = []
    @State private var backups: [ImportedSaveBackup] = []
    @State private var source: SaveSource?
    @State private var choosingSource = false
    @State private var showAllApps = false
    @State private var loadingApps = false
    @State private var loadingSlots = false
    @State private var loadingSource = false
    @State private var error: String?
    @State private var message: String?
    @State private var resultFolder: String?
    @State private var confirmingImport = false
    @State private var restoring: ImportedSaveBackup?
    @State private var confirmingRestore = false

    private var game: InstalledSaveGame? { apps.first { $0.id == gameID } }
    private var busy: Bool { library.transferringSaves }
    private var devices: [AppleTV] {
        library.devices + savedDevices.filter { saved in !library.devices.contains { $0.id == saved.id } }
    }
    private var canTransfer: Bool {
        online && availableApps.contains(gameID) && game?.compatible == true && !device.isEmpty && slots.contains { $0.id == slot }
            && !loadingApps && !loadingSlots && !loadingSource && !library.isBusy
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Manage Saves").font(.title2.weight(.semibold))
            Text("Manage game saves and browse backups offline.")
                .foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            HStack {
                Picker("Apple TV", selection: $device) {
                    Text("Choose Apple TV").tag("")
                    ForEach(devices) { Text($0.title).tag($0.id) }
                }
                Button("Refresh") { Task { await loadApps() } }.disabled(device.isEmpty || loadingApps || busy)
                Button("Back Up All Saves") { Task { await backUpAll() } }
                    .disabled(!online || device.isEmpty || loadingApps || loadingSlots || library.isBusy || availableApps.isEmpty)
            }.disabled(busy)
            Toggle("Keep backups in iCloud Drive", isOn: $library.icloudBackups)
                .disabled(library.isBusy)
                .help("Keep new automatic and manual backups, including originals saved before import or restore, in iCloud Drive → TVPort Saves.")
            if library.icloudBackups && !library.icloudAvailable {
                Label("iCloud Drive is unavailable on this Mac. Backups are kept locally until it is available.", systemImage: "icloud.slash")
                    .font(.caption).foregroundStyle(.orange).fixedSize(horizontal: false, vertical: true)
            }
            operationStatus
            if let connectionNotice {
                Label(connectionNotice, systemImage: "wifi.slash").foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            HStack(alignment: .top, spacing: 0) {
                VStack(alignment: .leading, spacing: 10) {
                    HStack {
                        Text(online ? "Games" : "Saved Games").font(.title3.weight(.semibold))
                        if loadingApps { ProgressView().controlSize(.small) }
                    }
                    List(selection: $gameID) {
                        ForEach(apps.filter { showAllApps || $0.compatible }) { app in
                            HStack(spacing: 8) {
                                GameArtworkThumbnail(titleID: app.title_id, name: app.name,
                                                     artworkPath: library.games.first { !$0.titleID.isEmpty && $0.titleID.caseInsensitiveCompare(app.title_id) == .orderedSame }?.artwork,
                                                     width: 48, height: 32)
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(app.name).lineLimit(2)
                                    if !app.compatible { Text("Unavailable").font(.caption).foregroundStyle(.secondary) }
                                }
                            }.tag(app.id)
                                .padding(.leading, -8)
                                .listRowInsets(EdgeInsets(top: 5, leading: 0, bottom: 5, trailing: 0))
                                .listRowSeparator(.hidden)
                        }
                    }
                    .listStyle(.plain)
                    .contentMargins(.horizontal, 0, for: .scrollContent)
                    .disabled(busy)
                    Toggle("Show other apps", isOn: $showAllApps).font(.caption).disabled(busy)
                }
                .frame(minWidth: 190, idealWidth: 220, maxWidth: 280)
                Divider()
                ScrollView {
                    gameDetails.padding(.leading, 12)
                }.frame(minWidth: 580)
            }
            .frame(minHeight: 550)
        }
        .padding(20).frame(minWidth: 860, minHeight: 720)
        .interactiveDismissDisabled(busy)
        .task {
            library.icloudAvailable = FileManager.default.fileExists(atPath: NSHomeDirectory() + "/Library/Mobile Documents/com~apple~CloudDocs")
            if library.devices.isEmpty { await library.refreshDevices() }
            if device.isEmpty { device = library.device ?? devices.first?.id ?? "" }
        }
        .task(id: device) { await loadApps() }
        .task(id: device + "|" + gameID + "|" + String(online)) { await loadSlots() }
        .fileImporter(isPresented: $choosingSource, allowedContentTypes: [.folder]) { result in
            guard case .success(let url) = result else { return }
            let requestedGame = gameID, requestedDevice = device, requestedSlot = slot
            Task {
                loadingSource = true; error = nil; source = nil
                defer { loadingSource = false }
                do {
                    let selected = try await Backend.ask(SaveSource.self, ["save-source", url.path])
                    guard gameID == requestedGame, device == requestedDevice, slot == requestedSlot else { return }
                    source = selected
                    confirmingImport = true
                }
                catch { self.error = error.localizedDescription }
            }
        }
        .alert("Import into \(game?.name ?? "game")?", isPresented: $confirmingImport) {
            Button("Cancel", role: .cancel) {}
            Button("Back Up & Import") { Task { await transfer(command: "import-save") } }
        } message: {
            Text("Import \(source?.files ?? 0) files from ‘\(source.map { URL(fileURLWithPath: $0.folder).lastPathComponent } ?? "")’ into \(slots.first { $0.id == slot }?.name ?? slot)? The game will close and its current save will be backed up first. You can restore it from Previous Backups.")
        }
        .alert("Restore this backup?", isPresented: $confirmingRestore) {
            Button("Cancel", role: .cancel) {}
            Button("Back Up & Restore") { Task { await transfer(command: "restore-save", backup: restoring) } }
        } message: {
            Text("This restores \(restoring?.slot ?? "the save") in \(game?.name ?? "the selected game"). The current save is backed up first, so you can undo the restore.")
        }
    }

    private var gameDetails: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(game.map { $0.name + ($0.version.isEmpty ? "" : " · \($0.version)") } ?? "Choose a game")
                .font(.title3.weight(.semibold))
            if let game, !game.compatible {
                Text(game.reason)
                    .font(.caption).foregroundStyle(.secondary)
            } else if !loadingApps && apps.isEmpty {
                Text("No saved backups found. Connect the Apple TV and press Refresh to back up a game.").foregroundStyle(.secondary)
            }
            if game?.compatible == true {
                if online && availableApps.contains(gameID) { HStack {
                    Picker("Save slot", selection: $slot) {
                        ForEach(slots) { Text("\($0.name) (\($0.files) files)").tag($0.id) }
                    }
                    if loadingSlots { ProgressView().controlSize(.small) }
                }.disabled(busy || loadingSlots) }
                Divider()
                HStack {
                    Button("Import Saves to Apple TV…") { source = nil; choosingSource = true }
                        .buttonStyle(.borderedProminent).disabled(!canTransfer)
                        .help("Import this game’s save folder from Ryujinx, another compatible emulator, or a Mac game. Choose the folder containing the save files, not the whole emulator folder.")
                    Button("Back Up to Mac") { Task { await transfer(command: "export-save") } }
                        .disabled(!canTransfer)
                        .help("Copy the selected save slot to your Mac. Open the backup in Finder to use it with a compatible emulator or Mac game.")
                    if loadingSource { ProgressView().controlSize(.small) }
                }
                Text("Import and restore back up the current save first.")
                    .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            }
            Divider()
            Text("Previous Backups").font(.headline)
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 12) {
                    if backups.isEmpty { Text("No backups for this game yet.").foregroundStyle(.secondary) }
                    ForEach(backups) { backup in
                        HStack {
                            VStack(alignment: .leading, spacing: 3) {
                                Text(Date(timeIntervalSince1970: backup.date).formatted(date: .abbreviated, time: .standard))
                                Text("\(slots.first { $0.id == backup.slot }?.name ?? backup.slot) · \(backup.files) files" + (backup.status == "exported" ? " · Exported copy" : " · Original save"))
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                            Spacer()
                            Button("Show in Finder") { reveal(backup.folder) }
                            Button("Restore…") { restoring = backup; confirmingRestore = true }
                                .disabled(!canTransfer)
                        }
                    }
                }.frame(maxWidth: .infinity, alignment: .leading)
            }.frame(minHeight: 100, maxHeight: 170)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    @ViewBuilder
    private var operationStatus: some View {
        if busy {
            HStack { ProgressView().controlSize(.small); Text("Copying and verifying saves…") }
        }
        if let message {
            HStack {
                Text(message).fixedSize(horizontal: false, vertical: true)
                if let resultFolder { Button("Show in Finder") { reveal(resultFolder) } }
            }
        }
        if let error {
            ScrollView {
                Text(error).foregroundStyle(.red).textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }.frame(maxHeight: 90)
        }
    }

    private func backUpAll() async {
        guard online, !device.isEmpty, !library.isBusy else { return }
        library.transferringSaves = true; error = nil; message = nil; resultFolder = nil
        defer { library.transferringSaves = false }
        do {
            let result = try await Backend.ask(SaveTransferResult.self, ["export-all-saves", "--device", device] + (library.icloudBackups ? ["--icloud"] : []))
            if let available = result.icloud_available { library.icloudAvailable = available }
            message = result.message; resultFolder = result.backup
            if let errors = result.errors, !errors.isEmpty { error = errors.joined(separator: "\n") }
        } catch { self.error = error.localizedDescription }
        await loadHistory()
    }

    private func loadApps() async {
        guard !busy else { return }
        let requested = device
        let previousGame = gameID
        loadingApps = true; online = false; availableApps = []; apps = []; slots = []; backups = []; error = nil; message = nil; connectionNotice = nil
        defer { if requested == device { loadingApps = false } }
        struct Answer: Decodable { let apps: [InstalledSaveGame] }
        struct SavedAnswer: Decodable { let apps: [InstalledSaveGame]; let devices: [AppleTV] }
        do {
            let saved = try await Backend.ask(SavedAnswer.self, ["saved-games", "--device", requested])
            guard requested == device, !Task.isCancelled else { return }
            savedDevices = saved.devices
            if requested.isEmpty {
                device = library.device ?? devices.first?.id ?? ""
                return
            }
            apps = saved.apps
            gameID = apps.contains { $0.id == previousGame } ? previousGame : (apps.first?.id ?? "")
            await loadHistory()
        } catch {
            guard requested == device, !Task.isCancelled else { return }
            self.error = "Saved backups could not be read: " + error.localizedDescription
        }
        guard !requested.isEmpty else { return }
        do {
            let answer = try await Backend.ask(Answer.self, ["installed-games", "--device", requested])
            guard requested == device, !Task.isCancelled else { return }
            availableApps = Set(answer.apps.filter { $0.compatible }.map(\.id))
            apps = (answer.apps + apps.filter { saved in !answer.apps.contains { $0.id == saved.id } })
                .sorted { $0.name.localizedStandardCompare($1.name) == .orderedAscending }
            if !apps.contains(where: { $0.id == gameID }) {
                gameID = apps.first { $0.compatible && !$0.title_id.isEmpty && $0.title_id.caseInsensitiveCompare(library.current?.titleID ?? "") == .orderedSame }?.id
                    ?? apps.first { $0.compatible }?.id ?? ""
            }
            online = true
        } catch {
            if requested == device && !Task.isCancelled {
                connectionNotice = "Apple TV offline · Saved backups are available."
            }
        }
    }

    private func loadSlots() async {
        slots = []; backups = []; message = nil; resultFolder = nil
        guard game?.compatible == true, !busy else { loadingSlots = false; return }
        await loadHistory()
        guard online, availableApps.contains(gameID), !Task.isCancelled else { loadingSlots = false; return }
        let requestedGame = gameID, requestedDevice = device
        loadingSlots = true; error = nil
        defer { if requestedGame == gameID && requestedDevice == device { loadingSlots = false } }
        struct Answer: Decodable { let slots: [SaveSlot]; let backups: [ImportedSaveBackup] }
        do {
            let answer = try await Backend.ask(Answer.self, ["save-targets", "--device", requestedDevice, "--bundle", requestedGame])
            guard requestedGame == gameID, requestedDevice == device, !Task.isCancelled else { return }
            slots = answer.slots; backups = answer.backups; slot = "save"
        } catch {
            if requestedGame == gameID && requestedDevice == device && !Task.isCancelled {
                connectionNotice = "Apple TV saves unavailable · Saved backups are available."
            }
        }
        await loadHistory()
    }

    private func loadHistory() async {
        let requestedGame = gameID, requestedDevice = device
        guard !requestedGame.isEmpty else { return }
        struct Answer: Decodable { let backups: [ImportedSaveBackup] }
        if let answer = try? await Backend.ask(Answer.self, ["save-history", "--device", requestedDevice, "--bundle", requestedGame]),
           requestedGame == gameID, requestedDevice == device { backups = answer.backups }
    }

    private func transfer(command: String, backup: ImportedSaveBackup? = nil) async {
        guard canTransfer else { return }
        var args = [command]
        if command == "import-save" {
            guard let source else { return }
            args.append(source.folder)
        }
        args += ["--device", device, "--bundle", gameID]
        if command == "restore-save" {
            guard let backup else { return }
            args += ["--backup", backup.id]
        } else { args += ["--slot", slot] }
        if library.icloudBackups { args.append("--icloud") }
        library.transferringSaves = true; error = nil; message = nil; resultFolder = nil
        defer { library.transferringSaves = false }
        do {
            let result = try await Backend.ask(SaveTransferResult.self, args)
            if let available = result.icloud_available { library.icloudAvailable = available }
            message = result.message; resultFolder = result.backup
            if command != "export-save" {
                let changedSlot = backup?.slot ?? slot
                slots = slots.map { $0.id == changedSlot ? SaveSlot(id: $0.id, name: $0.name, files: result.files) : $0 }
            }
        } catch { self.error = error.localizedDescription }
        await loadHistory()
    }

    private func reveal(_ folder: String) {
        NSWorkspace.shared.open(URL(fileURLWithPath: folder, isDirectory: true))
    }
}
