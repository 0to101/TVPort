import SwiftUI
import UniformTypeIdentifiers

extension Game {
    var topShelfArguments: [String] {
        var arguments: [String] = []
        if let topShelfArtwork { arguments += ["--shelf-art", topShelfArtwork] }
        if let crop = topShelfCrop {
            arguments += ["--shelf-scale", String(crop.scale), "--shelf-x", String(crop.x), "--shelf-y", String(crop.y)]
        }
        return arguments
    }
}

struct TopShelfArtworkCard: View {
    @EnvironmentObject var library: Library
    @State private var choosing = false
    @State private var targeted = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Top Shelf Cover").font(.headline)
            ZStack(alignment: .bottom) {
                RoundedRectangle(cornerRadius: 10).fill(.quaternary)
                if let preview = library.topShelfPreview {
                    Image(nsImage: preview).resizable().aspectRatio(29.0 / 9.0, contentMode: .fit)
                }
                Text("Drop PNG or JPEG · 2320 × 720 (29:9)")
                    .font(.caption).foregroundStyle(.white)
                    .padding(5).frame(maxWidth: .infinity).background(.black.opacity(0.65))
            }
            .aspectRatio(29.0 / 9.0, contentMode: .fit)
            .clipShape(RoundedRectangle(cornerRadius: 10))
            .overlay { if targeted { RoundedRectangle(cornerRadius: 10).strokeBorder(.tint, lineWidth: 2) } }
            .accessibilityLabel("Top Shelf cover. Drop a PNG or JPEG. Recommended size 2320 by 720 pixels.")
            .dropDestination(for: URL.self) { urls, _ in
                guard let url = urls.first, url.isFileURL else { return false }
                if ["nsp", "xci", "nsz", "xcz"].contains(url.pathExtension.lowercased()) || url.hasDirectoryPath {
                    if let game = library.current { library.attachAddons(urls, to: game.id) }
                    return true
                }
                guard ["png", "jpg", "jpeg"].contains(url.pathExtension.lowercased()), NSImage(contentsOf: url) != nil else { return false }
                library.setTopShelfArtwork(url)
                return true
            } isTargeted: { targeted = $0 }
            HStack {
                Button("Choose Cover…") { choosing = true }
                if library.current?.topShelfArtwork != nil {
                    Button("Use Game Artwork") { library.setTopShelfArtwork(nil) }
                }
            }
            ArtworkFramingControls(topShelf: true)
            Text("Shown above the game in the Apple TV top row. Uses game artwork by default. Applies on next Build & Install.")
                .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
        }
        .fileImporter(isPresented: $choosing, allowedContentTypes: [.png, .jpeg]) { result in
            if case .success(let url) = result { library.setTopShelfArtwork(url) }
        }
    }
}
