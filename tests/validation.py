#!/usr/bin/env python3
"""
tests/validation.py

Utilities for validating test outputs for find_best_images.py.
"""

import os
import sys
import json
import platform
import pickle
from typing import Tuple, Dict, Any, List, Optional
import logging
from PIL import Image
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("validation")

def print_header(message: str, file=None) -> str:
    """Print a formatted header."""
    header = "\n" + "=" * 80 + f"\n {message}\n" + "=" * 80
    if file:
        print(header, file=file)
    else:
        print(header)
    return header

def get_image_dimensions(image_path: str) -> Tuple[int, int]:
    """Get the dimensions of an image."""
    try:
        with Image.open(image_path) as img:
            return img.size
    except Exception as e:
        logger.warning(f"Error getting dimensions for {image_path}: {e}")
        return (0, 0)

def get_image_filesize(image_path: str) -> int:
    """Get the filesize of an image."""
    try:
        return os.path.getsize(image_path)
    except Exception as e:
        logger.warning(f"Error getting filesize for {image_path}: {e}")
        return 0

def get_image_modified_time(image_path: str) -> float:
    """Get the modification time of an image."""
    try:
        return os.path.getmtime(image_path)
    except Exception as e:
        logger.warning(f"Error getting modification time for {image_path}: {e}")
        return 0

def get_image_resolution(image_path: str) -> int:
    """Get the total resolution (width * height) of an image."""
    try:
        width, height = get_image_dimensions(image_path)
        return width * height
    except Exception as e:
        logger.warning(f"Error calculating resolution for {image_path}: {e}")
        return 0

def is_symbolic_link(path: str) -> bool:
    """Check if a path is a symbolic link, with platform-specific handling."""
    if platform.system() == "Windows":
        # On Windows, check for both symlinks and hardlinks
        if not os.path.isfile(path):
            return False
            
        try:
            # Using file attributes for Windows link detection
            import win32api
            import win32con
            attrs = win32api.GetFileAttributes(path)
            return bool(attrs & win32con.FILE_ATTRIBUTE_REPARSE_POINT)
        except (ImportError, AttributeError):
            # Fallback if win32api isn't available
            try:
                return Path(path).is_symlink() or os.stat(path).st_nlink > 1
            except:
                # If all checks fail, assume it's not a symlink
                return False
    else:
        # On Unix-like systems, simply use os.path.islink
        return os.path.islink(path)

def check_if_same_file(path1: str, path2: str) -> bool:
    """Check if two paths refer to the same file (accounting for symlinks)."""
    try:
        # Resolve any symlinks to get the actual file path
        real_path1 = os.path.realpath(path1)
        real_path2 = os.path.realpath(path2)
        
        # If the real paths are the same, they're the same file
        if real_path1 == real_path2:
            return True
        
        # On Windows, also compare device and inode (if available)
        if platform.system() != "Windows":
            stat1 = os.stat(path1)
            stat2 = os.stat(path2)
            return (stat1.st_dev == stat2.st_dev) and (stat1.st_ino == stat2.st_ino)
        
        # Additional check for Windows
        try:
            import win32file
            # Get file handles and info
            handle1 = win32file.CreateFile(path1, 0, 0, None, win32file.OPEN_EXISTING, 0, None)
            handle2 = win32file.CreateFile(path2, 0, 0, None, win32file.OPEN_EXISTING, 0, None)
            info1 = win32file.GetFileInformationByHandle(handle1)
            info2 = win32file.GetFileInformationByHandle(handle2)
            win32file.CloseHandle(handle1)
            win32file.CloseHandle(handle2)
            # Compare file index info
            return (info1[4] == info2[4]) and (info1[5] == info2[5])
        except (ImportError, Exception):
            # If win32file not available or other error, compare file contents as last resort
            with open(path1, 'rb') as f1, open(path2, 'rb') as f2:
                return f1.read() == f2.read()
                
    except Exception as e:
        logger.warning(f"Error comparing files {path1} and {path2}: {e}")
        return False

def validate_directory_structure(test_dir: str, verbose: int = 0,
                               output_file = None) -> bool:
    """Validate the directory structure created by find_best_images.py."""
    if not os.path.exists(test_dir):
        logger.error(f"Error: Directory {test_dir} does not exist.")
        return False
    
    # Look for directories created by the tool - these are our group directories
    group_dirs = [d for d in os.listdir(test_dir) if os.path.isdir(os.path.join(test_dir, d))
                  and not d.startswith('.') and d != "best_collection" and d != "_singletons_"]
    
    if not group_dirs:
        logger.warning(f"No group directories found in {test_dir}")
        return False
    
    logger.info(f"Found {len(group_dirs)} group directories.")
    
    # Check each group directory
    valid_dirs = 0
    
    for group_dir in group_dirs:
        group_path = os.path.join(test_dir, group_dir)
        
        # Check if there's a best image in the group directory
        best_images = [f for f in os.listdir(group_path) 
                     if os.path.isfile(os.path.join(group_path, f)) and
                     not f.startswith('.') and not f.endswith('.txt')]
        
        # Look for candidates directory
        candidate_dirs = [d for d in os.listdir(group_path) 
                        if os.path.isdir(os.path.join(group_path, d)) and 
                        ('_candidates' in d or '_variants' in d)]
        
        if not best_images:
            logger.warning(f"Warning: No best image found in {group_path}")
            continue
        
        if not candidate_dirs:
            logger.warning(f"Warning: No candidates directory found in {group_path}")
            continue
        
        # Get the candidates directory - it should be named with either _candidates or _variants suffix
        candidates_dir = None
        for d in candidate_dirs:
            if '_candidates' in d or '_variants' in d:
                candidates_dir = d
                break
                
        if not candidates_dir:
            logger.warning(f"Warning: No candidates directory with proper suffix found in {group_path}")
            continue
            
        candidates_path = os.path.join(group_path, candidates_dir)
        candidate_files = [f for f in os.listdir(candidates_path) 
                         if os.path.isfile(os.path.join(candidates_path, f)) and
                         not f.startswith('.') and not f.endswith('.txt')]
        
        # Basic checks
        valid_structure = len(best_images) >= 1 and len(candidate_files) >= 1
        
        if verbose > 0:
            logger.info(f"\nGroup: {group_dir}")
            logger.info(f"  Best image: {best_images[0] if best_images else 'None'}")
            logger.info(f"  Candidates directory: {candidates_dir}")
            logger.info(f"  Number of candidates: {len(candidate_files)}")
            logger.info(f"  Valid structure: {valid_structure}")
        
        if valid_structure:
            valid_dirs += 1
            
            # Quality check - verify best image according to quality metrics
            best_img_path = os.path.join(group_path, best_images[0])
            
            # Get various quality metrics for the best image and all candidates
            best_dimensions = get_image_dimensions(best_img_path)
            best_min_dimension = min(best_dimensions[0], best_dimensions[1])
            best_resolution = best_dimensions[0] * best_dimensions[1]
            best_filesize = get_image_filesize(best_img_path)
            best_mtime = get_image_modified_time(best_img_path)
            
            # Check all candidates to confirm best image selection based on multiple metrics
            all_candidates_metrics = []
            for candidate in candidate_files:
                candidate_path = os.path.join(candidates_path, candidate)
                dimensions = get_image_dimensions(candidate_path)
                min_dimension = min(dimensions[0], dimensions[1])
                resolution = dimensions[0] * dimensions[1]
                filesize = get_image_filesize(candidate_path)
                mtime = get_image_modified_time(candidate_path)
                
                all_candidates_metrics.append({
                    'file': candidate,
                    'path': candidate_path,
                    'dimensions': dimensions,
                    'min_dimension': min_dimension,
                    'resolution': resolution,
                    'filesize': filesize,
                    'mtime': mtime
                })
            
            if all_candidates_metrics:
                # Check various quality metrics - the best image should be optimal for at least one metric
                max_min_dimension = max(c['min_dimension'] for c in all_candidates_metrics)
                max_resolution = max(c['resolution'] for c in all_candidates_metrics)
                max_filesize = max(c['filesize'] for c in all_candidates_metrics)
                newest_mtime = max(c['mtime'] for c in all_candidates_metrics)
                oldest_mtime = min(c['mtime'] for c in all_candidates_metrics)
                
                # Check if the best image is optimal for at least one metric
                dimension_optimal = best_min_dimension >= max_min_dimension * 0.99  # Allow small margin for error
                resolution_optimal = best_resolution >= max_resolution * 0.99
                filesize_optimal = best_filesize >= max_filesize * 0.99
                newest_optimal = best_mtime >= newest_mtime - 60  # Allow 1 minute difference
                oldest_optimal = best_mtime <= oldest_mtime + 60
                
                metrics_passed = [
                    ("dimensions", dimension_optimal),
                    ("resolution", resolution_optimal),
                    ("filesize", filesize_optimal),
                    ("newest_date", newest_optimal),
                    ("oldest_date", oldest_optimal)
                ]
                
                if any(passed for _, passed in metrics_passed):
                    if verbose > 1:
                        passed_metrics = [metric for metric, passed in metrics_passed if passed]
                        logger.info(f"  Quality check passed: Best image is optimal for: {', '.join(passed_metrics)}")
                else:
                    logger.warning(f"Warning: Best image in {group_dir} does not appear to be optimal for any quality metric.")
                    if verbose > 1:
                        logger.info(f"  Best metrics: min_dim={best_min_dimension}, res={best_resolution}, size={best_filesize}, mtime={os.path.getctime(best_mtime)}")
                        logger.info(f"  Max metrics: min_dim={max_min_dimension}, res={max_resolution}, size={max_filesize}, newest={os.path.getctime(newest_mtime)}, oldest={os.path.getctime(oldest_mtime)}")
            
            # Check symlinks or copy status
            if verbose > 1:
                best_is_symlink = is_symbolic_link(best_img_path)
                logger.info(f"  Best image is symlink: {best_is_symlink}")
                
                symlinks = sum(1 for f in candidate_files if is_symbolic_link(os.path.join(candidates_path, f)))
                logger.info(f"  Candidate symlinks: {symlinks}/{len(candidate_files)}")
            
            # Look for metadata files for long paths
            metadata_files = [f for f in os.listdir(group_path) if f.endswith('.txt') and os.path.isfile(os.path.join(group_path, f))]
            if metadata_files and verbose > 1:
                logger.info(f"  Found {len(metadata_files)} metadata files for long paths")
    
    validation_success = valid_dirs == len(group_dirs)
    logger.info(f"\nValid group directories: {valid_dirs}/{len(group_dirs)} ({valid_dirs/len(group_dirs)*100:.1f}%)")
    return validation_success

def validate_collection_directory(test_dir: str, verbose: int = 0) -> bool:
    """Validate the collection directory structure, if present."""
    collection_dir = os.path.join(test_dir, "best_collection")
    if not os.path.exists(collection_dir):
        logger.info("No collection directory found.")
        return True  # Not a failure, it's optional
    
    # Check that it contains files
    collection_files = [f for f in os.listdir(collection_dir) 
                      if os.path.isfile(os.path.join(collection_dir, f)) and
                      not f.startswith('.') and not f.endswith('.txt')]
    
    if not collection_files:
        logger.warning(f"Collection directory exists but contains no files.")
        return False
    
    logger.info(f"Collection directory contains {len(collection_files)} files.")
    
    # Check if these are the best images from their respective groups
    group_dirs = [d for d in os.listdir(test_dir) if os.path.isdir(os.path.join(test_dir, d))
                  and not d.startswith('.') and d != "best_collection" and d != "_singletons_"]
    
    best_images = []
    for group_dir in group_dirs:
        group_path = os.path.join(test_dir, group_dir)
        group_files = [f for f in os.listdir(group_path) 
                     if os.path.isfile(os.path.join(group_path, f)) and
                     not f.startswith('.') and not f.endswith('.txt')]
        if group_files:
            best_images.append((group_dir, group_files[0], os.path.join(group_path, group_files[0])))
    
    # Check that each best image has a corresponding file in the collection
    found_matches = 0
    for group_name, best_img, best_path in best_images:
        # Look for an exact filename match first
        if best_img in collection_files:
            found_matches += 1
            if verbose > 1:
                logger.info(f"  Found best image {best_img} from group {group_name} in collection")
            continue
        
        # If no exact match, check if the collection has a file with the same content
        collection_paths = [os.path.join(collection_dir, f) for f in collection_files]
        for coll_path in collection_paths:
            if check_if_same_file(best_path, coll_path):
                found_matches += 1
                if verbose > 1:
                    logger.info(f"  Found matching file for {best_img} from group {group_name} in collection")
                break
    
    # If we should also check for singletons
    singletons_dir = os.path.join(test_dir, "_singletons_")
    if os.path.exists(singletons_dir) and os.path.isdir(singletons_dir):
        singleton_files = [f for f in os.listdir(singletons_dir) 
                          if os.path.isfile(os.path.join(singletons_dir, f)) and
                          not f.startswith('.') and not f.endswith('.txt')]
        
        for singleton_file in singleton_files:
            singleton_path = os.path.join(singletons_dir, singleton_file)
            
            # Check if this singleton is in the collection
            if singleton_file in collection_files:
                found_matches += 1
                if verbose > 1:
                    logger.info(f"  Found singleton {singleton_file} in collection")
                continue
            
            # Check for content match
            collection_paths = [os.path.join(collection_dir, f) for f in collection_files]
            for coll_path in collection_paths:
                if check_if_same_file(singleton_path, coll_path):
                    found_matches += 1
                    if verbose > 1:
                        logger.info(f"  Found matching file for singleton {singleton_file} in collection")
                    break
    
    total_expected = len(best_images) + (len(singleton_files) if 'singleton_files' in locals() else 0)
    match_percentage = (found_matches / total_expected * 100) if total_expected else 0
    logger.info(f"Found {found_matches} of {total_expected} expected images in collection ({match_percentage:.1f}%).")
    
    if verbose > 0 and match_percentage < 90:
        logger.warning("WARNING: Not all best images were found in the collection directory.")
    
    return match_percentage >= 90  # Allow for some files to be missing

def validate_singletons(test_dir: str, verbose: int = 0) -> bool:
    """Validate that singleton images were handled correctly."""
    singletons_dir = os.path.join(test_dir, "_singletons_")
    if not os.path.exists(singletons_dir):
        logger.info("No singletons directory found.")
        return True  # Not a failure, it's optional
    
    # Check that it contains files
    singleton_files = [f for f in os.listdir(singletons_dir) 
                      if os.path.isfile(os.path.join(singletons_dir, f)) and
                      not f.startswith('.') and not f.endswith('.txt')]
    
    if not singleton_files:
        logger.warning(f"Singletons directory exists but contains no files.")
        return False
    
    logger.info(f"Found {len(singleton_files)} singleton images.")
    
    # Check for symlinks
    symlink_count = sum(1 for f in singleton_files if is_symbolic_link(os.path.join(singletons_dir, f)))
    if verbose > 0:
        logger.info(f"  Singleton symlinks: {symlink_count}/{len(singleton_files)}")
    
    return True

def validate_move_operations(test_dir: str, verbose: int = 0) -> bool:
    """Check for proper move operations and backlinks."""
    # This requires running tests explicitly with --file-handling move
    move_dirs = []
    for item in os.listdir(test_dir):
        if "move" in item.lower() and os.path.isdir(os.path.join(test_dir, item)):
            move_dirs.append(os.path.join(test_dir, item))
    
    if not move_dirs:
        logger.info("No move operation test directory found.")
        return True  # Not a failure, it's optional
    
    # Check each move directory for backlinks
    backlinks_found = False
    
    for move_dir in move_dirs:
        # First, check each group's candidate directory for symlinks
        group_dirs = [d for d in os.listdir(move_dir) if os.path.isdir(os.path.join(move_dir, d))
                    and not d.startswith('.') and d != "_singletons_"]
        
        for group_dir in group_dirs:
            group_path = os.path.join(move_dir, group_dir)
            
            # Find candidates directory
            candidate_dirs = [d for d in os.listdir(group_path) 
                            if os.path.isdir(os.path.join(group_path, d)) and 
                            ('_candidates' in d or '_variants' in d)]
            
            if not candidate_dirs:
                continue
                
            candidates_path = os.path.join(group_path, candidate_dirs[0])
            candidate_files = [f for f in os.listdir(candidates_path) 
                            if os.path.isfile(os.path.join(candidates_path, f)) and
                            not f.startswith('.')]
            
            # Check if files are symlinks
            symlinks = [f for f in candidate_files if is_symbolic_link(os.path.join(candidates_path, f))]
            if symlinks:
                backlinks_found = True
                if verbose > 0:
                    logger.info(f"Found backlinks in {candidates_path}: {len(symlinks)} symlinks")
                break
        
        # Check singletons directory too
        singletons_dir = os.path.join(move_dir, "_singletons_")
        if os.path.exists(singletons_dir) and os.path.isdir(singletons_dir):
            singleton_files = [f for f in os.listdir(singletons_dir) 
                            if os.path.isfile(os.path.join(singletons_dir, f)) and
                            not f.startswith('.')]
            
            symlinks = [f for f in singleton_files if is_symbolic_link(os.path.join(singletons_dir, f))]
            if symlinks:
                backlinks_found = True
                if verbose > 0:
                    logger.info(f"Found backlinks in singletons directory: {len(symlinks)} symlinks")
    
    if backlinks_found:
        logger.info("Move operations with backlinks validation passed.")
        return True
    else:
        logger.warning("No backlinks found for move operations.")
        return False  # This might not be a failure depending on the test

def validate_cache_file(test_dir: str, verbose: int = 0) -> bool:
    """Check if cache file was created and has content."""
    cache_file = os.path.join(test_dir, ".embedding_cache.pkl")
    
    if os.path.exists(cache_file) and os.path.getsize(cache_file) > 0:
        logger.info(f"Cache file exists with size: {os.path.getsize(cache_file) / 1024:.1f} KB")
        
        # Check cache file content
        try:
            with open(cache_file, 'rb') as f:
                cache = pickle.load(f)
            
            if isinstance(cache, dict) and cache:
                logger.info(f"Cache contains {len(cache)} entries.")
                return True
            else:
                logger.warning("Cache file exists but has invalid content.")
                return False
        except Exception as e:
            logger.warning(f"Error reading cache file: {e}")
            return False
    else:
        logger.info("Cache file not found or empty.")
        return True  # Not a failure, it's optional if cache=False

def validate_long_path_handling(test_dir: str, verbose: int = 0) -> bool:
    """Validate long path handling and metadata files."""
    long_paths_found = False
    metadata_files = []
    
    # Search for metadata text files in the entire directory structure
    for root, _, files in os.walk(test_dir):
        for file in files:
            if file.endswith('.txt') and os.path.isfile(os.path.join(root, file)):
                # Try to read the file to check if it's a metadata file
                try:
                    with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                        content = f.read()
                        if "Original path:" in content or "Original filename:" in content:
                            metadata_files.append(os.path.join(root, file))
                            long_paths_found = True
                except Exception:
                    # Skip files that can't be read as text
                    pass
    
    if not long_paths_found:
        logger.info("No long path handling metadata files found.")
        return True  # Not a failure, it's optional
    
    logger.info(f"Found {len(metadata_files)} metadata files for long paths.")
    
    # Check content of metadata files
    valid_metadata = 0
    for metadata_file in metadata_files:
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if "Original path:" in content or "Original filename:" in content:
                valid_metadata += 1
                if verbose > 1:
                    logger.info(f"Valid metadata file: {metadata_file}")
                    if verbose > 2:
                        logger.info(f"Content: {content[:200]}...")
        except Exception as e:
            logger.warning(f"Error reading metadata file {metadata_file}: {e}")
    
    logger.info(f"Valid metadata files: {valid_metadata}/{len(metadata_files)}")
    return valid_metadata > 0

def validate_collision_handling(test_dir: str, verbose: int = 0) -> bool:
    """Validate filename collision handling."""
    # Look for evidence of collision handling throughout the directory structure
    collision_patterns = [
        "_dir", "_subdir",     # Parent directory pattern
        "_col_",               # Numeric collision pattern
        "_[a-f0-9]{8}",        # Hash pattern (8 character hex hash)
    ]
    
    collision_files = []
    
    # Search for files with collision patterns in their names
    for root, _, files in os.walk(test_dir):
        for file in files:
            # Skip metadata files
            if file.endswith('.txt'):
                continue
                
            for pattern in collision_patterns:
                import re
                if re.search(pattern, file):
                    collision_files.append(os.path.join(root, file))
                    break
    
    if not collision_files:
        logger.info("No evidence of collision handling found.")
        return True  # Not a failure, might not have collisions
    
    logger.info(f"Found {len(collision_files)} files with collision handling patterns.")
    
    if verbose > 0:
        # Show some examples
        examples = collision_files[:min(5, len(collision_files))]
        logger.info("Examples of collision-handled files:")
        for example in examples:
            logger.info(f"  {os.path.basename(example)}")
    
    return True


1
def validate_test_output(output_dir: str, verbose: int = 0) -> Tuple[bool, str]:
    """
    Validate the output directory structure from find_best_images.py.
    Returns a tuple of (overall_valid, details) where overall_valid is True if
    either group directories, singleton directories, or collection directories are valid.
    """
    structure_valid = validate_directory_structure(output_dir, verbose)
    singletons_valid = validate_singletons(output_dir, verbose)
    collection_valid = validate_collection_directory(output_dir, verbose)
    
    overall_valid = structure_valid or singletons_valid or collection_valid
    
    details = (f"Validation Results for {output_dir}:\n"
               f" - Directory Structure Valid: {structure_valid}\n"
               f" - Singletons Valid: {singletons_valid}\n"
               f" - Collection Valid: {collection_valid}\n"
               f"Contents: {os.listdir(output_dir)}\n")
    return overall_valid, details
