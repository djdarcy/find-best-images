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

import os
import shutil
import argparse
import subprocess
import re
import fnmatch  # For fallback pattern matching
from pathlib import Path
from PIL import Image
import sys
from sys import platform as _platform

# Try to import tqdm for progress bars
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    tqdm = lambda x, **kwargs: x  # Simple passthrough for when tqdm is not available

try:
    from imagetools.file_operations import (
        handle_duplicate, create_symlink, 
        reset_filename_registry, get_unique_path
    )
    from imagetools.core_imagetools import (
        matches_pattern, check_patterns
    )
    IMAGETOOLS_AVAILABLE = True
except ImportError:
    IMAGETOOLS_AVAILABLE = False

DEFAULT_EXTENSIONS = ['bmp', 'jpg', 'jpeg', 'png', 'webp', 'gif', 'tiff', 'tif', 'jp2', 'heif', 'heic']

def parse_arguments():
    epilog_text = (
        "Note: If you encounter issues with symbolic links on Windows, especially with network drives or UNC paths, \n"
        "you may need to enable local to remote symbolic link evaluations. This can be done by running the command: \n"
        "'fsutil behavior set SymlinkEvaluation L2L:0 L2R:0 R2R:1 R2L:1' in an elevated command prompt.\n"
        "\n"
        "Examples:\n"
        "  Most common: search for images with 1080 pixels or more in either dimension:\n"
        "    imgsrch.py -O 1080 -op gte -r -p .\\find_best_image_results\\best_collection -a copy -od output_dir_1080_flt -os flat -md 0\n"
        "\n"
        "  Search for large images in both dimensions and output to a file:\n"
        "    imgsrch.py -B 1080 -op gte -r -o images_bigger_than_1080_in_both_dims.txt\n"
        "\n"
        "  Copy large images to a flat directory structure:\n"
        "    imgsrch.py -O 1080 -op gte -r -a copy -od output_directory -os flat\n"
        "\n"
        "  Create symlinks preserving directory structure:\n"
        "    imgsrch.py -B 1080 -op gte -r -a symlink -od linked_images\n"
        "\n"
        "  Preview what would happen without making changes:\n"
        "    imgsrch.py -B 1080 -op gte -r -a copy -od output_directory --dry-run\n"
        "\n"
        "Pattern matching examples:\n"
        "  Search for JPGs in vacation folders only:\n"
        "    imgsrch.py -r --include-dirs vacation* --include-files *.jpg -B 1080 -op gte\n"
        "\n"
        "  Exclude backup folders and temporary files:\n"
        "    imgsrch.py -r --exclude-pattern *backup* --exclude-files *.tmp -B 1080 -op gte\n"
        "\n"
        "  Limit search depth to 2 directory levels:\n"
        "    imgsrch.py -r --max-depth 2 -B 1080 -op gte -o results.txt\n"
    )

    parser = argparse.ArgumentParser(
        description="Search for images based on various criteria.",
        epilog=epilog_text,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Create logical parameter groups
    path_group = parser.add_argument_group('Path and General Options')
    dim_group = parser.add_argument_group('Image Dimension Filtering')
    output_group = parser.add_argument_group('Output Options')
    pattern_group = parser.add_argument_group('Pattern Matching')
    
    # Path and General Options
    path_group.add_argument("-p", "--path", type=str, default=os.getcwd(), help="Starting directory for search.")
    path_group.add_argument("-r", "--recursive", action="store_true", help="Recursively search through directories.")
    path_group.add_argument("-v", "--verbosity", action="count", default=0, help="Increase output verbosity.")
    path_group.add_argument("-ex", "--exif", action="store_true", help="Search for images with EXIF data.")
    path_group.add_argument("-ed", "--exifdetail", type=str, help="Specific EXIF detail to search for.")

    # Pattern Matching - consolidated all pattern parameters here
    pattern_group.add_argument("-e", "--ext", type=str, help="File extension to filter images.")
    pattern_group.add_argument("-m", "--filemask", type=str, help="Filemask for filtering files.")
    pattern_group.add_argument("-x", "--regex", type=str, help="Regex pattern for file matching.")
    pattern_group.add_argument("-xd", "--exclude", action="append", help="Directories to exclude from search.")
    pattern_group.add_argument("-id", "--include-dirs", action="append", help="Directory patterns to include in search.")
    pattern_group.add_argument("-if", "--include-files", action="append", help="File patterns to include in search.")
    pattern_group.add_argument("-ef", "--exclude-files", action="append", help="File patterns to exclude from search.")
    pattern_group.add_argument("-ip", "--include-pattern", action="append", 
                              help="Patterns to match both directories and files for inclusion.")
    pattern_group.add_argument("-ep", "--exclude-pattern", action="append", 
                              help="Patterns to match both directories and files for exclusion.")
    pattern_group.add_argument("-pm", "--pattern-mode", choices=["glob", "regex"], default="glob", 
                              help="Pattern matching mode (default: glob)")
    pattern_group.add_argument("-md", "--max-depth", type=int, help="Maximum directory depth to search (0 = only start directory)")

    # Dimension Filtering
    dim_group.add_argument("-W", "--width", type=int, help="Width to search for.")
    dim_group.add_argument("-H", "--height", type=int, help="Height to search for.")
    dim_group.add_argument("-B", "--both", type=int, help="Size for both width and height.")
    dim_group.add_argument("-O", "--eitheror", type=int, help="Size for either width or height.")
    dim_group.add_argument("-op", "--operation", choices=["gt", "lt", "eq", "gte", "lte", "neq"], 
                        default="eq", help="Operation for size comparison (default: eq).")

    # Output Options
    output_group.add_argument("-o", "--output", type=str, help="Output file to write results (for 'list' action).")
    output_group.add_argument("-a", "--action", type=str, choices=["list", "symlink", "copy", "move"], default="list", 
                        help="Action to perform with matching files: list (default), symlink, copy, or move.")
    output_group.add_argument("-od", "--output-dir", type=str, 
                        help="Directory to output files (required for symlink/copy/move actions).")
    output_group.add_argument("-os", "--output-structure", type=str, choices=["nested", "flat"], 
                        default="nested", help="Output structure: nested (preserve paths) or flat (all files in one directory)")
    output_group.add_argument("-c", "--collision", type=str, choices=["hierarchical", "rename", "skip", "overwrite"], 
                        default="hierarchical", help="Strategy for handling filename collisions.")
    output_group.add_argument("-d", "--dry-run", action="store_true", help="Preview actions without making changes.")

    args = parser.parse_args()
    return parser, args

def is_image_file(filename, ext, filemask):
    if ext:
        return filename.lower().endswith('.' + ext.lower())
    elif filemask:
        return filemask in filename
    else:
        return any(filename.lower().endswith('.' + e) for e in DEFAULT_EXTENSIONS)

def compare_dimension(dimension, target, operation):
    if operation == "gt":
        return dimension > target
    elif operation == "lt":
        return dimension < target
    elif operation == "eq":
        return dimension == target
    elif operation == "gte":
        return dimension >= target
    elif operation == "lte":
        return dimension <= target
    elif operation == "neq":
        return dimension != target

def matches_criteria(image_path, args):
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            
            # Skip the check if the parameter isn't provided
            if args.width and not compare_dimension(width, args.width, args.operation):
                return False
            if args.height and not compare_dimension(height, args.height, args.operation):
                return False
            if args.both and not (compare_dimension(width, args.both, args.operation) and compare_dimension(height, args.both, args.operation)):
                return False
            if args.eitheror and not (compare_dimension(width, args.eitheror, args.operation) or compare_dimension(height, args.eitheror, args.operation)):
                return False
                
            # If no dimension criteria were specified, or all were passed, return True
            return True
    except Exception as e:
        if args.verbosity > 1:
            print(f"Error processing {image_path}: {e}")
        return False

def print_image_info(image_path, args):
    info = image_path
    if args.verbosity >= 1:
        try:
            with Image.open(image_path) as img:
                width, height = img.size
                print(f"Dimensions: {width}x{height}")
                if args.verbosity >= 2 and hasattr(img, "_getexif") and img._getexif():
                    print("EXIF data:")
                    for tag, value in img._getexif().items():
                        print(f"  {tag}: {value}")
        except Exception as e:
            if args.verbosity > 1:
                print(f"Error accessing image data for {image_path}: {e}")
    
    return info

# Fallback implementations when imagetools is not available
def fallback_create_symlink(source_path, target_path):
    """Create a symbolic link with fallback for when imagetools is not available."""
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    
    # The source path needs to be absolute to work correctly
    source_path = os.path.abspath(source_path)
    target_path = os.path.abspath(target_path)
    
    if _platform == "win32":
        subprocess.run(["mklink", target_path, source_path], shell=True, 
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        os.symlink(source_path, target_path)
    
    return target_path

def fallback_handle_duplicate(source_path, target_path, mode="copy", collision_strategy="rename"):
    """Handle file operations with collision strategy when imagetools is not available."""
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    
    # If target exists, handle based on collision strategy
    if os.path.exists(target_path):
        if collision_strategy == "overwrite":
            pass  # Will be overwritten in the copy/move operation
        elif collision_strategy == "skip":
            return target_path
        elif collision_strategy in ["rename", "hierarchical"]:
            # Simple rename strategy - add a number
            base, ext = os.path.splitext(target_path)
            counter = 1
            while os.path.exists(f"{base}_{counter}{ext}"):
                counter += 1
            target_path = f"{base}_{counter}{ext}"
    
    # Perform the operation
    if mode == "copy":
        shutil.copy2(source_path, target_path)
    elif mode == "move":
        shutil.move(source_path, target_path)
    
    return target_path

def fallback_check_patterns(item, include_patterns=None, exclude_patterns=None, pattern_mode="glob"):
    """Fallback implementation of check_patterns when imagetools is not available."""
    # If exclude patterns exist, none must match
    if exclude_patterns:
        exclude_match = any(fallback_matches_pattern(item, [p], pattern_mode) for p in exclude_patterns)
        if exclude_match:
            return False
            
    # If include patterns exist, one must match
    if include_patterns:
        include_match = any(fallback_matches_pattern(item, [p], pattern_mode) for p in include_patterns)
        if not include_match:
            return False
            
    return True
def fallback_matches_pattern(name, patterns, mode="glob"):
    """Fallback implementation when imagetools is not available."""
    if not patterns:
        return False
    
    if mode == "glob":
        return any(fnmatch.fnmatch(name, p) for p in patterns)
    else:  # regex
        return any(re.search(p, name) for p in patterns)

def process_matching_file(file_path, output_dir, action, structure, base_path, collision_strategy, dry_run=False):
    """
    Process a matching file according to the specified action.
    
    Args:
        file_path: Path to the source file
        output_dir: Directory where to output the file
        action: Action to perform (symlink, copy, move)
        structure: Output structure (nested, flat)
        base_path: Base path for relative path preservation
        collision_strategy: How to handle filename collisions
        dry_run: If True, only prints what would happen without making changes
    
    Returns:
        Path to the output file
    """
    # Determine output path based on structure
    if structure == "flat":
        rel_path = os.path.basename(file_path)
    else:  # nested
        rel_path = os.path.relpath(file_path, base_path)
    
    output_path = os.path.join(output_dir, rel_path)
    
    if dry_run:
        return output_path
    
    # Create directory if needed
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Perform action with appropriate function based on availability
    if action == "symlink":
        if IMAGETOOLS_AVAILABLE:
            create_symlink(file_path, output_path)
        else:
            fallback_create_symlink(file_path, output_path)
    elif action == "copy":
        if IMAGETOOLS_AVAILABLE:
            handle_duplicate(file_path, output_path, mode="copy", collision_strategy=collision_strategy)
        else:
            fallback_handle_duplicate(file_path, output_path, mode="copy", collision_strategy=collision_strategy)
    elif action == "move":
        if IMAGETOOLS_AVAILABLE:
            handle_duplicate(file_path, output_path, mode="move", collision_strategy=collision_strategy)
        else:
            fallback_handle_duplicate(file_path, output_path, mode="move", collision_strategy=collision_strategy)
    
    return output_path

def search_images(start_path, args):
    matched_files = []
    output_file = None
    
    # Open output file once if specified
    if args.output and args.action == "list":
        output_file = open(args.output, "w", encoding="utf-8")
    
    # Get list of files to process
    all_files = []
    
    for root, dirs, files in os.walk(start_path):
        # Calculate current depth for max_depth filtering
        rel_path = os.path.relpath(root, start_path)
        current_depth = 0 if rel_path == '.' else rel_path.count(os.sep) + 1
        
        # Skip excluded directories (traditional method)
        if args.exclude is not None and any(os.path.abspath(root).startswith(os.path.abspath(excluded_dir)) 
                                           for excluded_dir in args.exclude):
            dirs.clear()  # Skip this branch entirely
            continue
            
        # Apply directory pattern filtering
        dir_basename = os.path.basename(root)
        
        # Check directory exclusion and inclusion patterns
        if args.exclude_pattern or args.include_dirs:
            if IMAGETOOLS_AVAILABLE:
                dir_pattern_match = check_patterns(
                    dir_basename, 
                    include_patterns=args.include_dirs, 
                    exclude_patterns=args.exclude_pattern, 
                    pattern_mode=args.pattern_mode
                )
            else:
                dir_pattern_match = fallback_check_patterns(
                    dir_basename,
                    include_patterns=args.include_dirs,
                    exclude_patterns=args.exclude_pattern,
                    pattern_mode=args.pattern_mode
                )
                
            if not dir_pattern_match and current_depth > 0:  # Don't skip root directory
                dirs.clear()  # Skip this directory
                continue
        
        # Filter directories list in-place to prevent descent into excluded dirs
        i = 0
        while i < len(dirs):
            dir_name = dirs[i]
            
            # Handle exclusions and inclusions
            if args.exclude_pattern or args.include_dirs or args.include_pattern:
                include_match = True
                exclude_match = False
                
                # Check if directory should be excluded
                if args.exclude_pattern:
                    if IMAGETOOLS_AVAILABLE:
                        exclude_match = any(matches_pattern(dir_name, p, args.pattern_mode) for p in args.exclude_pattern)
                    else:
                        exclude_match = fallback_matches_pattern(dir_name, args.exclude_pattern, args.pattern_mode)
                
                # Traditional exclude by path prefix
                if args.exclude and any(os.path.abspath(os.path.join(root, dir_name)).startswith(
                       os.path.abspath(excluded_dir)) for excluded_dir in args.exclude):
                    exclude_match = True
                
                # Check if directory matches include patterns (if specified)
                if args.include_dirs:
                    if IMAGETOOLS_AVAILABLE:
                        include_match = any(matches_pattern(dir_name, p, args.pattern_mode) for p in args.include_dirs)
                    else:
                        include_match = fallback_matches_pattern(dir_name, args.include_dirs, args.pattern_mode)
                
                # Check general include patterns
                elif args.include_pattern:
                    if IMAGETOOLS_AVAILABLE:
                        include_match = any(matches_pattern(dir_name, p, args.pattern_mode) for p in args.include_pattern)
                    else:
                        include_match = fallback_matches_pattern(dir_name, args.include_pattern, args.pattern_mode)
                
                # Exclusion takes precedence over inclusion
                if exclude_match or (not include_match and (args.include_dirs or args.include_pattern)):
                    del dirs[i]
                    continue
            
            i += 1
            
        # Process files in current directory before limiting depth
        for file in files:
            # Check file exclusion patterns first
            exclude_file = False
            include_file = True
            
            if args.exclude_files:
                if IMAGETOOLS_AVAILABLE:
                    exclude_file = any(matches_pattern(file, p, args.pattern_mode) for p in args.exclude_files)
                else:
                    exclude_file = fallback_matches_pattern(file, args.exclude_files, args.pattern_mode)
            
            if args.exclude_pattern:
                if IMAGETOOLS_AVAILABLE:
                    exclude_file = exclude_file or any(matches_pattern(file, p, args.pattern_mode) for p in args.exclude_pattern)
                else:
                    exclude_file = exclude_file or fallback_matches_pattern(file, args.exclude_pattern, args.pattern_mode)
            
            if exclude_file:
                continue
            
            # Check file inclusion patterns if specified
            if args.include_files:
                if IMAGETOOLS_AVAILABLE:
                    include_file = any(matches_pattern(file, p, args.pattern_mode) for p in args.include_files)
                else:
                    include_file = fallback_matches_pattern(file, args.include_files, args.pattern_mode)
                
                if not include_file:
                    continue
            
            if args.include_pattern:
                if IMAGETOOLS_AVAILABLE:
                    include_file = include_file and any(matches_pattern(file, p, args.pattern_mode) for p in args.include_pattern)
                else:
                    include_file = include_file and fallback_matches_pattern(file, args.include_pattern, args.pattern_mode)
                
                if not include_file:
                    continue
            
            # If it passes all pattern checks, check if it's an image file
            if is_image_file(file, args.ext, args.filemask):
                full_path = os.path.join(root, file)
                all_files.append(full_path)
        
        # Now limit directory traversal depth *after* processing files in the current directory
        if args.max_depth is not None and current_depth >= args.max_depth:
            dirs.clear()  # Don't descend further, but we've already processed this level's files
                
        if not args.recursive:
            break
    
    # Process files with progress bar if available
    if TQDM_AVAILABLE and len(all_files) > 10:
        file_iterator = tqdm(all_files, desc="Processing images")
    else:
        file_iterator = all_files
        
    # Statistics tracking
    stats = {
        "processed": 0,
        "matched": 0,
        "errors": 0,
        "actions": 0
    }
    
    for full_path in file_iterator:
        stats["processed"] += 1
        try:
            if matches_criteria(full_path, args):
                matched_files.append(full_path)
                stats["matched"] += 1
                
                # Print or write info
                info = print_image_info(full_path, args)
                if output_file:
                    output_file.write(info + "\n")
                elif args.action == "list" and not args.verbosity:
                    print(info)
                
                # Process file based on action
                if args.action != "list" and args.output_dir:
                    processed_path = process_matching_file(
                        full_path,
                        args.output_dir,
                        args.action,
                        args.output_structure,
                        start_path,
                        args.collision,
                        args.dry_run
                    )
                    stats["actions"] += 0 if args.dry_run else 1
                    
                    if args.verbosity > 0 or args.dry_run:
                        action_text = f"Would {args.action}" if args.dry_run else f"{args.action.capitalize()}ed"
                        print(f"{action_text} {full_path} to {processed_path}")
        except Exception as e:
            stats["errors"] += 1
            if args.verbosity > 0:
                print(f"Error processing {full_path}: {e}")
    
    # Close output file if opened
    if output_file:
        output_file.close()
        
    # Print summary
    print(f"\nSummary:")
    print(f"  Files processed: {stats['processed']}")
    print(f"  Files matched: {stats['matched']}")
    print(f"  Errors: {stats['errors']}")
    
    if args.action != "list":
        if args.dry_run:
            print(f"  {args.action.capitalize()} operations that would be performed: {stats['matched']}")
        else:
            print(f"  {args.action.capitalize()} operations performed: {stats['actions']}")
            
    return matched_files

def main():
    parser, args = parse_arguments()
    
    # Show help if no arguments were provided
    if len(sys.argv) == 1:
        parser.print_help()
        return 0
    
    # Validate arguments
    if args.action != "list" and not args.output_dir:
        print(f"Error: --output-dir is required when using --action {args.action}")
        return 1
        
    # Prepare output directory if needed
    if args.action != "list" and args.output_dir and not args.dry_run:
        os.makedirs(args.output_dir, exist_ok=True)
        if IMAGETOOLS_AVAILABLE:
            # Reset the filename registry to avoid conflicts
            reset_filename_registry()
    
    if not IMAGETOOLS_AVAILABLE and args.action != "list" and not args.dry_run:
        print("Warning: imagetools module not available, falling back to basic file operations")
    
    # Search for images matching criteria
    search_images(args.path, args)
    
    return 0

if __name__ == "__main__":
    main()
