import SwiftUI
import AppKit
import UniformTypeIdentifiers

@main
struct TVPortApp: App {
    @StateObject private var library = Library()

    var body: some Scene {
        WindowGroup("TVPort") {
            ContentView().environmentObject(library).frame(width: 1000).frame(minHeight: 620)
                .background(InitialWindowSize())
        }
        .windowResizability(.contentSize)
        .defaultSize(width: 1000, height: 670)
        .windowToolbarStyle(.unified)
        .commands { TVPortCommands(library: library) }
        Settings {
            DefaultBuildFolderSettings().environmentObject(library)
        }
        Window("", id: "manage-saves") {
            SaveManagerView().environmentObject(library)
                .frame(width: 1000)
                .background(InitialWindowSize())
                .toolbar {
                    // Native toolbar chrome gives both windows the same corner treatment.
                    ToolbarItem(placement: .principal) {
                        Spacer().frame(width: 1).accessibilityHidden(true)
                    }
                }
                .toolbarBackground(.hidden, for: .windowToolbar)
        }
        .windowToolbarStyle(.unified)
        .defaultSize(width: 1000, height: 670)
        .windowResizability(.contentSize)
    }
}

// SwiftUI's defaultSize yields to saved window frames. Apply the requested
// starting size once after attachment, while allowing later height changes.
private struct InitialWindowSize: NSViewRepresentable {
    final class Marker: NSView {
        private weak var sizedWindow: NSWindow?

        override func viewDidMoveToWindow() {
            super.viewDidMoveToWindow()
            guard let window, window !== sizedWindow else { return }
            sizedWindow = window
            DispatchQueue.main.async { [weak self, weak window] in
                guard let self, let window, self.window === window else { return }
                let top = window.frame.maxY
                window.setContentSize(NSSize(width: 1000, height: 670))
                window.setFrameTopLeftPoint(NSPoint(x: window.frame.minX, y: top))
            }
        }
    }

    func makeNSView(context: Context) -> Marker { Marker() }
    func updateNSView(_ view: Marker, context: Context) {}
}

struct ContentView: View {
    @EnvironmentObject var library: Library
    @Environment(\.openWindow) private var openWindow
    @State private var choosingFolder = false

    var body: some View {
        NavigationSplitView(columnVisibility: .constant(.all)) {
            List(library.games, selection: $library.selection) { game in
                VStack(alignment: .leading, spacing: 6) {
                    GameArtworkThumbnail(titleID: game.titleID, name: game.name,
                                         artworkPath: game.artwork ?? (game.id == library.selection ? library.artworkPath : nil))
                    Text(game.name).lineLimit(1)
                    Text(game.built == true ? "Built" : "Ready to build").font(.callout).foregroundStyle(.secondary)
                    if let time = library.backedUp(game) { Text("Saves backed up \(time)").font(.caption).foregroundStyle(.secondary) }
                }
                .modifier(GameSelectionStyle(selected: library.selection == game.id))
                .tag(game.id)
                .contextMenu { Button("Remove from List") { library.remove(game) } }
            }
            .frame(width: 240)
            .navigationSplitViewColumnWidth(240)
            .toolbar(removing: .sidebarToggle)
            .toolbar {
                Button { choosingFolder = true } label: { Label("Add Game", systemImage: "plus") }
                    .help("Add a folder holding your game's .nsp or .xci files")
                Button { openWindow(id: "manage-saves") } label: { Label("Manage Saves", systemImage: "externaldrive.badge.timemachine") }
                    .help("Import, export and restore saves for games installed on an Apple TV")
                    .disabled(library.isBusy)
                SetupStatusButton()
            }
        } detail: {
            Group {
            if library.current == nil {
                VStack(spacing: 0) {
                    SetupBanner().padding(20)
                    ContentUnavailableView {
                        Label("No games yet", systemImage: "appletv")
                    } description: {
                        Text("Add a folder holding your own game's .nsp or .xci files, with any update or DLC.")
                    } actions: {
                        Button("Add Game Folder…") { choosingFolder = true }.buttonStyle(.borderedProminent)
                    }
                }
            } else {
                GameView()
            }
            }
            .frame(minWidth: 740)
        }
        .navigationSplitViewStyle(.balanced)
        .toolbar(removing: .sidebarToggle)
        .fileImporter(isPresented: $choosingFolder, allowedContentTypes: [.folder]) { result in
            if case .success(let folder) = result { library.add(folder: folder) }
        }
        .sheet(isPresented: $library.showingSetup) { SetupView().environmentObject(library) }
        .task { await library.checkSetup() }
        .task { await library.backUpEveryFewMinutes() }
        .task(id: library.selection) { await library.refresh() }
        .onChange(of: library.defaultBuildFolder) { _, _ in Task { await library.refresh() } }
    }

}

struct SetupStatusButton: View {
    @EnvironmentObject var library: Library

    var body: some View {
        Button { library.showingSetup = true } label: {
            Image(systemName: setupHasIssue ? "exclamationmark.triangle" : setupReady ? "checkmark.seal" : "seal")
                .symbolRenderingMode(.palette)
                .foregroundStyle(setupHasIssue ? Color.red : setupReady ? Color.green : Color.secondary)
                .font(.system(size: 20))
                .frame(width: 28, height: 28)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(setupHelp)
        .help(setupHelp)
    }

    private var setupHasIssue: Bool {
        !library.setupMissing.isEmpty || library.setupFailure != nil
            || (library.setup?.ready == false && !library.settingUp)
    }

    private var setupReady: Bool {
        library.setup?.ready == true && !setupHasIssue && !library.settingUp
    }

    private var setupHelp: String {
        if !library.setupMissing.isEmpty {
            return "Setup — missing: \(library.setupMissing.map(\.name).joined(separator: ", ")). Click to see what needs fixing."
        }
        if setupHasIssue { return "Setup needs attention. Click to see what needs fixing." }
        if setupReady { return "Setup — all requirements are ready." }
        return library.settingUp ? "Setup is in progress." : "Checking setup requirements…"
    }
}

struct GameView: View {
    @EnvironmentObject var library: Library

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    Header()
                    SetupBanner()
                    if let notice = library.notice { NoticeBar(text: notice) }
                    if let info = library.info, !info.prepared, info.sources.isEmpty {
                        NoticeBar(text: "This folder has no .nsp, .xci, .nsz or .xcz files. TVPort builds only from games you dumped from your own Switch.")
                    }
                    HStack(alignment: .top, spacing: 20) {
                        ArtworkCard().frame(width: 300)
                        // The grouped form adds its own 20-point horizontal inset.
                        // Let the surrounding content provide the shared margins.
                        SettingsForm().padding(.horizontal, -20)
                    }
                    if let diagnosis = library.diagnosis { DiagnosisCard(diagnosis: diagnosis) }
                }
                .padding(20)
            }
            if library.run != .idle || !library.stage.isEmpty || !library.log.isEmpty {
                Divider()
                ProgressPanel()
            }
        }
        .navigationTitle("")
        .toolbar { gameToolbar }
    }

    @ToolbarContentBuilder
    private var gameToolbar: some ToolbarContent {
        if #available(macOS 26.0, *) {
            ToolbarItem(placement: .primaryAction) { actions }
                .sharedBackgroundVisibility(.hidden)
        } else {
            ToolbarItem(placement: .primaryAction) { actions }
        }
    }

    private var actions: some View {
        HStack(spacing: 8) {
            ToolbarActionButton(title: "Last Run Stats", enabled: canUseInstalledGame,
                                help: "Read memory and frame times from the Apple TV") { library.diagnose() }
            ToolbarActionButton(title: "Open on TV", enabled: canUseInstalledGame) { library.launch() }
            if library.isBusy {
                ToolbarActionButton(title: "Stop") { library.cancel() }
            } else {
                ToolbarActionButton(title: "Build & Install", enabled: canBuild, primary: true) { library.build(install: true) }
            }
        }
        // Add to the toolbar's 8-point inset to match the content's 20-point margin.
        .padding(.trailing, 12)
    }

    private var canUseInstalledGame: Bool {
        library.bundleID != nil && library.device != nil && !library.isBusy
    }

    private var canBuild: Bool {
        guard let info = library.info, library.device != nil, library.setupMissing.isEmpty, !library.settingUp else { return false }
        return info.prepared || (!info.sources.isEmpty && library.keys != nil)
    }
}

struct Header: View {
    @EnvironmentObject var library: Library

    var body: some View {
        if let info = library.info {
            VStack(alignment: .leading, spacing: 4) {
                Text(info.name).font(.title2.weight(.semibold))
                Text([info.version.isEmpty ? nil : "Version \(info.version)", info.title_id.isEmpty ? nil : "ID: \(info.title_id)", info.built == true ? "Built" : "Ready to build"]
                    .compactMap { $0 }.joined(separator: " · ")).foregroundStyle(.secondary)
                if let days = info.signing?.days_left, days < 3, info.signing?.free_team == true {
                    Label(days < 0 ? "This install's signature has expired, so the TV won't open it. Build & Install renews it." : "This install stops opening in \(days) day\(days == 1 ? "" : "s"). Build & Install renews it.",
                          systemImage: "clock.badge.exclamationmark").foregroundStyle(.orange)
                }
            }
        } else {
            ProgressView().controlSize(.small)
        }
    }
}

/// Shown while something a build needs is missing, or while the first start sets up the engine.
struct SetupBanner: View {
    @EnvironmentObject var library: Library

    var body: some View {
        if library.settingUp {
            HStack {
                ProgressView().controlSize(.small)
                Text("Setting up: \(library.setupStage)").lineLimit(1)
            }
            .frame(maxWidth: .infinity, alignment: .leading).padding(10).background(.blue.opacity(0.1), in: RoundedRectangle(cornerRadius: 8))
        } else if !library.setupMissing.isEmpty || library.setupFailure != nil {
            HStack {
                Label(library.setupFailure != nil ? "TVPort could not finish setting up." : "Before the first build, this Mac needs: \(library.setupMissing.map(\.name).joined(separator: ", ")).",
                      systemImage: "exclamationmark.triangle")
                Spacer()
                Button("Show Setup") { library.showingSetup = true }
            }
            .padding(10).background(.orange.opacity(0.15), in: RoundedRectangle(cornerRadius: 8))
        }
    }
}

struct SetupView: View {
    @EnvironmentObject var library: Library
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Setup").font(.title2.weight(.semibold))
            Text("TVPort carries its engine and sets up its own Python. A build also needs these from Apple and others, which only you can install. Your games and prod.keys stay in the folders you choose.")
                .foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            if let checks = library.setup?.checks {
                ForEach(checks) { check in
                    HStack(alignment: .top, spacing: 10) {
                        Image(systemName: check.ok ? "checkmark.circle.fill" : "exclamationmark.circle.fill").foregroundStyle(check.ok ? .green : .orange)
                        VStack(alignment: .leading, spacing: 3) {
                            HStack {
                                Text(check.name).font(.headline)
                                Text(check.detail).foregroundStyle(.secondary).lineLimit(1).truncationMode(.middle)
                            }
                            if !check.ok {
                                if !check.fix.isEmpty { Text(check.fix).fixedSize(horizontal: false, vertical: true) }
                                if !check.command.isEmpty {
                                    HStack {
                                        Text(check.command).font(.system(.callout, design: .monospaced)).textSelection(.enabled)
                                        Button("Copy") {
                                            NSPasteboard.general.clearContents()
                                            NSPasteboard.general.setString(check.command, forType: .string)
                                        }
                                        .controlSize(.small)
                                    }
                                }
                            }
                        }
                    }
                }
            } else {
                ProgressView().controlSize(.small)
            }
            if library.settingUp {
                HStack { ProgressView().controlSize(.small); Text(library.setupStage) }
            }
            if let failure = library.setupFailure {
                Text(failure).font(.callout).foregroundStyle(.red).textSelection(.enabled).lineLimit(8)
            }
            HStack {
                Button("Check Again") { Task { await library.checkSetup() } }.disabled(library.settingUp)
                if library.setup?.can_set_up == true && library.setup?.checks.first(where: { $0.name == "Python" })?.ok == false {
                    Button("Set Up") { library.runSetup() }.disabled(library.isBusy)
                }
                Spacer()
                Button("Done") { dismiss() }.keyboardShortcut(.defaultAction)
            }
        }
        .padding(20).frame(width: 600)
    }
}

struct NoticeBar: View {
    let text: String
    var body: some View {
        Label(text, systemImage: "info.circle").frame(maxWidth: .infinity, alignment: .leading).padding(10)
            .background(.yellow.opacity(0.15), in: RoundedRectangle(cornerRadius: 8))
    }
}

struct ArtworkCard: View {
    @EnvironmentObject var library: Library
    @State private var choosing = false
    @State private var targeted = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Apple TV Icon").font(.headline)
            ZStack {
                RoundedRectangle(cornerRadius: 10).fill(.quaternary)
                if let preview = library.preview {
                    Image(nsImage: preview).resizable().aspectRatio(5.0 / 3.0, contentMode: .fit).clipShape(RoundedRectangle(cornerRadius: 10))
                } else {
                    VStack(spacing: 6) {
                        Image(systemName: "photo").font(.title)
                        Text("Drop an image here")
                    }.foregroundStyle(.secondary)
                }
                if targeted { RoundedRectangle(cornerRadius: 10).strokeBorder(.tint, lineWidth: 3) }
            }
            .aspectRatio(5.0 / 3.0, contentMode: .fit)
            .accessibilityLabel("Apple TV icon preview. Drop an image to replace it.")
            .dropDestination(for: URL.self) { urls, _ in
                guard let url = urls.first else { return false }
                library.setArtwork(url)
                return true
            } isTargeted: { targeted = $0 }
            HStack {
                Button("Choose Artwork…") { choosing = true }
                if library.current?.artwork != nil { Button("Use Automatic Artwork") { library.setArtwork(nil) } }
            }
            if library.current?.artwork == nil, !library.artworkStatus.isEmpty {
                Text(library.artworkStatus).font(.caption).foregroundStyle(.secondary)
            }
            ArtworkFramingControls()
            Text("Automatic framing keeps square art on a blurred background. Crop to fill lets you zoom and choose the visible area. The Top Shelf banner uses the same cropped image. Takes effect at the next Build & Install.")
                .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
        }
        .fileImporter(isPresented: $choosing, allowedContentTypes: [.image]) { result in
            if case .success(let url) = result { library.setArtwork(url) }
        }
    }
}

struct SettingsForm: View {
    @EnvironmentObject var library: Library
    @Environment(\.openWindow) private var openWindow
    @State private var choosingKeys = false

    var body: some View {
        Form {
            Section("Build folder") {
                GameBuildFolderSettings()
            }
            Section("Apple TV") {
                Picker("Device", selection: $library.device) {
                    if library.devices.isEmpty { Text("None found").tag(AppleTV.ID?.none) }
                    ForEach(library.devices) { Text($0.title).tag(Optional($0.id)) }
                }
                TextField("Signing team", text: $library.team, prompt: Text("10-character team ID"))
                Button("Look Again") { Task { await library.refreshDevices() } }
            }
            Section("Performance") {
                Picker("Render mode", selection: binding(\.mode, default: .handheld)) { ForEach(RenderMode.allCases) { Text($0.label).tag($0) } }
                Text(library.current?.mode.note ?? "").font(.caption).foregroundStyle(.secondary)
                Picker("Texture detail", selection: binding(\.texture, default: .medium)) { ForEach(TextureDetail.allCases) { Text($0.label).tag($0) } }
                Text("The A15 has to store these textures uncompressed, so lower detail saves memory and shortens loading.").font(.caption).foregroundStyle(.secondary)
                if library.info?.render_scale == true {
                    Picker("3D resolution", selection: renderScaleBinding) {
                        ForEach([1.0, 0.9, 0.8, 0.75, 0.7, 0.6, 0.5], id: \.self) { Text($0 == 1 ? "Full" : "\(Int(($0 * 100).rounded()))%").tag($0) }
                    }
                    Text("Draws the game's 3D scene at a lower resolution, so the GPU keeps up; menus and text stay sharp. Below Full the size is fixed, in place of the game's own dynamic resolution. Takes effect at the next Build & Install.")
                        .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                }
                Picker("Frame rate", selection: fpsBinding(profileFPS ?? 0)) {
                    if profileFPS == nil { Text("Game default").tag(0) }
                    Text("30 fps").tag(30)
                    Text("Up to 60 fps").tag(60)
                }
                .disabled(profileFPS == nil)
                Text(frameRateNote)
                    .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                if library.info?.frame_step == true {
                    Toggle("Hold 30 fps when the Apple TV is hot", isOn: coolBinding)
                    Text("When tvOS reports the TV as hot, it lowers the chip's speed, the GPU to about a third, whatever the game does, and this makes the game hold 30 fps so the TV cools down sooner. Off, the game keeps trying for 60, which it can then rarely reach, and the TV stays hot and slow for longer. Takes effect at the next Build & Install.")
                        .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                }
                Toggle("Frame-rate counter", isOn: binding(\.showFPS, default: false))
                Text("Shows how many frames reach the screen each second (FPS) while you play, so you can monitor performance. This only displays the frame rate; it does not change the FPS limit. Takes effect at the next Build & Install.")
                    .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            }
            Section("Controller") {
                Toggle("Swap A/B and X/Y", isOn: swapButtonsBinding)
                Text("Swaps A with B and X with Y on connected controllers for this game. Takes effect at the next Build & Install.")
                    .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            }
            Section("Saves") {
                Button("Manage Saves…") { openWindow(id: "manage-saves") }.disabled(library.isBusy)
                Text("While TVPort is open, it backs up each built game's saves from the Apple TV every 5 minutes, only reading the TV. Enable iCloud backups in Manage Saves to keep new backups in iCloud Drive, in TVPort Saves.")
                    .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                TextField("Players", text: playersBinding, prompt: Text("Names, separated by commas"))
                Text("With two or more names, the Apple TV asks who's playing, and each person gets their own saves. The first name picked keeps the saves already on the TV. Takes effect at the next Build & Install.")
                    .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                if let game = library.current, let time = library.backedUp(game) {
                    LabeledContent("Last backup", value: "\(time), \(place(game))")
                }
            }
            if library.info?.prepared == false {
                Section("First Build") {
                    LabeledContent("prod.keys") {
                        HStack {
                            Text(library.keys.map { URL(fileURLWithPath: $0).deletingLastPathComponent().lastPathComponent + "/prod.keys" } ?? "Not found").foregroundStyle(.secondary)
                            Button("Choose…") { choosingKeys = true }
                        }
                    }
                    Text("The keys of your own Switch. The first build reads them to decrypt the game, and TVPort never copies them or puts them in what it builds.")
                        .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                }
            }
        }
        .formStyle(.grouped).scrollDisabled(true)
        .fileImporter(isPresented: $choosingKeys, allowedContentTypes: [.data, .item]) { result in
            if case .success(let url) = result { library.update { $0.keys = url.path } }
        }
    }

    private func place(_ game: Game) -> String {
        (library.backups[game.folder]?.last_backup_place ?? library.info?.last_backup_place) == "icloud" ? "iCloud Drive" : "this Mac"
    }

    private var playersBinding: Binding<String> {
        Binding(get: { library.current?.players ?? "" }, set: { value in library.update { $0.players = value } })
    }

    private var profileFPS: Int? {
        guard let fps = library.info?.fps_target, [30, 60].contains(fps) else { return nil }
        return fps
    }

    private var frameRateNote: String {
        guard let info = library.info else { return "Frame-rate selection is unavailable until the game has been checked." }
        if info.title_id.isEmpty { return "Frame-rate selection becomes available once a supported game profile is detected. Until then, the game uses its own frame rate." }
        guard profileFPS != nil else { return "This game's profile does not support choosing a frame rate. The game uses its own frame rate." }
        return "At 30 the TV does half the work, so it heats up more slowly and loads faster, and a game the TV cannot run at 60 is steadier. Up to 60 holds 60 where the TV keeps up and 30 where it does not. Takes effect at the next Build & Install."
    }

    private func fpsBinding(_ profile: Int) -> Binding<Int> {
        Binding(get: { profile == 0 ? 0 : library.current?.fpsTarget ?? profile }, set: { value in
            guard profile != 0 else { return }
            library.update { $0.fpsTarget = value == profile ? nil : value }
        })
    }

    private var swapButtonsBinding: Binding<Bool> {
        Binding(get: { library.current?.swapABXY ?? false }, set: { value in library.update { $0.swapABXY = value } })
    }

    private var coolBinding: Binding<Bool> {
        Binding(get: { library.current?.coolWhenHot ?? true }, set: { value in library.update { $0.coolWhenHot = value ? nil : false } })
    }

    private var renderScaleBinding: Binding<Double> {
        Binding(get: { library.current?.renderScale ?? 1 }, set: { value in library.update { $0.renderScale = value < 1 ? value : nil } })
    }

    private func binding<T>(_ path: WritableKeyPath<Game, T>, default fallback: T) -> Binding<T> {
        // SwiftUI can read a control's binding while removing its game view.
        // Keep it tied to that game and tolerate the game no longer existing.
        let gameID = library.selection
        return Binding(get: {
            library.games.first { $0.id == gameID }?[keyPath: path] ?? fallback
        }, set: { value in
            guard library.selection == gameID else { return }
            library.update { $0[keyPath: path] = value }
        })
    }
}

struct DiagnosisCard: View {
    let diagnosis: Diagnosis

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Last Run").font(.headline)
            Grid(alignment: .leading, horizontalSpacing: 28, verticalSpacing: 4) {
                GridRow { stat("Peak memory", "\(Int(diagnosis.run.peak_mb)) MB"); stat("Long frames", "\(diagnosis.run.hitches)"); stat("Worst frame", "\(Int(diagnosis.run.worst_ms)) ms") }
                GridRow { stat("Closest to limit", diagnosis.run.min_headroom_mb.map { "\(Int($0)) MB left" } ?? "Not reported"); stat("Texture loading", "\(Int(diagnosis.run.texture_ms)) ms"); stat("Shaders", "\(Int(diagnosis.run.pipeline_ms)) ms") }
            }
            ForEach(diagnosis.verdicts, id: \.self) { Label($0, systemImage: "arrow.right.circle") }
        }
        .frame(maxWidth: .infinity, alignment: .leading).padding(14)
        .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 10))
    }

    private func stat(_ title: String, _ value: String) -> some View {
        VStack(alignment: .leading) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            Text(value).font(.body.monospacedDigit().weight(.medium))
        }
    }
}

struct ProgressPanel: View {
    @EnvironmentObject var library: Library
    @State private var showLog = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                switch library.run {
                case .idle:
                    if !library.stage.isEmpty { Text(library.stage).foregroundStyle(.secondary) }
                case .running:
                    ProgressView().controlSize(.small)
                    Text(library.stage).lineLimit(1)
                case .succeeded: Label(library.stage, systemImage: "checkmark.circle.fill").foregroundStyle(.green)
                case .failed: Label("Failed", systemImage: "xmark.octagon.fill").foregroundStyle(.red)
                }
                if !library.log.isEmpty {
                    if library.run != .idle || !library.stage.isEmpty {
                        Text("|").foregroundStyle(.secondary).accessibilityHidden(true)
                    }
                    Button(showLog ? "Hide Log" : "Show Log") { showLog.toggle() }.buttonStyle(.link)
                }
                Spacer()
            }
            if library.run == .running, let progress = library.progress { ProgressView(value: progress) }
            if case .failed(let message) = library.run {
                Text(message).font(.callout).textSelection(.enabled).lineLimit(8).foregroundStyle(.red)
            }
            if showLog && !library.log.isEmpty {
                ScrollViewReader { reader in
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 0) {
                            ForEach(Array(library.log.enumerated()), id: \.offset) { index, line in
                                Text(line).font(.system(.caption, design: .monospaced)).textSelection(.enabled).id(index)
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .frame(height: 170)
                    .onChange(of: library.log.count) { _, count in reader.scrollTo(count - 1, anchor: .bottom) }
                }
            }
        }
        .padding(12)
        .onChange(of: library.log.isEmpty) { _, isEmpty in
            if isEmpty { showLog = false }
        }
    }
}
