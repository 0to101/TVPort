"""Verify pointer movement and crop bounds in the shared icon/cover geometry."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]


@unittest.skipUnless(sys.platform == 'darwin', 'macOS Foundation required')
class ArtworkDrag(unittest.TestCase):
    def test_drag_direction_bounds_and_image_shapes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checks = root / 'main.swift'
            checks.write_text(r'''
import Foundation
import CoreGraphics
func close(_ a: Double, _ b: Double) { assert(abs(a - b) < 0.0001, "\(a) != \(b)") }
let image = CGSize(width: 1600, height: 900)
let viewport = CGSize(width: 300, height: 180)
let original = ArtworkCrop(scale: 2, x: 0, y: 0)
let start = original.rect(in: image, ratio: 5.0 / 3.0)
let moved = original.dragged(by: CGSize(width: 75, height: 30), source: image, viewport: viewport, ratio: 5.0 / 3.0)
let area = moved.rect(in: image, ratio: 5.0 / 3.0)
// The visible picture must track the pointer by exactly 75 and 30 preview points.
close((start.minX - area.minX) * viewport.width / area.width, 75)
close((start.minY - area.minY) * viewport.height / area.height, 30)
assert(moved.scale == original.scale)
let back = moved.dragged(by: CGSize(width: -75, height: -30), source: image, viewport: viewport, ratio: 5.0 / 3.0)
close(back.x, 0); close(back.y, 0)
for ratio in [5.0 / 3.0, 8.0 / 3.0] {
    for size in [CGSize(width: 900, height: 900), CGSize(width: 3200, height: 600), image] {
        let view = CGSize(width: 300, height: 300 / ratio)
        let a = original.dragged(by: CGSize(width: 10000, height: 10000), source: size, viewport: view, ratio: ratio)
        let b = original.dragged(by: CGSize(width: -10000, height: -10000), source: size, viewport: view, ratio: ratio)
        close(a.rect(in: size, ratio: ratio).minX, 0); close(a.rect(in: size, ratio: ratio).minY, 0)
        close(b.rect(in: size, ratio: ratio).maxX, size.width); close(b.rect(in: size, ratio: ratio).maxY, size.height)
    }
}
let exact = CGSize(width: 2400, height: 900)
assert(ArtworkCrop().dragged(by: CGSize(width: 80, height: 50), source: exact,
                           viewport: CGSize(width: 300, height: 112.5), ratio: 8.0 / 3.0) == ArtworkCrop())
// Source pixel density must not change how dragging feels.
let doubled = original.dragged(by: CGSize(width: 75, height: 30), source: CGSize(width: 3200, height: 1800), viewport: viewport, ratio: 5.0 / 3.0)
close(doubled.x, moved.x); close(doubled.y, moved.y)
assert(original.dragged(by: CGSize(width: 10, height: 10), source: image, viewport: .zero, ratio: 5.0 / 3.0) == original)
print("PASS: pointer tracking, both crop ratios, edge clamping, no overflow, zoom and pixel density")
''')
            exe = root / 'check'
            subprocess.run(['swiftc', str(REPO / 'tvport/app/Sources/ArtworkCrop.swift'), str(checks), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)
