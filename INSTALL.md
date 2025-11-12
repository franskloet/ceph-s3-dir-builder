# Installation Guide

## Quick Install

The easiest way to install dir-builder tools:

```bash
./install.sh
```

This installs to `~/bin` (no root required).

## Installation Options

### 1. User Install (Recommended)
No root access needed, installs to `~/bin`:

```bash
./install.sh
```

If `~/bin` is not in your PATH, add to `~/.bashrc`:
```bash
export PATH="$HOME/bin:$PATH"
```

Then reload:
```bash
source ~/.bashrc
```

### 2. System-Wide Install
Requires root, installs to `/usr/local/bin`:

```bash
sudo ./install.sh
```

### 3. Custom Location
Specify any directory:

```bash
./install.sh /path/to/custom/dir
```

## What Gets Installed

The install script creates wrapper commands:
- `dir-builder` - Apply IAM configurations
- `export-config` - Export existing IAM to YAML

Both are lightweight wrappers that call the Python scripts.

## Dependencies

### Required
- Python 3.7+
- PyYAML: `pip install pyyaml` or `pip3 install --user pyyaml`
- AWS CLI configured
- [aws-tools](../aws-tools) installed

The install script will check for PyYAML and warn if missing.

### Installing PyYAML

**User install (no root):**
```bash
pip3 install --user pyyaml
```

**System-wide:**
```bash
sudo pip3 install pyyaml
```

**Or use your package manager:**
```bash
# AlmaLinux/RHEL/CentOS
sudo dnf install python3-pyyaml

# Debian/Ubuntu
sudo apt install python3-yaml
```

## Verification

After installation, verify:

```bash
# Check commands are available
which dir-builder
which export-config

# Test help
dir-builder --help
export-config --help

# Test with example
dir-builder example-simple.yaml --print-tree
```

## Usage After Installation

No need for `.py` extension or `./` prefix:

```bash
# Before installation
./dir-builder.py config.yaml --dry-run

# After installation
dir-builder config.yaml --dry-run
```

## Uninstallation

### User Install
```bash
rm ~/bin/dir-builder ~/bin/export-config
```

### System-Wide Install
```bash
sudo rm /usr/local/bin/dir-builder /usr/local/bin/export-config
```

### Custom Install
```bash
rm /path/to/custom/dir/dir-builder /path/to/custom/dir/export-config
```

## Troubleshooting

### "command not found"
Install directory not in PATH. Add to `~/.bashrc`:
```bash
export PATH="$HOME/bin:$PATH"
```

### "PyYAML not installed"
Install with:
```bash
pip3 install --user pyyaml
```

### Permission denied
For user install, no root needed. If getting permission errors:
```bash
# Make install script executable
chmod +x install.sh

# Run without sudo
./install.sh
```

### Commands point to wrong location
The wrapper scripts reference the original script location. If you move the `dir-builder/` directory, reinstall:
```bash
cd /new/location/dir-builder
./install.sh
```

## Development Install

If you're actively developing, you may prefer to use the Python scripts directly:

```bash
# Make executable
chmod +x dir-builder.py export-config.py

# Run directly
./dir-builder.py config.yaml
./export-config.py --bucket my-bucket
```

Or create symlinks:
```bash
ln -s "$(pwd)/dir-builder.py" ~/bin/dir-builder
ln -s "$(pwd)/export-config.py" ~/bin/export-config
```

## Integration with aws-tools

dir-builder requires aws-tools to be installed. If not already done:

```bash
cd /path/to/aws-tools
./install.sh ~/s3/AWS
source ~/.bashrc
```

See [aws-tools README](../aws-tools/README.md) for details.

## Next Steps

After installation:
1. Read [QUICKSTART.md](QUICKSTART.md) for basic usage
2. See [README.md](README.md) for full documentation
3. Try examples: `dir-builder example-simple.yaml --print-tree`
4. Export existing setup: `export-config --bucket my-bucket`
