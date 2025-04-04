#!/bin/bash
# Custom dependency installation script to resolve conflicts

echo "Installing dependencies in the correct order to avoid conflicts..."

# First install httpx at the specific version we need
pip install httpx==0.24.1

# Then install all other requirements except solana
grep -v "solana==" requirements.txt | pip install -r /dev/stdin

# Finally install solana with --no-deps to avoid dependency conflicts
pip install --no-deps solana==0.31.0

echo "Installation completed successfully!"
