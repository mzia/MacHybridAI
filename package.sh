#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"

APP_NAME="MacHybridAI"
VERSION="${MAC_HYBRID_VERSION:-$(tr -d '[:space:]' < "${PROJECT_DIR}/VERSION" 2>/dev/null || echo "1.1.0")}"
DIST_DIR="dist"
APP_BUNDLE="${APP_NAME}.app"

echo "==> [1/4] Building & Bundling ${APP_NAME} v${VERSION}..."
./bundle.sh

rm -rf "${DIST_DIR}"
mkdir -p "${DIST_DIR}"

echo "==> [2/4] Generating macOS Installer Package (.pkg)..."
PKG_FILE="${DIST_DIR}/${APP_NAME}-${VERSION}.pkg"
pkgbuild --install-location "/Applications" \
         --component "${APP_BUNDLE}" \
         --identifier "com.mzia.${APP_NAME}" \
         --version "${VERSION}" \
         "${PKG_FILE}"

cp "${PKG_FILE}" "${DIST_DIR}/${APP_NAME}-latest.pkg"
if [ "${VERSION}" != "1.0.0" ]; then
    cp "${PKG_FILE}" "${DIST_DIR}/${APP_NAME}-1.0.0.pkg"
fi
echo "    Created: ${PKG_FILE} & ${DIST_DIR}/${APP_NAME}-latest.pkg"

echo "==> [3/4] Generating Drag-and-Drop Disk Image (.dmg)..."
DMG_FILE="${DIST_DIR}/${APP_NAME}-${VERSION}.dmg"
DMG_STAGE="dmg_stage"

rm -rf "${DMG_STAGE}" "${DMG_FILE}"
mkdir -p "${DMG_STAGE}"

cp -R "${APP_BUNDLE}" "${DMG_STAGE}/"
ln -s /Applications "${DMG_STAGE}/Applications"

hdiutil create -volname "${APP_NAME}" \
               -srcfolder "${DMG_STAGE}" \
               -ov \
               -format UDZO \
               "${DMG_FILE}"

rm -rf "${DMG_STAGE}"
cp "${DMG_FILE}" "${DIST_DIR}/${APP_NAME}-latest.dmg"
if [ "${VERSION}" != "1.0.0" ]; then
    cp "${DMG_FILE}" "${DIST_DIR}/${APP_NAME}-1.0.0.dmg"
fi
echo "    Created: ${DMG_FILE} & ${DIST_DIR}/${APP_NAME}-latest.dmg"

echo "==> [4/4] Generating Zipped App Archive (.app.zip) & SHA-256 Checksums..."
ZIP_FILE="${DIST_DIR}/${APP_NAME}-${VERSION}-macos-arm64.app.zip"
ditto -c -k --sequesterRsrc --keepParent "${APP_BUNDLE}" "${ZIP_FILE}"
cp "${ZIP_FILE}" "${DIST_DIR}/${APP_NAME}-latest-macos-arm64.app.zip"

(
    cd "${DIST_DIR}"
    shasum -a 256 *.pkg *.dmg *.zip > SHA256SUMS.txt
)

echo "    Created: ${ZIP_FILE} & ${DIST_DIR}/SHA256SUMS.txt"
ls -lh "${DIST_DIR}"
