#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"

APP_NAME="MacHybridAI"
BUILD_DIR=".build/release"
APP_BUNDLE="${APP_NAME}.app"
CONTENTS_DIR="${APP_BUNDLE}/Contents"
MACOS_DIR="${CONTENTS_DIR}/MacOS"
RESOURCES_DIR="${CONTENTS_DIR}/Resources"
BACKEND_DEST="${RESOURCES_DIR}/backend"

echo "==> [1/4] Building ${APP_NAME} in release mode..."
swift build -c release

echo "==> [2/4] Creating macOS App Bundle (${APP_BUNDLE})..."
rm -rf "${APP_BUNDLE}"
mkdir -p "${MACOS_DIR}" "${RESOURCES_DIR}"

cp "${BUILD_DIR}/${APP_NAME}" "${MACOS_DIR}/${APP_NAME}"
chmod +x "${MACOS_DIR}/${APP_NAME}"

echo "==> [3/5] Generating custom MacHybridAI Split-Compute AppIcon.icns..."
mkdir -p "${PROJECT_DIR}/build"
swift "${PROJECT_DIR}/scripts/generate_app_icon.swift" "${PROJECT_DIR}/build/AppIcon.iconset" || true
if [ -d "${PROJECT_DIR}/build/AppIcon.iconset" ]; then
    iconutil -c icns "${PROJECT_DIR}/build/AppIcon.iconset" -o "${RESOURCES_DIR}/AppIcon.icns" || true
fi

echo "==> [4/5] Bundling Python Hybrid Compute & Antigravity Engine..."
mkdir -p "${BACKEND_DEST}"
cp -R "${PROJECT_DIR}/backend/machybrid" "${BACKEND_DEST}/"
cp "${PROJECT_DIR}/backend/pyproject.toml" "${BACKEND_DEST}/"

cat <<EOF > "${CONTENTS_DIR}/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>${APP_NAME}</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.mzia.${APP_NAME}</string>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>14.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

echo "==> [5/5] Ad-hoc signing ${APP_BUNDLE}..."
codesign --force --deep --sign - -r='designated => identifier "com.mzia.MacHybridAI"' "${APP_BUNDLE}" 2>/dev/null || codesign --force --deep --sign - "${APP_BUNDLE}" 2>/dev/null || true

echo "=================================================================="
echo " Successfully packaged self-contained ${APP_BUNDLE}!"
echo "=================================================================="
