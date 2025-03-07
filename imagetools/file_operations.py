#!/usr/bin/env python3

# Copyright (C) 2025 Dustin Darcy <ScarcityHypothesis.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
file_operations.py

Functions for file operations, symlinks, copying, moving, and path handling.
Part of the refactored common_imagetools functionality.

Updates include:
- Improved filename collision handling with hierarchical resolution
- Filename registry to prevent any overwrites
- Enhanced logging for collision operations
"""

import os
import sys
import logging
import shutil
import hashlib
import platform
import subprocess
from datetime import datetime
from pathlib import Path

# Global constants
MAX_PATH_LENGTH = 250  # Default max path length to avoid OS limits

# -----------------------------
# Path Handling Functions
# -----------------------------
def create_safe_path(original_path, max_length=MAX_PATH_LENGTH, metadata=True):
    """
    Create a path that won't exceed OS limits.
    
    Args:
        original_path: The original path that might be too long
        max_length: Maximum allowed path length
        metadata: Whether to create a metadata file for shortened paths
    
    Returns:
        tuple: (safe_path, metadata_path) where metadata_path is None if not needed or metadata=False
    """
    if len(original_path) <= max_length:
        return original_path, None
        
    # Calculate how much we need to shorten
    excess = len(original_path) - max_length
    
    # Split into components
    dir_path, filename = os.path.split(original_path)
    name, ext = os.path.splitext(filename)
    
    # Shorten the name part
    shortened_name = name[:max(3, len(name)-excess-10)] + "_" + hashlib.md5(name.encode()).hexdigest()[:8]
    shortened_path = os.path.join(dir_path, shortened_name + ext)
    
    # Create metadata file path if requested
    metadata_path = None
    if metadata:
        metadata_path = os.path.join(dir_path, shortened_name + ".txt")
        
    return shortened_path, metadata_path

def write_metadata_file(metadata_path, original_path, additional_info=None):
    """Write metadata to a file for a shortened path."""
    try:
        # Make sure the directory exists
        os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            f.write(f"Original path: {original_path}\n")
            f.write(f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            if additional_info:
                for key, value in additional_info.items():
                    f.write(f"{key}: {value}\n")
        return True
    except Exception as e:
        logging.warning(f"Error writing metadata file {metadata_path}: {e}")
        return False

# -----------------------------
# Symlink and File Operations
# -----------------------------
def create_symlink(source, destination):
    """Create a symbolic link; if it fails, fallback to copying the file."""
    source = os.path.abspath(source)
    destination = os.path.abspath(destination)
    
    try:
        # Create parent directory if it doesn't exist
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        
        if os.path.exists(destination):
            os.remove(destination)
            
        if platform.system() == "Windows":
            # On Windows, try to create a symbolic link first
            try:
                os.symlink(source, destination)
                logging.debug(f"Created symbolic link: {destination} -> {source}")
            except OSError:
                # If that fails (e.g., no admin privileges), try creating a hard link
                try:
                    os.link(source, destination)
                    logging.debug(f"Created hard link: {destination} -> {source}")
                except OSError:
                    # If hard link also fails, fall back to copying
                    shutil.copy2(source, destination)
                    logging.warning(f"Created copy instead of link for {destination}")
        else:
            # Unix-like systems
            os.symlink(source, destination)
            logging.debug(f"Created symbolic link: {destination} -> {source}")
            
    except Exception as e:
        logging.error(f"Error creating link from {source} to {destination}: {e}")
        # Fall back to copying
        try:
            shutil.copy2(source, destination)
            logging.warning(f"Created copy instead of link for {destination}")
        except Exception as copy_error:
            logging.error(f"Error copying file: {copy_error}")
            raise

# Global registry to track filenames and prevent collisions
# This is a dictionary mapping directories to sets of filenames
# Example: { '/path/to/dir': {'file1.jpg', 'file2.png'} }
_filename_registry = {}

def get_unique_path(dest_path, source_path=None, collision_strategy="hierarchical"):
    """
    Generate a unique path that doesn't conflict with existing files.
    Uses a hierarchical approach to generate meaningful unique names.
    
    Args:
        dest_path: The destination path that might have a collision
        source_path: Original source path (for context in naming)
        collision_strategy: Strategy for resolving collisions
                           "hierarchical" (default): use parent dirs, then hash, then numeric
                           "hash": use hash of source path
                           "numeric": use incremental numbers
                           "parent_only": only use parent directory names
    
    Returns:
        A unique path that won't cause collisions
    """
    dest_dir, dest_filename = os.path.split(dest_path)
    name, ext = os.path.splitext(dest_filename)
    
    # Initialize the registry for this directory if needed
    if dest_dir not in _filename_registry:
        _filename_registry[dest_dir] = set()
        # If the directory exists, add all existing files to the registry
        if os.path.exists(dest_dir):
            for existing_file in os.listdir(dest_dir):
                if os.path.isfile(os.path.join(dest_dir, existing_file)):
                    _filename_registry[dest_dir].add(existing_file)
    
    # Check if the destination filename is already in use
    if dest_filename not in _filename_registry[dest_dir] and not os.path.exists(dest_path):
        # Add to registry and return original path
        _filename_registry[dest_dir].add(dest_filename)
        return dest_path
    
    # Need to create a unique name based on collision strategy
    if collision_strategy == "hierarchical" or collision_strategy == "parent_only":
        # First try: append parent directory name if source path provided
        if source_path:
            parent_dir = os.path.basename(os.path.dirname(source_path))
            parent_name = f"{name}_{parent_dir}{ext}"
            parent_path = os.path.join(dest_dir, parent_name)
            
            if parent_name not in _filename_registry[dest_dir] and not os.path.exists(parent_path):
                _filename_registry[dest_dir].add(parent_name)
                return parent_path
        
        # For parent_only strategy, move directly to numeric suffixes
        if collision_strategy == "parent_only":
            counter = 1
            while True:
                numeric_name = f"{name}_col_{counter}{ext}"
                numeric_path = os.path.join(dest_dir, numeric_name)
                
                if numeric_name not in _filename_registry[dest_dir] and not os.path.exists(numeric_path):
                    _filename_registry[dest_dir].add(numeric_name)
                    return numeric_path
                counter += 1
    
    # Second try: use hash of source path or fall back to "hash" strategy
    if collision_strategy == "hierarchical" or collision_strategy == "hash":
        if source_path:
            # Create a hash of the source path for uniqueness
            path_hash = hashlib.md5(source_path.encode()).hexdigest()[:8]
            hash_name = f"{name}_{path_hash}{ext}"
            hash_path = os.path.join(dest_dir, hash_name)
            
            if hash_name not in _filename_registry[dest_dir] and not os.path.exists(hash_path):
                _filename_registry[dest_dir].add(hash_name)
                return hash_path
    
    # Final fallback: use numeric suffixes for all strategies
    counter = 1
    while True:
        numeric_name = f"{name}_col_{counter}{ext}"
        numeric_path = os.path.join(dest_dir, numeric_name)
        
        if numeric_name not in _filename_registry[dest_dir] and not os.path.exists(numeric_path):
            _filename_registry[dest_dir].add(numeric_name)
            return numeric_path
        counter += 1

def handle_duplicate(source_path, dest_path, mode="copy", create_backlink=False, collision_strategy="hierarchical"):
    """
    Handle a duplicate file by resolving name collisions clearly.
    Uses a hierarchical approach for naming to avoid overwrites.

    Args:
        source_path: Path to the source file
        dest_path: Path where to place the file
        mode: "copy", "symlink", or "move"
        create_backlink: Create a link back to the new location if moving
        collision_strategy: Strategy for resolving name collisions
    """
    try:
        # Create destination directory if needed
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        # Get a unique destination path that won't cause collisions
        unique_dest_path = get_unique_path(dest_path, source_path, collision_strategy)
        
        # Log if path was changed due to collision
        if unique_dest_path != dest_path:
            logging.info(f"Filename collision: {os.path.basename(dest_path)} -> {os.path.basename(unique_dest_path)}")
        
        if mode == "copy":
            shutil.copy2(source_path, unique_dest_path)
            logging.debug(f"Copied {source_path} to {unique_dest_path}")
        elif mode == "symlink":
            create_symlink(source_path, unique_dest_path)
            logging.debug(f"Created symlink at {unique_dest_path} pointing to {source_path}")
        elif mode == "move":
            # Move the file
            shutil.move(source_path, unique_dest_path)
            logging.debug(f"Moved {source_path} to {unique_dest_path}")
            
            # Optionally create a link back to the new location
            if create_backlink:
                create_symlink(unique_dest_path, source_path)
                logging.debug(f"Created backlink at {source_path} pointing to {unique_dest_path}")
        else:
            raise ValueError(f"Unknown duplicate handling mode: {mode}")

        return unique_dest_path

    except Exception as e:
        logging.error(f"Error handling duplicate {source_path} -> {dest_path} (mode={mode}): {e}")
        raise

def is_symbolic_link(path):
    """Check if a path is a symbolic link, with platform-specific handling."""
    if platform.system() == "Windows":
        # On Windows, check for both symlinks and hardlinks
        try:
            return os.path.islink(path) or Path(path).is_symlink()
        except:
            # If checks fail, assume it's not a symlink
            return False
    else:
        # On Unix-like systems, simply use os.path.islink
        return os.path.islink(path)

def get_target_of_link(path):
    """Get the target of a symbolic link."""
    try:
        if is_symbolic_link(path):
            if platform.system() == "Windows":
                # Windows specific handling
                try:
                    return os.readlink(path)
                except:
                    # Fall back to pathlib
                    return str(Path(path).resolve())
            else:
                # Unix-like systems
                return os.readlink(path)
        return None
    except Exception as e:
        logging.warning(f"Error getting link target for {path}: {e}")
        return None

def reset_filename_registry():
    """Reset the filename registry, primarily for testing."""
    global _filename_registry
    _filename_registry = {}