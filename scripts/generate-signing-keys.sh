#!/bin/bash
# Generate Tauri updater signing keys
# Run this once and save the keys as GitHub secrets

set -e

echo "Generating Tauri updater signing keys..."
echo ""

# Check if tauri CLI is installed
if ! command -v cargo &> /dev/null; then
    echo "Error: cargo is not installed. Please install Rust first."
    exit 1
fi

# Install tauri-cli if not present
if ! cargo tauri --version &> /dev/null; then
    echo "Installing tauri-cli..."
    cargo install tauri-cli --version "^2.0.0"
fi

# Generate keys
echo "Generating signing keys..."
cargo tauri signer generate -w ~/.tauri/anvil.key

echo ""
echo "Keys generated successfully!"
echo ""
echo "Private key location: ~/.tauri/anvil.key"
echo ""
echo "Next steps:"
echo "1. Read the public key:"
cat ~/.tauri/anvil.key.pub
echo ""
echo ""
echo "2. Add to GitHub repository secrets:"
echo "   - TAURI_PRIVATE_KEY: Contents of ~/.tauri/anvil.key"
echo "   - TAURI_KEY_PASSWORD: Password you set during generation"
echo ""
echo "3. Add to tauri.conf.json plugins.updater.pubkey:"
echo "   $(cat ~/.tauri/anvil.key.pub)"
echo ""
echo "⚠️  IMPORTANT: Keep the private key secure! Never commit it to the repository."
