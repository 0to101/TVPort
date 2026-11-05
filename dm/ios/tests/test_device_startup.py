"""Exercise the production boot check with simulated GPUs, without a device or game files."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]


@unittest.skipUnless(sys.platform == 'darwin', 'Foundation required')
class DeviceStartup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        root = Path(cls.temp.name)
        main = (REPO / 'dm/ios/Sources/main.m').read_text()
        check = main[main.index('const char *front_ios_device_check(void)'):main.index('static void romfs_identity_report')]
        source = root / 'device.m'
        source.write_text('''#import <Foundation/Foundation.h>
#include <stdio.h>
#include <string.h>
#undef TARGET_OS_TV
#define TARGET_OS_TV TEST_TV
@protocol MTLDevice
@property(readonly) BOOL supportsBCTextureCompression;
@property(readonly) NSString *name;
@end
static BOOL hasBC, absent;
static int creations;
@interface FakeGPU : NSObject <MTLDevice>
@end
@implementation FakeGPU
- (BOOL)supportsBCTextureCompression { return hasBC; }
- (NSString *)name { return @"Fixture GPU"; }
@end
static id<MTLDevice> MTLCreateSystemDefaultDevice(void) {
    creations++;
    return absent ? nil : [FakeGPU new];
}
''' + check + '''
int main(int argc, char **argv) { @autoreleasepool {
    if (argc != 2) return 2;
    hasBC = !strcmp(argv[1], "bc"); absent = !strcmp(argv[1], "absent");
    const char *first = front_ios_device_check();
    const char *second = front_ios_device_check();
    if (creations != 1 || first != second) return 3;
    puts(first ? first : "supported");
    return 0;
}}
''')
        cls.executables = {}
        for platform, tv in [('ios', 0), ('tvos', 1)]:
            executable = root / platform
            subprocess.run(['clang', '-fobjc-arc', '-Wall', '-Werror', f'-DTEST_TV={tv}',
                            str(source), '-framework', 'Foundation', '-o', str(executable)], check=True)
            cls.executables[platform] = executable

    def check_gpu(self, platform, gpu):
        result = subprocess.run([str(self.executables[platform]), gpu], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip(), result.stderr

    def test_apple_tv_without_bc_uses_decoder(self):
        message, log = self.check_gpu('tvos', 'no-bc')
        self.assertEqual(message, 'supported')
        self.assertIn("using TVPort's texture decoder", log)
        self.assertNotIn('[RED]', log)

    def test_ios_without_bc_still_refuses(self):
        message, log = self.check_gpu('ios', 'no-bc')
        self.assertIn('cannot read BC-compressed textures', message)
        self.assertIn('[RED]', log)

    def test_hardware_bc_is_supported_on_both_platforms(self):
        for platform in self.executables:
            with self.subTest(platform=platform):
                self.assertEqual(self.check_gpu(platform, 'bc'), ('supported', ''))

    def test_missing_metal_is_refused_on_both_platforms(self):
        for platform in self.executables:
            with self.subTest(platform=platform):
                message, log = self.check_gpu(platform, 'absent')
                self.assertEqual(message, 'No Metal GPU is available on this device.')
                self.assertIn('[RED]', log)


if __name__ == '__main__':
    unittest.main()
