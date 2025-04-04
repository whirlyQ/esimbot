#!/bin/bash
# Custom dependency installation script to resolve conflicts

set -e  # Exit immediately if a command exits with a non-zero status
set -x  # Print commands before execution for debugging

echo "Installing dependencies for eSIM Bot..."

# Update pip and setuptools
pip install --upgrade pip setuptools wheel

# First install all dependencies EXCEPT python-telegram-bot
echo "Installing base dependencies..."
pip install python-dotenv==1.0.1 requests==2.31.0 aiohttp==3.9.3 certifi==2024.2.2 solders==0.19.0 base58==2.1.1

# Install solana with specific httpx version
echo "Installing httpx compatible with solana..."
pip install httpx==0.23.3

# Manually download and install solana package
echo "Installing solana package directly from GitHub..."
mkdir -p /tmp/solana-py
curl -L https://github.com/michaelhly/solana-py/archive/refs/tags/v0.31.0.tar.gz | tar -xz -C /tmp/solana-py --strip-components=1
cd /tmp/solana-py

# Edit the pyproject.toml to fix the httpx dependency
sed -i 's/httpx>=0.23.0,<0.24.0/httpx==0.23.3/g' pyproject.toml

# Install the package
pip install -e .
cd -

# Verify solana installation
python -c "import solana; print(f'Successfully imported solana v{solana.__version__}')"

# Now upgrade httpx to the version needed by python-telegram-bot
echo "Upgrading httpx for python-telegram-bot..."
pip install --upgrade httpx~=0.26.0

# Finally install python-telegram-bot
echo "Installing python-telegram-bot..."
pip install python-telegram-bot==20.8

# Show final package versions
echo "Final package versions:"
pip list | grep httpx
pip list | grep solana
pip list | grep python-telegram-bot

echo "Installation completed successfully!"
