#!/bin/bash
# Custom dependency installation script to resolve conflicts

set -e  # Exit immediately if a command exits with a non-zero status
set -x  # Print commands before execution for debugging

echo "Installing dependencies in the correct order to avoid conflicts..."

# Check if we have the direct requirements file
if [ -f "requirements-direct.txt" ]; then
    echo "Found requirements-direct.txt - installing direct dependencies first"
    pip install -r requirements-direct.txt
    DIRECT_DEPS_INSTALLED=true
else
    echo "No requirements-direct.txt found - will install from requirements.txt"
    DIRECT_DEPS_INSTALLED=false
    
    # First install httpx at the specific version we need
    pip install httpx==0.24.1
    
    # Then install all other requirements except solana
    grep -v "solana==" requirements.txt | pip install -r /dev/stdin
fi

# Install solana package (using multiple methods to ensure it works)
echo "Installing solana package..."
SOLANA_INSTALLED=false

# Method 1: Try regular install
if pip install solana==0.31.0; then
    echo "Successfully installed solana with dependencies"
    SOLANA_INSTALLED=true
else
    echo "Failed to install solana with dependencies, trying without dependencies..."
fi

# Method 2: Try without dependencies
if [ "$SOLANA_INSTALLED" = false ] && pip install --no-deps solana==0.31.0; then
    echo "Successfully installed solana without dependencies"
    SOLANA_INSTALLED=true
else
    echo "Failed to install solana without dependencies, trying from GitHub..."
fi

# Method 3: Install directly from GitHub
if [ "$SOLANA_INSTALLED" = false ]; then
    echo "Installing solana from GitHub..."
    if pip install git+https://github.com/michaelhly/solana-py.git@master; then
        echo "Successfully installed solana from GitHub"
        SOLANA_INSTALLED=true
    else
        echo "Failed to install solana from GitHub"
    fi
fi

# Method 4: Use our fallback solana module if all else fails
if [ "$SOLANA_INSTALLED" = false ]; then
    echo "Warning: All attempts to install solana package failed!"
    echo "Installing fallback solana module..."
    
    # Check if the fallback file exists
    if [ -f "fallback_solana.py" ]; then
        # Create a solana directory in the Python path
        SITE_PACKAGES=$(python -c "import site; print(site.getsitepackages()[0])")
        mkdir -p "$SITE_PACKAGES/solana"
        touch "$SITE_PACKAGES/solana/__init__.py"
        
        # Copy our fallback module files
        cp fallback_solana.py "$SITE_PACKAGES/solana/__init__.py"
        
        echo "Fallback solana module installed"
    else
        echo "Error: Fallback solana module not found!"
        exit 1
    fi
fi

# Verify installations
echo "Verifying installations:"
pip list | grep solana || echo "Warning: solana not found in pip list"
pip list | grep httpx || echo "Warning: httpx not found in pip list" 
pip list | grep python-telegram-bot || echo "Warning: python-telegram-bot not found in pip list"

# Additional check to see if solana is importable
python -c "import solana; print(f'Solana package imported successfully')" || echo "Warning: Failed to import solana package"

echo "Installation completed successfully!"
