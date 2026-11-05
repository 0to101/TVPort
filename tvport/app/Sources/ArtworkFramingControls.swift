import SwiftUI

struct ArtworkCrop: Codable, Hashable {
    var scale = 1.0
    var x = 0.0
    var y = 0.0

    var arguments: [String] {
        ["--art-scale", String(scale), "--art-x", String(x), "--art-y", String(y)]
    }
}

struct ArtworkFramingControls: View {
    @EnvironmentObject var library: Library

    var topShelf = false
    private var crop: ArtworkCrop? { topShelf ? library.current?.topShelfCrop : library.current?.artworkCrop }
    private var hasArtwork: Bool { library.artworkPath != nil || (topShelf && library.current?.topShelfArtwork != nil) }
    private func setCrop(_ value: ArtworkCrop?) {
        if topShelf { library.setTopShelfCrop(value) } else { library.setArtworkCrop(value) }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Picker("Framing", selection: Binding(
                get: { crop != nil },
                set: { setCrop($0 ? ArtworkCrop() : nil) }
            )) {
                Text("Automatic").tag(false)
                Text("Crop to fill").tag(true)
            }
            if let crop {
                HStack {
                    Text("Zoom")
                    Spacer()
                    Text("\(Int((crop.scale * 100).rounded()))%")
                        .monospacedDigit().foregroundStyle(.secondary)
                }
                Slider(value: binding(\.scale), in: 1...3, step: 0.05)
                    .accessibilityLabel("Artwork zoom")
                Slider(value: binding(\.x), in: -1...1) {
                    Text("Horizontal position")
                } minimumValueLabel: { Text("Left") } maximumValueLabel: { Text("Right") }
                Slider(value: binding(\.y), in: -1...1) {
                    Text("Vertical position")
                } minimumValueLabel: { Text("Top") } maximumValueLabel: { Text("Bottom") }
                Button("Reset Crop") { setCrop(ArtworkCrop()) }
                    .disabled(crop == ArtworkCrop())
            }
        }
        .disabled(!hasArtwork)
    }

    private func binding(_ key: WritableKeyPath<ArtworkCrop, Double>) -> Binding<Double> {
        Binding(get: { (crop ?? ArtworkCrop())[keyPath: key] }, set: { value in
            var crop = self.crop ?? ArtworkCrop()
            crop[keyPath: key] = value
            setCrop(crop)
        })
    }
}
