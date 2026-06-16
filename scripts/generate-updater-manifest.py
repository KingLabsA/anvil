#!/usr/bin/env python3
"""
Generate Tauri updater manifest for GitHub releases.
Run this after creating a new release to generate latest.json.
"""

import json
import sys
import os
from pathlib import Path

def generate_manifest(version: str, notes: str, pub_date: str):
    """Generate the latest.json manifest for Tauri updater."""
    
    # Platform-specific download URLs and signatures
    # These would be generated during the build process
    platforms = {
        "darwin-aarch64": {
            "url": f"https://github.com/KingLabsA/anvil/releases/download/v{version}/Anvil-Desktop_{version}_aarch64.dmg",
            "signature": ""  # Would be filled during build
        },
        "darwin-x86_64": {
            "url": f"https://github.com/KingLabsA/anvil/releases/download/v{version}/Anvil-Desktop_{version}_x64.dmg",
            "signature": ""
        },
        "linux-x86_64": {
            "url": f"https://github.com/KingLabsA/anvil/releases/download/v{version}/anvil-desktop_{version}_amd64.AppImage",
            "signature": ""
        },
        "windows-x86_64": {
            "url": f"https://github.com/KingLabsA/anvil/releases/download/v{version}/Anvil-Desktop_{version}_x64_en-US.msi",
            "signature": ""
        }
    }
    
    manifest = {
        "version": version,
        "notes": notes,
        "pub_date": pub_date,
        "platforms": platforms
    }
    
    return manifest

def main():
    if len(sys.argv) < 2:
        print("Usage: generate-updater-manifest.py <version> [notes] [pub_date]")
        print("Example: generate-updater-manifest.py 0.4.0 'New features' '2026-06-15T12:00:00Z'")
        sys.exit(1)
    
    version = sys.argv[1]
    notes = sys.argv[2] if len(sys.argv) > 2 else "Bug fixes and improvements"
    pub_date = sys.argv[3] if len(sys.argv) > 3 else "2026-06-15T12:00:00Z"
    
    manifest = generate_manifest(version, notes, pub_date)
    
    # Write to latest.json
    output_path = Path("latest.json")
    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    print(f"Generated {output_path}")
    print(json.dumps(manifest, indent=2))

if __name__ == "__main__":
    main()
