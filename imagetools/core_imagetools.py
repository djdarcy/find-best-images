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
core_imagetools.py

Core functions for image discovery, validation, and basic operations.
Part of the refactored common_imagetools functionality.

Updates include:
- Pattern matching for include/exclude directories and files
- Support for glob and regex patterns
- Enhanced file discovery with pattern filtering
"""

import os
import sys
import logging
import re
import fnmatch
from pathlib import Path
import platform

from imagetools import (
    PILLOW_AVAILABLE, 
    DEFAULT_EXTENSIONS, 
    Image,
    FILE_FORMAT_QUALITY
)

# try:
#     from PIL import Image
#     PILLOW_AVAILABLE = True
# except ImportError:
#     PILLOW_AVAILABLE = False
    
# Try importing optional dependencies
from imagetools import TQDM_AVAILABLE, tqdm
    # Don't print anything here; let the main script handle it

# Global constants
# DEFAULT_EXTENSIONS = ['.bmp', '.jpg', '.jpeg', '.png', '.webp', '.gif', '.tiff', '.tif', '.jp2', '.heif', '.heic']
MAX_PATH_LENGTH = 250  # Default max path length to avoid OS limits

# File format quality rankings (higher number = better quality)
# FILE_FORMAT_QUALITY = {
#     '.png': 100,      # Lossless
#     '.tiff': 95,      # Lossless
#     '.tif': 95,       # Lossless
#     '.bmp': 90,       # Lossless
#     '.webp': 85,      # Can be lossless
#     '.jp2': 80,       # Better than JPEG
#     '.jpeg': 75,      # Lossy
#     '.jpg': 75,       # Lossy
#     '.heif': 77,      # Lossy but efficient
#     '.heic': 77,      # Lossy but efficient
#     '.gif': 60        # Limited colors
# }

def check_dependencies():
    """Check if required dependencies are available."""
    missing = []
    if not PILLOW_AVAILABLE:
        missing.append("PIL/Pillow")
    
    return missing

# -----------------------------
# Pattern Matching Functions
# -----------------------------
def matches_pattern(item, pattern, pattern_mode="glob"):
    """
    Check if an item matches a pattern.
    
    Args:
        item: The string to check
        pattern: The pattern to match against
        pattern_mode: "glob" or "regex"
        
    Returns:
        True if item matches pattern, False otherwise
    """
    if not pattern:
        return False
        
    try:
        if pattern_mode == "glob":
            return fnmatch.fnmatch(item, pattern)
        elif pattern_mode == "regex":
            return bool(re.search(pattern, item))
        else:
            # Default to glob
            return fnmatch.fnmatch(item, pattern)
    except Exception as e:
        logging.warning(f"Error matching pattern '{pattern}' with mode '{pattern_mode}': {e}")
        return False

def check_patterns(item, include_patterns=None, exclude_patterns=None, pattern_mode="glob"):
    """
    Check if an item matches any include patterns and doesn't match any exclude patterns.
    
    Args:
        item: The string to check
        include_patterns: List of patterns to include
        exclude_patterns: List of patterns to exclude
        pattern_mode: "glob" or "regex"
        
    Returns:
        True if item should be included, False otherwise
    """
    # If no include patterns, include everything by default
    # If include patterns exist, at least one must match
    include_match = not include_patterns or any(matches_pattern(item, p, pattern_mode) for p in include_patterns)
    
    # If exclude patterns exist, none must match
    exclude_match = exclude_patterns and any(matches_pattern(item, p, pattern_mode) for p in exclude_patterns)
    
    # Include if it matches include patterns and doesn't match exclude patterns
    return include_match and not exclude_match

# -----------------------------
# Image Discovery and Validation
# -----------------------------
def is_valid_image(file_path, min_file_size=0, extensions=None):
    """Check if the file is a valid image based on extension and file size."""
    if not PILLOW_AVAILABLE:
        raise ImportError("PIL/Pillow is required for image processing")
        
    if extensions is None:
        extensions = DEFAULT_EXTENSIONS
    
    # Normalize extensions to have leading dots and be lowercase
    extensions = [ext.lower() if ext.startswith('.') else f'.{ext.lower()}' for ext in extensions]
    
    file_ext = os.path.splitext(file_path)[1].lower()
    if file_ext not in extensions:
        return False
    if min_file_size > 0 and os.path.getsize(file_path) < min_file_size * 1024:
        return False
    try:
        with Image.open(file_path) as img:
            img.verify()
        return True
    except Exception:
        return False

def find_images(input_dirs, exclude_dirs=None, recursive=True, follow_symlinks=False,
                min_file_size=0, extensions=None, logger=None, show_progress=True,
                include_dirs_pattern=None, include_files_pattern=None,
                exclude_dirs_pattern=None, exclude_files_pattern=None,
                pattern_mode="glob"):
    """
    Traverse directories to find valid images with pattern filtering.
    
    Args:
        input_dirs: List of directories to search
        exclude_dirs: List of directories to exclude
        recursive: Whether to search recursively
        follow_symlinks: Whether to follow symbolic links
        min_file_size: Minimum file size in KB
        extensions: List of file extensions to include
        logger: Logger instance
        show_progress: Whether to show progress bar
        include_dirs_pattern: List of patterns to include directories
        include_files_pattern: List of patterns to include files
        exclude_dirs_pattern: List of patterns to exclude directories
        exclude_files_pattern: List of patterns to exclude files
        pattern_mode: "glob" or "regex"
        
    Returns:
        List of valid image paths
    """
    if not PILLOW_AVAILABLE:
        raise ImportError("PIL/Pillow is required for image processing")
        
    if logger is None:
        logger = logging.getLogger("core_imagetools")
    if exclude_dirs is None:
        exclude_dirs = []
    exclude_dirs = [os.path.abspath(d) for d in exclude_dirs]
    if extensions is None:
        extensions = DEFAULT_EXTENSIONS

    all_images = []
    total_dirs = len(input_dirs)
    
    # Ensure input_dirs is a list
    if isinstance(input_dirs, str):
        input_dirs = [input_dirs]
    
    for dir_idx, input_dir in enumerate(input_dirs):
        input_dir = os.path.abspath(input_dir)
        logger.info(f"Scanning directory [{dir_idx+1}/{total_dirs}]: {input_dir}")
        
        if not os.path.exists(input_dir):
            logger.warning(f"Input directory does not exist: {input_dir}")
            continue
            
        if not os.path.isdir(input_dir):
            logger.warning(f"Not a directory: {input_dir}")
            continue
        
        # Process walk parameters based on Python version
        walk_kwargs = {}
        if recursive and follow_symlinks:
            walk_kwargs['followlinks'] = True
            
        for root, dirs, files in os.walk(input_dir, **walk_kwargs):
            # Check if the current directory should be excluded
            if any(os.path.abspath(root).startswith(ed) for ed in exclude_dirs):
                logger.debug(f"Skipping excluded directory: {root}")
                continue
            
            # Check directory against patterns
            dir_name = os.path.basename(root)
            if not check_patterns(dir_name, include_dirs_pattern, exclude_dirs_pattern, pattern_mode):
                logger.debug(f"Skipping directory {root} due to pattern filtering")
                continue
                
            if recursive:
                # Filter out excluded directories in-place
                dirs[:] = [d for d in dirs if 
                          (not any(os.path.abspath(os.path.join(root, d)).startswith(ed) for ed in exclude_dirs) and
                           check_patterns(d, include_dirs_pattern, exclude_dirs_pattern, pattern_mode))]
            
            valid_images = []
            for file in files:
                # Check file against patterns
                if not check_patterns(file, include_files_pattern, exclude_files_pattern, pattern_mode):
                    continue
                    
                file_path = os.path.join(root, file)
                try:
                    if is_valid_image(file_path, min_file_size, extensions):
                        valid_images.append(file_path)
                except Exception as e:
                    logger.debug(f"Error processing {file_path}: {e}")
            
            all_images.extend(valid_images)
            
            if not recursive:
                break  # Don't process subdirectories if not recursive
    
    logger.info(f"Found {len(all_images)} valid images")
    return all_images

def get_image_dimensions(image_path):
    """Return the width and height of the image."""
    if not PILLOW_AVAILABLE:
        raise ImportError("PIL/Pillow is required for image processing")
        
    try:
        with Image.open(image_path) as img:
            return img.size
    except Exception as e:
        logging.warning(f"Error getting dimensions for {image_path}: {e}")
        return (0, 0)

def get_image_resolution(image_path):
    """Get the total resolution (width * height) of an image."""
    try:
        width, height = get_image_dimensions(image_path)
        return width * height
    except Exception as e:
        logging.warning(f"Error calculating resolution for {image_path}: {e}")
        return 0