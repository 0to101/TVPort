import SwiftUI
import AppKit

/// Live crop movement uses the original pixels, then persists once on release.
/// The normal rendered preview remains in use for Automatic framing.
struct ArtworkPositioningPreview: View {
    @EnvironmentObject var library: Library
    let preview: NSImage
    var topShelf = false
    @State private var source: NSImage?
    @State private var dragStart: ArtworkCrop?
    @State private var dragCrop: ArtworkCrop?

    private var ratio: Double { topShelf ? 8.0 / 3.0 : 5.0 / 3.0 }
    private var crop: ArtworkCrop? { topShelf ? library.current?.topShelfCrop : library.current?.artworkCrop }
    private var input: Source {
        Source(path: topShelf ? library.current?.topShelfArtwork ?? library.artworkPath : library.artworkPath,
               inheritedCrop: topShelf && library.current?.topShelfArtwork == nil ? library.current?.artworkCrop : nil)
    }

    private struct Source: Equatable {
        let path: String?
        let inheritedCrop: ArtworkCrop?
    }

    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .topLeading) {
                if let source, let position = dragCrop ?? crop {
                    let area = position.rect(in: source.size, ratio: ratio)
                    let scale = geometry.size.width / area.width
                    Image(nsImage: source).resizable()
                        .frame(width: source.size.width * scale, height: source.size.height * scale)
                        .offset(x: -area.minX * scale, y: -area.minY * scale)
                } else {
                    Image(nsImage: preview).resizable()
                        .frame(width: geometry.size.width, height: geometry.size.height)
                }
            }
            .frame(width: geometry.size.width, height: geometry.size.height, alignment: .topLeading)
            .clipped()
            .contentShape(Rectangle())
            .gesture(DragGesture(minimumDistance: 2)
                .onChanged { value in
                    guard let source, let crop else { return }
                    if dragStart == nil { dragStart = crop }
                    dragCrop = dragStart?.dragged(by: value.translation, source: source.size,
                                                  viewport: geometry.size, ratio: ratio)
                }
                .onEnded { _ in
                    if let moved = dragCrop {
                        if topShelf { library.setTopShelfCrop(moved) } else { library.setArtworkCrop(moved) }
                    }
                    dragStart = nil; dragCrop = nil
                }, including: crop != nil && source != nil ? .all : .none)
        }
        .aspectRatio(ratio, contentMode: .fit)
        .help(crop == nil ? "Choose Crop to fill to drag the image." : "Drag to position the image. Zoom in for more movement.")
        .task(id: input) { loadSource() }
        .onChange(of: crop) { _, _ in dragStart = nil; dragCrop = nil }
    }

    private func loadSource() {
        dragStart = nil; dragCrop = nil; source = nil
        guard let path = input.path, let image = NSImage(contentsOfFile: path),
              var pixels = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else { return }
        // The default Top Shelf source is the already-cropped app artwork,
        // exactly as in tv_icon.swift. A custom cover has its own original pixels.
        if let inherited = input.inheritedCrop {
            let size = CGSize(width: pixels.width, height: pixels.height)
            guard let cropped = pixels.cropping(to: inherited.rect(in: size, ratio: 5.0 / 3.0)) else { return }
            pixels = cropped
        }
        source = NSImage(cgImage: pixels, size: NSSize(width: pixels.width, height: pixels.height))
    }
}
