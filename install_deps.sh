#!/bin/bash
# Custom dependency installation script to resolve conflicts

set -e  # Exit immediately if a command exits with a non-zero status
set -x  # Print commands before execution for debugging

echo "Installing dependencies for eSIM Bot..."

# Update pip and setuptools
pip install --upgrade pip setuptools wheel

# Install correct version of httpx for solana
echo "Installing httpx compatible with solana..."
pip install httpx==0.23.3

# Install base dependencies
echo "Installing base dependencies..."
pip install python-dotenv==1.0.1 requests==2.31.0 aiohttp==3.9.3 certifi==2024.2.2 solders==0.19.0 base58==2.1.1

# Install solana without dependencies
echo "Installing solana without dependencies..."
pip install --no-deps solana==0.31.0

# Verify solana installation
python -c "import solana; print('Successfully imported solana')"

# Upgrade httpx for python-telegram-bot
echo "Upgrading httpx for python-telegram-bot..."
pip install --upgrade httpx~=0.26.0

# Install python-telegram-bot
echo "Installing python-telegram-bot..."
pip install python-telegram-bot==20.8

# Show final package versions
echo "Final package versions:"
pip list | grep httpx
pip list | grep solana
pip list | grep python-telegram-bot

echo "Installation completed successfully!"
