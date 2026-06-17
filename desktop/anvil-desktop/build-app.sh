#!/bin/bash
set -e

echo "Building Tauri app..."
npx tauri build

APP="/tmp/anvil_gh/desktop/anvil-desktop/src-tauri/target/release/bundle/macos/Anvil Desktop.app"
SRC="/tmp/anvil_gh/desktop/anvil-desktop/src"

if [ -d "$APP" ]; then
  echo "Copying frontend files to app bundle..."
  mkdir -p "$APP/Contents/Resources"
  cp "$SRC/index.html" "$APP/Contents/Resources/"
  cp "$SRC/styles.css" "$APP/Contents/Resources/"
  cp "$SRC/app.js" "$APP/Contents/Resources/"
  echo "Done! App: $APP"
else
  echo "ERROR: App bundle not found"
  exit 1
fi
