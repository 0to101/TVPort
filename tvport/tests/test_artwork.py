"""Crop geometry and renderer parity, using synthetic artwork rather than game files."""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import backend


class ArtworkOptions(unittest.TestCase):
    def test_crop_arguments_are_bounded(self):
        self.assertEqual(backend.art_scale_arg('0'), 0)
        self.assertEqual(backend.art_scale_arg('3'), 3)
        for value in ['0.5', '-1', '4', 'nan', 'inf']:
            with self.assertRaises(argparse.ArgumentTypeError):
                backend.art_scale_arg(value)
        for value in ['-2', '2', 'nan', 'inf']:
            with self.assertRaises(argparse.ArgumentTypeError):
                backend.art_position_arg(value)

    def test_same_settings_for_preview_and_build(self):
        args = argparse.Namespace(art_scale=2.0, art_x=-1.0, art_y=1.0)
        self.assertEqual(backend.artwork_env(args), {
            'DM_ICON_CROP_SCALE': '2.0', 'DM_ICON_CROP_X': '-1.0', 'DM_ICON_CROP_Y': '1.0'})

    @unittest.skipUnless(sys.platform == 'darwin', 'AppKit renderer requires macOS')
    def test_renderer_crop_and_installed_icon_match(self):
        renderer = backend.REPO / 'dm/ios/tools/tv_icon.swift'
        # Run the actual rendering functions with known image geometry and compare
        # the flattened generated icon with the preview's composition at 2x.
        source = renderer.read_text().split('let args = CommandLine.arguments')[0]
        checks = r'''
let c = bitmap(600, 600)
for row in 0..<6 {
    for column in 0..<6 {
        c.setFillColor(CGColor(srgbRed: Double(column) / 5, green: Double(row) / 5, blue: 0.3, alpha: 1))
        c.fill(CGRect(x: column * 100, y: row * 100, width: 100, height: 100))
    }
}
let original = c.makeImage()!
assert(cropArtwork(original, environment: [:]) === original)
func pixels(_ image: CGImage) -> Data {
    let b = bitmap(image.width, image.height)
    b.draw(image, in: CGRect(x: 0, y: 0, width: image.width, height: image.height))
    return Data(bytes: b.data!, count: b.bytesPerRow * b.height)
}
for (x, y, origin) in [(-1.0, -1.0, CGPoint(x: 0, y: 0)),
                       (0.0, 0.0, CGPoint(x: 150, y: 210)),
                       (1.0, 1.0, CGPoint(x: 300, y: 420))] {
    let image = cropArtwork(original, environment: ["DM_ICON_CROP_SCALE": "2", "DM_ICON_CROP_X": String(x), "DM_ICON_CROP_Y": String(y)])
    assert(image.width == 300 && image.height == 180)
    let expected = original.cropping(to: CGRect(origin: origin, size: CGSize(width: 300, height: 180)))!
    assert(pixels(image) == pixels(expected))
}
let art = cropArtwork(original, environment: ["DM_ICON_CROP_SCALE": "2", "DM_ICON_CROP_X": "1", "DM_ICON_CROP_Y": "-1"])
let out = URL(fileURLWithPath: CommandLine.arguments[1])
_ = imageStack(art, "Test", 400, 240, [2], in: out)
let area = CGRect(x: 0, y: 0, width: 800, height: 480)
let preview = bitmap(800, 480)
preview.draw(backLayer(art, 800, 480), in: area)
preview.draw(frontLayer(art, 800, 480), in: area)
let installed = bitmap(800, 480)
for layer in ["Back", "Front"] {
    installed.draw(loadImage(out.appendingPathComponent("Test.imagestack/\(layer).imagestacklayer/Content.imageset/icon@2x.png").path), in: area)
}
assert(pixels(preview.makeImage()!) == pixels(installed.makeImage()!))
// The independent wide crop keeps its own zoom and offset, without touching icon geometry.
let wideCanvas = bitmap(580, 360)
wideCanvas.draw(original, in: CGRect(x: 0, y: 0, width: 580, height: 360))
let wideOriginal = wideCanvas.makeImage()!
for (x, y) in [(-1.0, -1.0), (0.0, 0.0), (1.0, 1.0)] {
    let cropped = cropArtwork(wideOriginal, environment: ["DM_SHELF_CROP_SCALE": "2", "DM_SHELF_CROP_X": String(x), "DM_SHELF_CROP_Y": String(y)], prefix: "DM_SHELF", ratio: 29.0 / 9.0)
    assert(cropped.width == 290 && cropped.height == 90)
    let expected = wideOriginal.cropping(to: CGRect(x: 290 * (x + 1) / 2, y: 270 * (y + 1) / 2, width: 290, height: 90))!
    assert(pixels(cropped) == pixels(expected))
}
print("Icon and wide cover crop geometry passed")
'''
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / 'check.swift'
            script.write_text(source + checks)
            result = subprocess.run(['xcrun', 'swift', '-module-cache-path', str(Path(folder) / 'modules'), str(script), folder], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
