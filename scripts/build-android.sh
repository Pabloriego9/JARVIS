#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../apps/jarvis_app"
flutter pub get --enforce-lockfile
flutter analyze
flutter test
flutter build apk --debug --target-platform android-arm64
mkdir -p ../../artifacts
cp build/app/outputs/flutter-apk/app-debug.apk ../../artifacts/JARVIS-Android-arm64-debug.apk
