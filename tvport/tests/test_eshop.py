import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import backend


class ArtworkTitleID(unittest.TestCase):
    def test_filename_hint_does_not_change_build_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            (p / 'Game [0100DBF01000A000][v0].nsp').touch()
            (p / 'Update [0100DBF01000A800].nsp').touch()
            game = backend.Game(p)
            self.assertEqual(game.artwork_title_id, '0100DBF01000A000')
            self.assertEqual(game.title_id, '')
            self.assertIsNone(game.build)
            (p / 'Another [0100000000010000].xci').touch()
            self.assertEqual(backend.Game(p).artwork_title_id, '')

    @unittest.skipUnless(sys.platform == 'darwin', 'AppKit artwork cache requires macOS')
    def test_download_selection_cache_and_offline_fallback(self):
        source = backend.REPO / 'tvport/app/Sources/ArtworkStore.swift'
        harness = r'''
import AppKit
import Foundation

enum Backend { static let data = URL(fileURLWithPath: CommandLine.arguments[1]) }
final class FixtureProtocol: URLProtocol {
    static var count = 0
    static var offline = false
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        Self.count += 1
        if Self.offline {
            client?.urlProtocol(self, didFailWithError: URLError(.notConnectedToInternet))
            return
        }
        let url = request.url!
        let bytes: Data
        if url.host == "raw.githubusercontent.com" {
            let products: [String: Any] = [
                "base": ["id": "0100DBF01000A000", "name": "Game", "nsuId": "10", "bannerUrl": "https://img-eshop.cdn.nintendo.net/base.png"],
                "bundle": ["id": "0100DBF01000A000", "name": "Game Deluxe Edition", "nsuId": 1, "bannerUrl": "https://img-eshop.cdn.nintendo.net/bundle.png"],
                "second": ["id": "0100000000010000", "name": "Other", "bannerUrl": "https://img-eshop.cdn.nintendo.net/other.png"],
                "unsafe": ["id": "0100000000020000", "name": "Unsafe", "bannerUrl": "https://example.com/image.png"]]
            bytes = try! JSONSerialization.data(withJSONObject: products)
        } else {
            precondition(url.host == "img-eshop.cdn.nintendo.net" && url.path != "/bundle.png")
            let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: 2, pixelsHigh: 2, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
            bytes = bitmap.representation(using: .png, properties: [:])!
        }
        client?.urlProtocol(self, didReceive: HTTPURLResponse(url: url, statusCode: 200, httpVersion: nil, headerFields: nil)!, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: bytes)
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}
@main struct Check {
    static func main() async throws {
        URLProtocol.registerClass(FixtureProtocol.self)
        let dir = Backend.data.appendingPathComponent("cache")
        let store = ArtworkStore(directory: dir)
        async let first = store.fetchMissing(["0100DBF01000A000"])
        async let second = store.fetchMissing(["0100000000010000"])
        _ = await (first, second)
        precondition(ArtworkStore.cachedBanner("0100DBF01000A000", in: dir) != nil)
        precondition(ArtworkStore.cachedBanner("0100000000010000", in: dir) != nil)
        precondition(FixtureProtocol.count == 3)
        let named = await store.titleID(named: "GAME™")
        precondition(named == "0100DBF01000A000")
        let unknown = await store.titleID(named: "Not in the catalogue")
        precondition(unknown == nil)
        let reloaded = ArtworkStore(directory: dir)
        let cachedName = await reloaded.titleID(named: "game")
        precondition(cachedName == named && FixtureProtocol.count == 3)
        _ = await store.fetchMissing(["0100DBF01000A000", "0100000000020000"])
        precondition(FixtureProtocol.count == 3) // cache hit and rejected non-Nintendo URL
        precondition(ArtworkStore.cachedBanner("../outside", in: dir) == nil)
        FixtureProtocol.offline = true
        let offline = ArtworkStore(directory: Backend.data.appendingPathComponent("offline"))
        let result = await offline.fetchMissing(["0100DBF01000A000"])
        precondition(result.isEmpty)
        print("eShop lookup, selection, concurrent requests, cache and offline fallback passed")
    }
}
'''
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            runner = root / 'Check.swift'
            runner.write_text(harness)
            compile = subprocess.run(['xcrun', 'swiftc', '-module-cache-path', str(root / 'modules'), '-parse-as-library', str(source), str(runner), '-o', str(root / 'check')], capture_output=True, text=True)
            self.assertEqual(compile.returncode, 0, compile.stderr)
            result = subprocess.run([str(root / 'check'), folder], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
