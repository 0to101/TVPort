import SwiftUI
import ImageIO

/// Uses the library's chosen artwork first, then the shared cached Nintendo artwork.
struct GameArtworkThumbnail: View {
    let titleID: String
    let name: String
    var artworkPath: String?
    var width: CGFloat? = nil
    var height: CGFloat = 100
    @Environment(\.displayScale) private var displayScale
    @State private var image: CGImage?

    var body: some View {
        RoundedRectangle(cornerRadius: 6).fill(.quaternary)
        .overlay {
            if let image {
                Image(decorative: image, scale: displayScale, orientation: .up)
                    .resizable().interpolation(.high).scaledToFill()
            } else {
                Image(systemName: "gamecontroller").foregroundStyle(.secondary)
            }
        }
        .frame(width: width, height: height)
        .clipped().clipShape(RoundedRectangle(cornerRadius: 6))
        .accessibilityHidden(true)
        .task(id: "\(titleID)|\(name)|\(artworkPath ?? "")|\(displayScale)") {
            image = artworkPath.flatMap { thumbnail(URL(fileURLWithPath: $0)) }
            guard image == nil else { return }
            let id: String
            if !titleID.isEmpty { id = titleID }
            else { id = await ArtworkStore.shared.titleID(named: name) ?? "" }
            guard !Task.isCancelled, !id.isEmpty else { return }
            if let cached = ArtworkStore.cachedBanner(id) { image = thumbnail(cached) }
            await ArtworkStore.shared.fetchMissing([id])
            guard !Task.isCancelled else { return }
            if let cached = ArtworkStore.cachedBanner(id) { image = thumbnail(cached) }
        }
    }

    private func thumbnail(_ url: URL) -> CGImage? {
        guard let source = CGImageSourceCreateWithURL(url as CFURL, nil) else { return nil }
        let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any]
        let sourceWidth = (properties?[kCGImagePropertyPixelWidth] as? NSNumber)?.doubleValue ?? 1
        let sourceHeight = (properties?[kCGImagePropertyPixelHeight] as? NSNumber)?.doubleValue ?? 1
        let ratio = sourceWidth / max(sourceHeight, 1)
        let targetWidth = Double(width ?? 280)
        // Downsample before rendering, retaining enough pixels for aspect-fill on Retina displays.
        let longestSide = max(targetWidth, Double(height) * ratio, Double(height), targetWidth / ratio)
        return CGImageSourceCreateThumbnailAtIndex(source, 0, [
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceCreateThumbnailWithTransform: true,
            kCGImageSourceThumbnailMaxPixelSize: Int(ceil(longestSide * displayScale)),
            kCGImageSourceShouldCacheImmediately: true
        ] as CFDictionary)
    }
}
