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
__init__.py

Export all public functions from the imagetools package.
"""
import sys
import os

# Ensure this package is correctly recognized
# __package__ = "imagetools"

# print(f"DEBUG: imagetools/__init__.py loaded, __package__ = {__package__}")

# print(f"DEBUG: Loading imagetools, sys.path = {sys.path}")
# print(f"DEBUG: imagetools package found at {os.path.dirname(os.path.abspath(__file__))}")

# Export version info
__version__ = '0.4.0'

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

try:
    import torch
    from transformers import CLIPProcessor, CLIPModel
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

# Constants defined centrally
DEFAULT_EXTENSIONS = ['.bmp', '.jpg', '.jpeg', '.png', '.webp', '.gif', '.tiff', '.tif', '.jp2', '.heif', '.heic']

# File format quality rankings (higher number = better quality)
FILE_FORMAT_QUALITY = {
    '.png': 100,      # Lossless
    '.tiff': 95,      # Lossless
    '.tif': 95,       # Lossless
    '.bmp': 90,       # Lossless
    '.webp': 85,      # Can be lossless
    '.jp2': 80,       # Better than JPEG
    '.jpeg': 75,      # Lossy
    '.jpg': 75,       # Lossy
    '.heif': 77,      # Lossy but efficient
    '.heic': 77,      # Lossy but efficient
    '.gif': 60        # Limited colors
}

# Import and re-export similarity presets
from imagetools.similarity_tools import SIMILARITY_PRESETS

# Core image tools
from imagetools.core_imagetools import (
    check_dependencies,
    is_valid_image,
    find_images,
    get_image_dimensions,
    get_image_resolution
)

# Similarity tools
from imagetools.similarity_tools import (
    load_clip_model,
    compute_embedding,
    compute_embeddings_batch,
    extract_image_region,
    compute_region_similarity,
    cosine_similarity,
    group_similar_images,
    save_cache,
    load_cache,
    get_similarity_threshold
)

# Quality metrics
from imagetools.quality_metrics import (
    get_image_filesize,
    get_image_modified_time,
    get_image_created_time,
    get_image_quality,
    find_best_image,
    find_best_image_weighted,
    find_best_image_hybrid,
    get_metric_overrides,
    DEFAULT_METRIC_WEIGHTS
)

# File operations
from imagetools.file_operations import (
    create_safe_path,
    write_metadata_file,
    create_symlink,
    handle_duplicate,
    is_symbolic_link,
    get_target_of_link,
    get_unique_path,
    reset_filename_registry
)

# Directory structure
from imagetools.directory_structure import (
    create_output_structure,
    handle_singletons,
    collect_best_images
)

# Import utilities for easy access
import logging

def setup_logging(level=logging.INFO, log_file=None):
    """Configure logging for the imagetools package."""
    if log_file:
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            filename=log_file,
            filemode='w'
        )
        # Also log to console
        console = logging.StreamHandler()
        console.setLevel(level)
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)
    else:
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    return logging.getLogger('imagetools')