import Foundation
import CoreGraphics

struct ArtworkCrop: Codable, Hashable {
    var scale = 1.0
    var x = 0.0
    var y = 0.0

    var arguments: [String] {
        ["--art-scale", String(scale), "--art-x", String(x), "--art-y", String(y)]
    }
}

// Match tv_icon.swift: positions select available overflow, not a fixed pixel offset.
extension ArtworkCrop {
    func rect(in source: CGSize, ratio: Double) -> CGRect {
        let width = min(source.width, source.height * ratio) / scale
        let height = width / ratio
        return CGRect(x: (source.width - width) * (x + 1) / 2,
                      y: (source.height - height) * (y + 1) / 2,
                      width: width, height: height)
    }

    func dragged(by translation: CGSize, source: CGSize, viewport: CGSize, ratio: Double) -> ArtworkCrop {
        guard source.width > 0, source.height > 0, viewport.width > 0, viewport.height > 0 else { return self }
        let area = rect(in: source, ratio: ratio)
        var moved = self
        let overflowX = source.width - area.width
        let overflowY = source.height - area.height
        // Moving the picture right/down moves the crop window left/up.
        if overflowX > 0.001 {
            moved.x = max(-1, min(1, x - 2 * translation.width * area.width / viewport.width / overflowX))
        }
        if overflowY > 0.001 {
            moved.y = max(-1, min(1, y - 2 * translation.height * area.height / viewport.height / overflowY))
        }
        return moved
    }
}
