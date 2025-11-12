#!/bin/bash
# Installation script for dir-builder tools
# Supports both system-wide (root) and user-local installation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS=("dir-builder" "export-config")

echo "=========================================="
echo "dir-builder Installation"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    INSTALL_DIR="/usr/local/bin"
    INSTALL_TYPE="system-wide"
else
    INSTALL_DIR="${HOME}/bin"
    INSTALL_TYPE="user-local"
fi

# Allow override with command line argument
if [ -n "$1" ]; then
    INSTALL_DIR="$1"
    INSTALL_TYPE="custom"
fi

echo "Installation type: $INSTALL_TYPE"
echo "Install directory: $INSTALL_DIR"
echo ""

# Create install directory if it doesn't exist
if [ ! -d "$INSTALL_DIR" ]; then
    echo "Creating directory: $INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
fi

# Check if PyYAML is installed
echo "Checking Python dependencies..."
if ! python3 -c "import yaml" 2>/dev/null; then
    echo ""
    echo "⚠️  Warning: PyYAML is not installed"
    echo "    The scripts require PyYAML to run"
    echo ""
    echo "    Install with:"
    echo "    pip install pyyaml"
    echo "    or"
    echo "    pip3 install --user pyyaml"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 1
    fi
fi

echo ""
echo "Installing tools..."

for tool in "${TOOLS[@]}"; do
    TARGET="${INSTALL_DIR}/${tool}"
    
    echo "  Installing ${tool}..."
    
    # Create wrapper script
    cat > "$TARGET" <<EOF
#!/bin/bash
# Wrapper for ${tool}.py
exec python3 "${SCRIPT_DIR}/${tool}.py" "\$@"
EOF
    
    chmod +x "$TARGET"
    echo "    ✓ ${TARGET}"
done

echo ""
echo "=========================================="
echo "Installation complete!"
echo "=========================================="
echo ""

# Check if install directory is in PATH
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo "⚠️  Note: $INSTALL_DIR is not in your PATH"
    echo ""
    
    if [ "$INSTALL_TYPE" = "user-local" ]; then
        echo "Add this line to your ~/.bashrc:"
        echo ""
        echo "    export PATH=\"\$HOME/bin:\$PATH\""
        echo ""
        echo "Then reload your shell:"
        echo "    source ~/.bashrc"
    else
        echo "Add this directory to your PATH:"
        echo "    export PATH=\"$INSTALL_DIR:\$PATH\""
    fi
    echo ""
else
    echo "✓ Install directory is already in your PATH"
    echo ""
fi

echo "Installed tools:"
for tool in "${TOOLS[@]}"; do
    echo "  - ${tool}"
done

echo ""
echo "Usage examples:"
echo "  dir-builder config.yaml --dry-run"
echo "  export-config --bucket my-bucket -o output.yaml"
echo ""
echo "For more information:"
echo "  dir-builder --help"
echo "  export-config --help"
echo ""
