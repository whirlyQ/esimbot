#!/usr/bin/env python
"""
Setup script for fallback Solana modules.
This script checks if the required Solana packages are installed,
and if not, installs fallback implementations from the fallback_modules directory.
"""

import os
import sys
import shutil
import logging
import importlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_site_packages_dir():
    """Get the site-packages directory."""
    import site
    return site.getsitepackages()[0]

def check_module_exists(module_name):
    """Check if a module exists."""
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False

def setup_fallback_modules():
    """Set up fallback modules for solana-related packages."""
    logger.info("Checking for required Solana packages...")
    
    # Check if the solana package exists
    solana_exists = check_module_exists('solana')
    solders_exists = check_module_exists('solders')
    
    if solana_exists and solders_exists:
        logger.info("All required Solana packages are installed.")
        return
    
    # Install fallback modules
    site_packages = get_site_packages_dir()
    logger.info(f"Installing fallback modules to {site_packages}...")
    
    # Create directories if they don't exist
    if not solana_exists:
        os.makedirs(os.path.join(site_packages, 'solana', 'rpc'), exist_ok=True)
        logger.info("Created solana directory structure")
        
    if not solders_exists:
        os.makedirs(os.path.join(site_packages, 'solders'), exist_ok=True)
        logger.info("Created solders directory structure")
    
    # Copy fallback modules
    fallback_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'fallback_modules')
    
    if os.path.exists(fallback_dir):
        # Copy solana modules if needed
        if not solana_exists:
            solana_src = os.path.join(fallback_dir, 'solana')
            solana_dst = os.path.join(site_packages, 'solana')
            
            # Copy all files from solana directory
            for root, dirs, files in os.walk(solana_src):
                # Get the relative path from solana_src to the current directory
                rel_path = os.path.relpath(root, solana_src)
                
                # Create the corresponding directory in the destination
                if rel_path != '.':
                    os.makedirs(os.path.join(solana_dst, rel_path), exist_ok=True)
                
                # Copy all files in this directory
                for file in files:
                    src_file = os.path.join(root, file)
                    dst_file = os.path.join(solana_dst, rel_path, file)
                    shutil.copy2(src_file, dst_file)
                    logger.info(f"Copied {src_file} to {dst_file}")
        
        # Copy solders modules if needed
        if not solders_exists:
            solders_src = os.path.join(fallback_dir, 'solders')
            solders_dst = os.path.join(site_packages, 'solders')
            
            # Copy all files from solders directory
            for root, dirs, files in os.walk(solders_src):
                # Get the relative path from solders_src to the current directory
                rel_path = os.path.relpath(root, solders_src)
                
                # Create the corresponding directory in the destination
                if rel_path != '.':
                    os.makedirs(os.path.join(solders_dst, rel_path), exist_ok=True)
                
                # Copy all files in this directory
                for file in files:
                    src_file = os.path.join(root, file)
                    dst_file = os.path.join(solders_dst, rel_path, file)
                    shutil.copy2(src_file, dst_file)
                    logger.info(f"Copied {src_file} to {dst_file}")
        
        logger.info("Fallback modules installed successfully.")
    else:
        logger.error(f"Fallback directory {fallback_dir} not found!")
        sys.exit(1)
    
    # Verify the installation
    verify_solana = check_module_exists('solana')
    verify_solders = check_module_exists('solders')
    
    if verify_solana and verify_solders:
        logger.info("Verification successful: All modules can now be imported.")
    else:
        logger.error(f"Verification failed: solana={verify_solana}, solders={verify_solders}")
        sys.exit(1)

if __name__ == "__main__":
    setup_fallback_modules()
