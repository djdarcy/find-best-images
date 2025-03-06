#!/usr/bin/env python3
"""
directory_structure.py

Functions for creating and managing output directory structures.
Part of the refactored common_imagetools functionality.

Updates include:
- Support for hybrid quality metrics (ordered primary + weighted secondary)
- Enhanced collision handling with multiple strategies
- Date preference configuration for quality metrics
- Improved logging and error handling
"""

import os
import sys
import logging
import shutil
from pathlib import Path

from imagetools import TQDM_AVAILABLE, tqdm

# Import from our modules
from .core_imagetools import get_image_dimensions
from .quality_metrics import find_best_image_hybrid, get_metric_overrides
from .file_operations import (
    create_safe_path, write_metadata_file, handle_duplicate, 
    create_symlink, reset_filename_registry
)

# -----------------------------
# Output Directory Structure
# -----------------------------
def create_output_structure(similar_groups, output_dir, primary_metrics=None, secondary_metrics=None,
                           metric_weights=None, date_preference="newest", metric_overrides=None, 
                           naming_pattern="{filename}_{width}x{height}_candidates",
                           file_handling="symlink", copy_best=False, suffix="_candidates",
                           handle_long_paths=True, max_path_length=250,
                           include_singletons=True, singletons_subdir="_singletons_",
                           collision_strategy="hierarchical", dryrun=False, create_backlinks=False,
                           logger=None, show_progress=True):
    """
    Create directories for each group.
    For each group, create a main folder for the best image and a candidate subfolder for all images.
    
    Args:
        similar_groups: List of image groups (each group is a set of image paths)
        output_dir: Base output directory
        primary_metrics: List of primary metrics for determining best image, in priority order
        secondary_metrics: List of secondary metrics for weighted tie-breaking
        metric_weights: Dictionary mapping metrics to their weights (for secondary metrics)
        date_preference: Preference for date metrics ("newest" or "oldest")
        metric_overrides: Dictionary of per-metric preference overrides
        naming_pattern: Pattern for output directory names
        file_handling: How to handle files - "symlink", "copy", or "move"
        copy_best: Always copy best image, regardless of file_handling mode
        suffix: Suffix for candidate directories
        handle_long_paths: Whether to handle long paths
        max_path_length: Maximum allowed path length
        include_singletons: Whether to include singleton images
        singletons_subdir: Subdirectory name for singleton images
        collision_strategy: Strategy for resolving filename collisions
        dryrun: Don't actually create any files/directories
        create_backlinks: Create symlinks back to original locations when moving files
        logger: Logger instance
        show_progress: Whether to show progress bar
        
    Returns:
        List of dictionaries with information about created groups
    """
    if logger is None:
        logger = logging.getLogger("directory_structure")
    
    # Create output directory if it doesn't exist and we're not in dry run mode
    if not dryrun:
        try:
            os.makedirs(output_dir, exist_ok=True)
            logger.debug(f"Created output directory: {output_dir}")
        except Exception as e:
            logger.error(f"Failed to create output directory {output_dir}: {e}")
            raise
    
    # Process metric overrides if provided as string
    if isinstance(metric_overrides, str):
        metric_overrides = get_metric_overrides(metric_overrides)
    elif metric_overrides is None:
        metric_overrides = {}
    
    results = []
    singletons = []
    
    # Setup progress bar if available and requested
    if show_progress and TQDM_AVAILABLE:
        iterator = tqdm(similar_groups, desc="Creating output structure")
    else:
        iterator = similar_groups
        logger.info(f"Creating output structure for {len(similar_groups)} groups...")
    
    for group_idx, image_group in enumerate(iterator):
        # Skip processing for single-image groups if not including singletons
        if len(image_group) == 1 and not include_singletons:
            continue
            
        # Handle singleton images differently if requested
        if len(image_group) == 1 and include_singletons:
            singleton_path = next(iter(image_group))
            singletons.append(singleton_path)
            continue
        
        # Find the best image in the group using hybrid approach
        try:
            best_image = find_best_image_hybrid(
                image_group, 
                primary_metrics=primary_metrics,
                secondary_metrics=secondary_metrics,
                metric_weights=metric_weights,
                date_preference=date_preference,
                metric_overrides=metric_overrides,
                logger=logger if logger.isEnabledFor(logging.DEBUG) else None
            )
        except Exception as e:
            logger.error(f"Error finding best image for group {group_idx}: {e}")
            best_image = None
        
        if not best_image:
            logger.warning(f"Could not determine best image for group {group_idx}")
            continue
        
        # Get filename and dimensions for naming
        best_filename = os.path.splitext(os.path.basename(best_image))[0]
        width, height = get_image_dimensions(best_image)
        
        # Create directory name
        dir_name = naming_pattern.format(
            filename=best_filename,
            width=width,
            height=height
        )
        
        # Handle long paths if requested
        group_dir = os.path.join(output_dir, dir_name)
        if handle_long_paths and len(group_dir) > max_path_length:
            safe_dir, metadata_path = create_safe_path(group_dir, max_path_length)
            
            # Write metadata if path was shortened and not in dry run
            if metadata_path and not dryrun:
                write_metadata_file(metadata_path, group_dir, {
                    "Original name": dir_name,
                    "Best image": best_image,
                    "Image dimensions": f"{width}x{height}"
                })
            
            group_dir = safe_dir
        
        # Create candidates directory
        candidates_dir = os.path.join(group_dir, f"{best_filename}{suffix}")
        
        # Handle long paths for candidates directory
        if handle_long_paths and len(candidates_dir) > max_path_length:
            safe_dir, metadata_path = create_safe_path(candidates_dir, max_path_length)
            
            # Write metadata if path was shortened and not in dry run
            if metadata_path and not dryrun:
                write_metadata_file(metadata_path, candidates_dir, {
                    "Original name": f"{best_filename}{suffix}",
                    "Parent group": dir_name
                })
            
            candidates_dir = safe_dir
        
        # Log what we're doing
        logger.info(f"Processing group {group_idx+1}: {os.path.basename(group_dir)}")
        
        if not dryrun:
            # Create directories
            try:
                os.makedirs(group_dir, exist_ok=True)
                os.makedirs(candidates_dir, exist_ok=True)
                logger.debug(f"Created directories: {group_dir} and {candidates_dir}")
            except Exception as e:
                logger.error(f"Failed to create directories: {e}")
                continue
        
        # Handle the best image
        best_image_dest = os.path.join(group_dir, os.path.basename(best_image))
        
        # Handle long paths for best image destination
        if handle_long_paths and len(best_image_dest) > max_path_length:
            safe_path, metadata_path = create_safe_path(best_image_dest, max_path_length)
            
            # Write metadata if path was shortened and not in dry run
            if metadata_path and not dryrun:
                write_metadata_file(metadata_path, best_image_dest, {
                    "Original filename": os.path.basename(best_image),
                    "Source path": best_image
                })
            
            best_image_dest = safe_path
        
        if not dryrun:
            try:
                # Always copy best image if copy_best is True, otherwise use file_handling mode
                if copy_best:
                    actual_dest = handle_duplicate(best_image, best_image_dest, "copy", False, collision_strategy)
                    logger.debug(f"Copied best image to {actual_dest}")
                elif file_handling == "copy":
                    actual_dest = handle_duplicate(best_image, best_image_dest, "copy", False, collision_strategy)
                    logger.debug(f"Copied best image to {actual_dest}")
                elif file_handling == "move":
                    actual_dest = handle_duplicate(best_image, best_image_dest, "move", create_backlinks, collision_strategy)
                    logger.debug(f"Moved best image to {actual_dest}")
                    # Note: backlinks are created by handle_duplicate if requested
                else:  # symlink is the default
                    actual_dest = handle_duplicate(best_image, best_image_dest, "symlink", False, collision_strategy)
                    logger.debug(f"Created symlink for best image at {actual_dest}")
                
                # Update best_image_dest with the actual destination (which might have changed due to collision)
                best_image_dest = actual_dest
            except Exception as e:
                logger.error(f"Failed to handle best image {best_image}: {e}")
                continue
        
        # Process all images in the group (including best) for candidates directory
        candidate_count = 0
        for image_path in image_group:
            candidate_dest = os.path.join(candidates_dir, os.path.basename(image_path))
            
            # Handle long paths for candidate destination
            if handle_long_paths and len(candidate_dest) > max_path_length:
                safe_path, metadata_path = create_safe_path(candidate_dest, max_path_length)
                
                # Write metadata if path was shortened and not in dry run
                if metadata_path and not dryrun:
                    write_metadata_file(metadata_path, candidate_dest, {
                        "Original filename": os.path.basename(image_path),
                        "Source path": image_path
                    })
                
                candidate_dest = safe_path
            
            if not dryrun:
                try:
                    if file_handling == "copy":
                        actual_dest = handle_duplicate(image_path, candidate_dest, "copy", False, collision_strategy)
                        logger.debug(f"Copied candidate to {actual_dest}")
                    elif file_handling == "move":
                        actual_dest = handle_duplicate(image_path, candidate_dest, "move", create_backlinks, collision_strategy)
                        logger.debug(f"Moved candidate to {actual_dest}")
                        # Note: backlinks are created by handle_duplicate if requested
                    else:  # symlink is the default
                        actual_dest = handle_duplicate(image_path, candidate_dest, "symlink", False, collision_strategy)
                        logger.debug(f"Created symlink for candidate at {actual_dest}")
                    candidate_count += 1
                except Exception as e:
                    logger.error(f"Failed to process candidate {image_path}: {e}")
        
        # Add to results
        results.append({
            "best_image": best_image,
            "best_image_dest": best_image_dest,
            "candidates_dir": candidates_dir,
            "total_candidates": candidate_count
        })
    
    # Handle singleton images if requested
    if include_singletons and singletons:
        handle_singletons(
            singletons, 
            output_dir, 
            singletons_subdir, 
            file_handling, 
            create_backlinks, 
            handle_long_paths, 
            max_path_length, 
            collision_strategy,
            dryrun, 
            logger
        )
    
    return results

def handle_singletons(singletons, output_dir, singletons_subdir, file_handling,
                     create_backlinks, handle_long_paths, max_path_length,
                     collision_strategy, dryrun, logger):
    """Handle singleton images (with no duplicates)."""
    if not singletons:
        return
        
    singletons_dir = os.path.join(output_dir, singletons_subdir)
    
    if not dryrun:
        try:
            os.makedirs(singletons_dir, exist_ok=True)
            logger.info(f"Created singletons directory: {singletons_dir}")
            
            for singleton_path in singletons:
                singleton_dest = os.path.join(singletons_dir, os.path.basename(singleton_path))
                
                # Handle long paths for singleton destination
                if handle_long_paths and len(singleton_dest) > max_path_length:
                    safe_path, metadata_path = create_safe_path(singleton_dest, max_path_length)
                    
                    # Write metadata if path was shortened
                    if metadata_path:
                        write_metadata_file(metadata_path, singleton_dest, {
                            "Original filename": os.path.basename(singleton_path),
                            "Source path": singleton_path
                        })
                    
                    singleton_dest = safe_path
                
                try:
                    handle_duplicate(singleton_path, singleton_dest, file_handling, create_backlinks, collision_strategy)
                except Exception as e:
                    logger.error(f"Failed to process singleton {singleton_path}: {e}")
            
            logger.info(f"Processed {len(singletons)} singleton images")
        except Exception as e:
            logger.error(f"Failed to process singleton images: {e}")

def collect_best_images(base_dir, output_dir, mode="copy", handle_long_paths=True, 
                       max_path_length=250, include_singletons=True,
                       singletons_subdir="_singletons_", create_backlinks=False,
                       collision_strategy="hierarchical", logger=None):
    """
    Collect all best images from group directories into a single directory.
    
    Args:
        base_dir: Base directory containing group directories
        output_dir: Directory where to collect best images
        mode: How to handle files - "copy", "symlink", or "move"
        handle_long_paths: Whether to handle long paths
        max_path_length: Maximum allowed path length
        include_singletons: Whether to include singleton images
        singletons_subdir: Subdirectory name for singleton images
        create_backlinks: Create symlinks back to original locations when moving files
        collision_strategy: Strategy for resolving filename collisions
        logger: Logger instance
    
    Returns:
        Number of images collected
    """
    if logger is None:
        logger = logging.getLogger("directory_structure")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Collecting best images into {output_dir}")
    
    # Find all group directories (any directory that's not the singletons directory)
    group_dirs = []
    for item in os.listdir(base_dir):
        item_path = os.path.join(base_dir, item)
        if os.path.isdir(item_path) and not item.startswith('.') and item != singletons_subdir:
            group_dirs.append(item_path)
    
    logger.info(f"Found {len(group_dirs)} group directories to collect from")
    
    collected_count = 0
    
    # Process each group directory to find the best image
    for group_dir in group_dirs:
        # Find best image (non-directory file in the group directory)
        best_images = [f for f in os.listdir(group_dir) 
                      if os.path.isfile(os.path.join(group_dir, f)) and 
                      not f.startswith('.') and 
                      not f.endswith('.txt')]  # Skip metadata files
        
        if not best_images:
            logger.warning(f"No best image found in {group_dir}")
            continue
        
        best_image = best_images[0]  # Take the first file as the best image
        src_path = os.path.join(group_dir, best_image)
        
        # Generate destination path
        dest_path = os.path.join(output_dir, best_image)
        
        # Handle long paths if requested
        if handle_long_paths and len(dest_path) > max_path_length:
            safe_path, metadata_path = create_safe_path(dest_path, max_path_length)
            
            # Write metadata if path was shortened
            if metadata_path:
                write_metadata_file(metadata_path, dest_path, {
                    "Original filename": best_image,
                    "Source path": src_path,
                    "Source group": os.path.basename(group_dir)
                })
            
            dest_path = safe_path
        
        # Handle the file according to the specified mode
        try:
            actual_dest = handle_duplicate(src_path, dest_path, mode=mode, create_backlink=create_backlinks, 
                                           collision_strategy=collision_strategy)
            collected_count += 1
            logger.debug(f"Collected {src_path} to {actual_dest}")
        except Exception as e:
            logger.error(f"Error collecting {src_path}: {e}")
    
    # Also collect singletons if requested
    if include_singletons:
        singletons_dir = os.path.join(base_dir, singletons_subdir)
        if os.path.exists(singletons_dir) and os.path.isdir(singletons_dir):
            singleton_files = [f for f in os.listdir(singletons_dir) 
                              if os.path.isfile(os.path.join(singletons_dir, f)) and 
                              not f.startswith('.') and 
                              not f.endswith('.txt')]  # Skip metadata files
            
            for singleton_file in singleton_files:
                src_path = os.path.join(singletons_dir, singleton_file)
                
                # Generate destination path
                dest_path = os.path.join(output_dir, singleton_file)
                
                # Handle long paths if requested
                if handle_long_paths and len(dest_path) > max_path_length:
                    safe_path, metadata_path = create_safe_path(dest_path, max_path_length)
                    
                    # Write metadata if path was shortened
                    if metadata_path:
                        write_metadata_file(metadata_path, dest_path, {
                            "Original filename": singleton_file,
                            "Source path": src_path,
                            "Source": "Singleton"
                        })
                    
                    dest_path = safe_path
                
                # Handle the file according to the specified mode
                try:
                    actual_dest = handle_duplicate(src_path, dest_path, mode=mode, create_backlink=create_backlinks,
                                                  collision_strategy=collision_strategy)
                    collected_count += 1
                    logger.debug(f"Collected singleton {src_path} to {actual_dest}")
                except Exception as e:
                    logger.error(f"Error collecting singleton {src_path}: {e}")
    
    logger.info(f"Collected {collected_count} images to {output_dir}")
    return collected_count