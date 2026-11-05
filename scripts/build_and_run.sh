#!/usr/bin/env bash
set -euo pipefail
MODE="${1:-run}"
case "$MODE" in run|--verify|--debug|--logs|--telemetry) ;; *) echo "usage: $0 [--verify|--debug|--logs|--telemetry]" >&2; exit 2 ;; esac
TVPORT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$TVPORT_ROOT"
pkill -x TVPort >/dev/null 2>&1 || true
xcodegen generate --spec tvport/app/project.yml
xcodebuild -project tvport/app/TVPort.xcodeproj -scheme TVPort -configuration Debug -derivedDataPath tvport/app/build build
TVPORT_APP="$TVPORT_ROOT/tvport/app/build/Build/Products/Debug/TVPort.app"
if [[ "$MODE" == --debug ]]; then
    exec lldb -- "$TVPORT_APP/Contents/MacOS/TVPort"
fi
open -n "$TVPORT_APP"
case "$MODE" in
    --verify) sleep 1; pgrep -f "$TVPORT_APP/Contents/MacOS/TVPort" >/dev/null ;;
    --logs) exec /usr/bin/log stream --info --style compact --predicate 'process == "TVPort"' ;;
    --telemetry) exec /usr/bin/log stream --info --style compact --predicate 'subsystem == "dev.tvport.mac"' ;;
esac
