import AppKit

// Regenerate the transparent foreground for TVPortIcon.icon using macOS SF Symbols.
let size = 1024
let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
let context = NSGraphicsContext(bitmapImageRep: bitmap)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = context


func symbol(_ name: String, rect: NSRect, color: NSColor, operation: NSCompositingOperation = .sourceOver) {
    let configuration = NSImage.SymbolConfiguration(pointSize: 300, weight: .regular).applying(NSImage.SymbolConfiguration(paletteColors: [color]))
    let image = NSImage(systemSymbolName: name, accessibilityDescription: nil)!.withSymbolConfiguration(configuration)!
    let scale = min(rect.width / image.size.width, rect.height / image.size.height)
    let bounds = NSRect(x: rect.midX - image.size.width * scale / 2, y: rect.midY - image.size.height * scale / 2, width: image.size.width * scale, height: image.size.height * scale)
    image.draw(in: bounds, from: .zero, operation: operation, fraction: 1)
}

symbol("appletv", rect: NSRect(x: 230, y: 150, width: 570, height: 500), color: .white)
NSGraphicsContext.saveGraphicsState()
let transform = NSAffineTransform()
transform.translateX(by: 530, yBy: 655)
transform.rotate(byDegrees: -22)
transform.concat()
// A transparent separation keeps both glyphs distinct in every icon appearance.
for angle in stride(from: 0.0, to: 360.0, by: 15.0) {
    let rad = angle * .pi / 180
    symbol("gamecontroller.fill", rect: NSRect(x: -310 + cos(rad)*12, y: -185 + sin(rad)*12, width: 620, height: 370), color: .white, operation: .destinationOut)
}
symbol("gamecontroller.fill", rect: NSRect(x: -310, y: -185, width: 620, height: 370), color: .white)
NSGraphicsContext.restoreGraphicsState()
NSGraphicsContext.restoreGraphicsState()
let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
let output = root.appendingPathComponent("tvport/app/Resources/TVPortIcon.icon/Assets/TVController.png")
try bitmap.representation(using: .png, properties: [:])!.write(to: output)
print(output.path)
