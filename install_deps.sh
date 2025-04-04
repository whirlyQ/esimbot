#!/bin/bash
# Custom dependency installation script to resolve conflicts

set -e  # Exit immediately if a command exits with a non-zero status
set -x  # Print commands before execution for debugging

echo "Installing dependencies for eSIM Bot..."

# Update pip and setuptools
pip install --upgrade pip setuptools wheel

# Install dependencies from requirements.txt (which includes httpx==0.23.3)
pip install -r requirements.txt

# Manually download, unpack and install solana package
echo "Installing solana package directly from GitHub..."
mkdir -p /tmp/solana-py
curl -L https://github.com/michaelhly/solana-py/archive/refs/tags/v0.31.0.tar.gz | tar -xz -C /tmp/solana-py --strip-components=1
cd /tmp/solana-py

# Edit the pyproject.toml to fix the httpx dependency
sed -i 's/httpx>=0.23.0,<0.24.0/httpx==0.23.3/g' pyproject.toml

# Install the package
pip install -e .
cd -

# Verify installation
python -c "import solana; print(f'Successfully imported solana v{solana.__version__}')"

echo "Installation completed successfully!"
