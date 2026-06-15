#!/bin/bash
set -e

# Anvil Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/KingLabsA/anvil/main/install.sh | bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "  ___                      _____           _     "
echo " / _ \ _ __   ___ _ __    / ___| ___  ___| |__  "
echo "| | | | '_ \ / _ \ '_ \  | |  _ / _ \/ __| '_ \ "
echo "| |_| | |_) |  __/ | | | | |_| |  __/\__ \ | | |"
echo " \___/| .__/ \___|_| |_|  \____|\___|___/_| |_|"
echo "      |_|                                       "
echo -e "${NC}"
echo "The Self-Verified Coding Agent"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    echo "Please install Python 3.10 or higher first:"
    echo "  - macOS: brew install python"
    echo "  - Ubuntu/Debian: sudo apt install python3 python3-pip"
    echo "  - Windows: Download from python.org"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}Error: Python $REQUIRED_VERSION or higher is required (found $PYTHON_VERSION)${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python $PYTHON_VERSION detected${NC}"

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo -e "${YELLOW}Warning: pip3 not found, attempting to install...${NC}"
    python3 -m ensurepip --upgrade || {
        echo -e "${RED}Error: Failed to install pip${NC}"
        echo "Please install pip manually:"
        echo "  curl https://bootstrap.pypa.io/get-pip.py | python3"
        exit 1
    }
fi

echo -e "${GREEN}✓ pip detected${NC}"

# Ask about installation type
echo ""
echo "Select installation type:"
echo "  1) Minimal (core only)"
echo "  2) Standard (with web UI)"
echo "  3) Full (all features including local models)"
echo ""
read -p "Enter choice [1-3] (default: 2): " choice
choice=${choice:-2}

case $choice in
    1)
        EXTRAS=""
        echo -e "${BLUE}Installing minimal version...${NC}"
        ;;
    2)
        EXTRAS="[web]"
        echo -e "${BLUE}Installing standard version with web UI...${NC}"
        ;;
    3)
        EXTRAS="[all]"
        echo -e "${BLUE}Installing full version with all features...${NC}"
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

# Install Anvil
echo ""
echo "Installing Anvil..."
pip3 install --upgrade "fableforge-anvil-agent${EXTRAS}" || {
    echo -e "${RED}Error: Installation failed${NC}"
    echo "Try running with --user flag or use a virtual environment"
    exit 1
}

echo -e "${GREEN}✓ Anvil installed successfully${NC}"

# Verify installation
if ! command -v anvil &> /dev/null; then
    echo -e "${YELLOW}Warning: anvil command not found in PATH${NC}"
    echo "You may need to add ~/.local/bin to your PATH:"
    echo '  export PATH="$HOME/.local/bin:$PATH"'
    echo "Add this to your ~/.bashrc or ~/.zshrc"
fi

# Show next steps
echo ""
echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Test the installation:"
echo "     anvil --version"
echo ""
echo "  2. Run your first task:"
echo "     anvil run \"Create a hello world program\""
echo ""
echo "  3. Start the web UI:"
echo "     anvil serve"
echo "     Then open http://localhost:8000"
echo ""
echo "  4. Get help:"
echo "     anvil --help"
echo ""
echo "Documentation: https://github.com/KingLabsA/anvil"
echo ""
