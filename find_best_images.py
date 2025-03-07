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
find_best_images.py

A tool to find the highest quality version of similar images across directories,
organizing them into a structured output with the best version as the main reference
and similar/duplicate versions linked in a candidates subfolder.

Enhanced with:
- Multiple quality metrics with priority ordering, including hybrid order/weight approach
- Region-based similarity checking for better duplicate detection
- Named similarity presets for easier threshold configuration
- Path length management for OS compatibility
- Directory/file pattern matching with glob and regex support
- Improved filename collision handling
- Singleton file handling
- Results collection into a single directory
- Move operations with backlinks
- Date preference configuration for quality metrics
"""

import os
import sys
import argparse
import logging
from datetime import datetime
import time

# script_dir = os.path.dirname(os.path.abspath(__file__))
# sys.path.insert(0, script_dir)  # Ensure Find-best-image/ is in sys.path
# sys.path.insert(0, os.path.join(script_dir, "imagetools"))

# print(f"DEBUG: sys.path = {sys.path}")

# Try to import our common library
try:
    import imagetools as cit
    # import common_imagetools as cit
except ImportError:
    print("Error: imagetools module not found in the current directory or PYTHONPATH.")
    print("Make sure imagetools module is in the same directory as this script.")
    sys.exit(1)

VERSION = "0.4.0"

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Find the highest quality version of similar images across directories.",
        epilog=r"Example: find_best_images.py -i .\Pictures\Vacation .\Pictures\Downloads -o .\BestImages -r"
    )
    
    # Input/Output Parameters
    input_group = parser.add_argument_group('Input/Output Parameters')
    input_group.add_argument("-i", "--input-dirs", action='append', required=True, 
                        help="Input directories to search for images (can be specified multiple times)")
    input_group.add_argument("-o", "--output-dir", required=True,
                        help="Output directory for organized images")
    input_group.add_argument("-e", "--extensions", nargs='+', 
                        help=f"Image extensions to include (default: {', '.join(ext.lstrip('.') for ext in cit.DEFAULT_EXTENSIONS)})")
    input_group.add_argument("-xd", "--exclude-dirs", nargs='+',
                        help="Directories to exclude from search")
    
    # Pattern Matching
    pattern_group = parser.add_argument_group('Pattern Matching')
    pattern_group.add_argument("--include-dirs-pattern", nargs='+',
                        help="Directory name patterns to include (glob or regex)")
    pattern_group.add_argument("--include-files-pattern", nargs='+',
                        help="File name patterns to include (glob or regex)")
    pattern_group.add_argument("--exclude-dirs-pattern", nargs='+',
                        help="Directory name patterns to exclude (glob or regex)")
    pattern_group.add_argument("--exclude-files-pattern", nargs='+',
                        help="File name patterns to exclude (glob or regex)")
    pattern_group.add_argument("--include-pattern", nargs='+',
                        help="General pattern to include for both directories and files")
    pattern_group.add_argument("--pattern-mode", choices=["glob", "regex"], default="glob",
                        help="Pattern matching mode (default: glob)")
    
    # Search Behavior
    search_group = parser.add_argument_group('Search Behavior')
    search_group.add_argument("-r", "--recursive", action="store_true", default=True,
                        help="Search directories recursively (default: True)")
    search_group.add_argument("--no-recursive", action="store_false", dest="recursive",
                        help="Don't search directories recursively")
    search_group.add_argument("--follow-symlinks", action="store_true", default=False,
                        help="Follow symbolic links during directory traversal")
    search_group.add_argument("--min-file-size", type=int, default=0,
                        help="Minimum file size to consider in KB")
    
    # Image Comparison
    comparison_group = parser.add_argument_group('Image Comparison')
    comparison_group.add_argument("--similarity-threshold", type=float, default=0.96,
                        help=f"Minimum similarity score to consider images as duplicates (default: 0.96)")
    comparison_group.add_argument("--similarity-preset", 
                        choices=list(cit.SIMILARITY_PRESETS.keys()),
                        help="Named preset for similarity threshold (overrides --similarity-threshold)")
    comparison_group.add_argument("--check-regions", type=int, default=0, choices=range(0, 6),
                        help="Number of image regions to check for similarity (0-5, default: 0)")
    comparison_group.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto",
                        help="Device to use for model inference (default: auto)")
    comparison_group.add_argument("--batch-size", type=int, default=16,
                        help="Batch size for processing images (default: 16)")
    
    # Best Image Selection - Primary Metrics
    quality_group = parser.add_argument_group('Best Image Selection - Primary Metrics')
    quality_group.add_argument("--primary-metrics", nargs='+', 
                        default=["dimensions", "format_quality", "filesize", "modified_date"],
                        choices=["dimensions", "filesize", "resolution", "format_quality", "modified_date", "created_date"],
                        help="Primary quality metrics to use, in strict order (default: dimensions format_quality filesize modified_date)")
    
    # Best Image Selection - Secondary Metrics
    secondary_group = parser.add_argument_group('Best Image Selection - Secondary Metrics')
    secondary_group.add_argument("--secondary-metrics", nargs='+', 
                        choices=["dimensions", "filesize", "resolution", "format_quality", "modified_date", "created_date"],
                        help="Secondary quality metrics to use for tie-breaking with weights")
    secondary_group.add_argument("--metric-weights", 
                        help="Weights for secondary metrics as comma-separated name:weight pairs (e.g., dimensions:1.0,filesize:0.8)")
    
    # Date Preferences
    date_group = parser.add_argument_group('Date Preferences')
    date_group.add_argument("--date-preference", choices=["newest", "oldest"], default="newest",
                        help="Preference for date-based metrics (default: newest)")
    date_group.add_argument("--prefer-oldest", action="store_true", default=False,
                        help="DEPRECATED: Prefer oldest files when using date metrics (use --date-preference=oldest instead)")
    date_group.add_argument("--date-metric-override", 
                        help="Override date preferences for specific metrics (e.g., modified_date:oldest,created_date:newest)")
    
    # Directory Structure
    structure_group = parser.add_argument_group('Directory Structure')
    structure_group.add_argument("--naming-pattern", default="{filename}_{width}x{height}_candidates",
                        help="Pattern for output directory names (default: {filename}_{width}x{height}_candidates)")
    structure_group.add_argument("--handle-long-paths", action="store_true", default=True,
                        help="Handle long paths by shortening and creating metadata files (default: True)")
    structure_group.add_argument("--no-handle-long-paths", action="store_false", dest="handle_long_paths",
                        help="Don't handle long paths")
    structure_group.add_argument("--max-path-length", type=int, default=250,
                        help="Maximum path length to allow (default: 250)")
    structure_group.add_argument("--file-handling", choices=["symlink", "copy", "move"], default="symlink",
                        help="How to handle duplicate files (default: symlink)")
    structure_group.add_argument("--create-backlinks", action="store_true", default=False,
                        help="Create links back to new locations when moving files (default: False)")
    structure_group.add_argument("--copy-best", action="store_true", default=False,
                        help="Copy best image instead of using the file handling mode (default: False)")
    structure_group.add_argument("--suffix", default="_candidates",
                        help="Custom suffix for candidate directories (default: _candidates)")
    structure_group.add_argument("--include-singletons", action="store_true", default=True,
                        help="Include singleton images (without duplicates) in output (default: True)")
    structure_group.add_argument("--no-include-singletons", action="store_false", dest="include_singletons",
                        help="Don't include singleton images")
    structure_group.add_argument("--singletons-subdir", default="_singletons_",
                        help="Custom subdirectory name for singleton images (default: _singletons_)")
    
    # Collision Handling
    collision_group = parser.add_argument_group('Filename Collision Handling')
    collision_group.add_argument("--collision-strategy", 
                        choices=["hierarchical", "hash", "numeric", "parent_only"], default="hierarchical",
                        help="Strategy for resolving filename collisions (default: hierarchical)")
    
    # Results Collection
    collection_group = parser.add_argument_group('Results Collection')
    collection_group.add_argument("--collect-results", action="store_true", default=False,
                        help="Collect best images into a separate directory (default: False)")
    collection_group.add_argument("--collection-dir", 
                        help="Directory for collected best images (default: 'best_collection' in output directory)")
    collection_group.add_argument("--collection-mode", choices=["symlink", "copy", "move"], default="copy",
                        help="How to handle collected files (default: copy)")
    
    # Processing Controls
    control_group = parser.add_argument_group('Processing Controls')
    control_group.add_argument("--dryrun", action="store_true",
                        help="Show what would be done without making changes")
    control_group.add_argument("--threads", type=int, default=os.cpu_count(),
                        help=f"Number of threads to use (default: {os.cpu_count()})")
    control_group.add_argument("--cache", action="store_true", default=True,
                        help="Cache embeddings to speed up future runs (default: True)")
    control_group.add_argument("--no-cache", action="store_false", dest="cache",
                        help="Don't cache embeddings")
    
    # Output and Logging
    output_group = parser.add_argument_group('Output and Logging')
    output_group.add_argument("-v", "--verbosity", action="count", default=0,
                        help="Increase output verbosity (use multiple times for more detail)")
    output_group.add_argument("--progress", action="store_true", default=True,
                        help="Show progress bar during processing (default: True)")
    output_group.add_argument("--no-progress", action="store_false", dest="progress",
                        help="Don't show progress bar")
    output_group.add_argument("--log-file", 
                        help="Write log output to a file instead of stdout")
    
    # Advanced Features
    advanced_group = parser.add_argument_group('Advanced Features')
    advanced_group.add_argument("--force", action="store_true",
                        help="Overwrite existing files/directories")
    advanced_group.add_argument("--skip-existing", action="store_true",
                        help="Skip processing if output directory already exists")
    
    # For legacy compatibility - accept singular form too
    quality_group.add_argument("--quality-metric", choices=["dimensions", "filesize", "resolution", "format_quality", "modified_date", "created_date"],
                        help="DEPRECATED: Use --primary-metrics instead")
    # Also legacy compatibility
    quality_group.add_argument("--quality-metrics", nargs='+', 
                        choices=["dimensions", "filesize", "resolution", "format_quality", "modified_date", "created_date"],
                        help="DEPRECATED: Use --primary-metrics instead")
    
    # Version information
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    
    return parser.parse_args()

def setup_logging(verbosity, log_file=None):
    """Configure logging based on verbosity level."""
    log_level = logging.WARNING
    if verbosity == 1:
        log_level = logging.INFO
    elif verbosity >= 2:
        log_level = logging.DEBUG
    
    # Configure logging to file if specified
    if log_file:
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            filename=log_file,
            filemode='w'
        )
        # Also log to console
        console = logging.StreamHandler()
        console.setLevel(log_level)
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)
    else:
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    return logging.getLogger("find_best_images")

def parse_metric_weights(weights_str):
    """Parse metric weights from a string format.
    
    Format: "metric1:weight1,metric2:weight2"
    Example: "dimensions:1.0,filesize:0.8"
    
    Returns dict of {metric: weight}
    """
    if not weights_str:
        return {}
        
    weights = {}
    try:
        for pair in weights_str.split(','):
            if ':' in pair:
                metric, weight = pair.strip().split(':')
                try:
                    weights[metric.strip()] = float(weight)
                except ValueError:
                    pass
    except Exception as e:
        logging.warning(f"Error parsing metric weights {weights_str}: {e}")
    
    return weights

def main():
    """Main entry point for the script."""
    start_time = time.time()
    args = parse_arguments()
    
    # Set up logging
    logger = setup_logging(args.verbosity, args.log_file)
    logger.info(f"Starting find_best_images.py version {VERSION}")
    
    # Check for required dependencies
    missing_deps = cit.check_dependencies()
    if missing_deps:
        print("Error: Missing required dependencies:")
        for dep in missing_deps:
            print(f"  - {dep}")
        print("\nPlease install the missing dependencies and try again.")
        print("You can install them with: pip install pillow torch transformers tqdm")
        return 1
    
    # Handle legacy single quality_metric argument
    if args.quality_metric:
        logger.warning("The --quality-metric option is deprecated. Please use --primary-metrics instead.")
        if not args.primary_metrics:
            args.primary_metrics = [args.quality_metric]
    
    # Handle legacy quality_metrics argument
    if args.quality_metrics and not args.primary_metrics:
        logger.warning("The --quality-metrics option is deprecated. Please use --primary-metrics instead.")
        args.primary_metrics = args.quality_metrics
    
    # Handle legacy prefer_oldest argument
    if args.prefer_oldest:
        logger.warning("The --prefer-oldest option is deprecated. Please use --date-preference=oldest instead.")
        args.date_preference = "oldest"
    
    # Parse metric weights if provided
    metric_weights = parse_metric_weights(args.metric_weights)
    
    # Parse date metric overrides if provided
    metric_overrides = cit.get_metric_overrides(args.date_metric_override)
    
    # Process general include pattern if provided
    if args.include_pattern:
        if not args.include_dirs_pattern:
            args.include_dirs_pattern = args.include_pattern
        if not args.include_files_pattern:
            args.include_files_pattern = args.include_pattern
    
    # Output directory
    output_dir = os.path.abspath(args.output_dir)
    if os.path.exists(output_dir) and not args.force and not args.skip_existing:
        logger.error(f"Output directory {output_dir} already exists. Use --force to overwrite or --skip-existing to skip.")
        return 1
    
    # Set up cache file
    cache_file = os.path.join(output_dir, ".embedding_cache.pkl")
    
    # Process input directories
    # Flatten list if input_dirs contains nested lists
    all_input_dirs = []
    for item in args.input_dirs:
        if isinstance(item, list):
            all_input_dirs.extend(item)
        else:
            all_input_dirs.append(item)
    
    # Convert input_dirs to absolute paths and ensure they all exist
    input_dirs = []
    for d in all_input_dirs:
        abs_path = os.path.abspath(d)
        if not os.path.exists(abs_path):
            logger.warning(f"Input directory does not exist: {abs_path}")
            continue
        if not os.path.isdir(abs_path):
            logger.warning(f"Not a directory: {abs_path}")
            continue
        input_dirs.append(abs_path)
    
    if not input_dirs:
        logger.error("No valid input directories found!")
        return 1
    
    # Log all input directories
    logger.info(f"Searching for images in {len(input_dirs)} directories:")
    for idx, directory in enumerate(input_dirs):
        logger.info(f"  {idx+1}. {directory}")
    
    # Prepare extensions list - normalize to always include the dot
    if args.extensions:
        extensions = [ext if ext.startswith('.') else f'.{ext}' for ext in args.extensions]
    else:
        extensions = cit.DEFAULT_EXTENSIONS
    
    # Find all images with pattern filtering
    try:
        all_images = cit.find_images(
            input_dirs=input_dirs,
            exclude_dirs=args.exclude_dirs,
            recursive=args.recursive,
            follow_symlinks=args.follow_symlinks,
            min_file_size=args.min_file_size,
            extensions=extensions,
            logger=logger,
            show_progress=args.progress and cit.TQDM_AVAILABLE,
            include_dirs_pattern=args.include_dirs_pattern,
            include_files_pattern=args.include_files_pattern,
            exclude_dirs_pattern=args.exclude_dirs_pattern,
            exclude_files_pattern=args.exclude_files_pattern,
            pattern_mode=args.pattern_mode
        )
    except Exception as e:
        logger.error(f"Error finding images: {e}")
        return 1
    
    if not all_images:
        logger.error("No valid images found!")
        return 1
    
    # Create output directory if it doesn't exist yet (needed for cache file)
    if args.cache and not os.path.exists(output_dir) and not args.dryrun:
        try:
            os.makedirs(output_dir, exist_ok=True)
            logger.debug(f"Created output directory: {output_dir}")
        except Exception as e:
            logger.error(f"Failed to create output directory: {e}")
            return 1
    
    # Load cache if enabled
    cached_embeddings = {}
    if args.cache:
        try:
            cached_embeddings = cit.load_cache(cache_file, logger=logger)
        except Exception as e:
            logger.warning(f"Error loading cache: {e}")
            cached_embeddings = {}
    
    # Determine which images need embedding computation
    images_to_process = [img for img in all_images if img not in cached_embeddings]
    logger.info(f"Computing embeddings for {len(images_to_process)} images")
    
    # Skip embedding computation if no new images
    if not images_to_process:
        embeddings = cached_embeddings
        logger.info("No new images to process, using cached embeddings")
    else:
        # Load models for embedding calculation
        try:
            model, processor, device = cit.load_clip_model(device=args.device)
            logger.info(f"Loaded CLIP model on device: {device}")
            
            # Compute embeddings
            new_embeddings = cit.compute_embeddings_batch(
                images_to_process,
                model,
                processor,
                device,
                batch_size=args.batch_size,
                show_progress=args.progress and cit.TQDM_AVAILABLE
            )
            
            # Combine cached and new embeddings
            embeddings = {**cached_embeddings, **new_embeddings}
            
            # Save updated cache
            if args.cache and not args.dryrun:
                cache_success = cit.save_cache(embeddings, cache_file, logger=logger)
                if not cache_success:
                    logger.warning("Failed to save embedding cache")
                
        except Exception as e:
            logger.error(f"Error computing embeddings: {e}")
            return 1
    
    # Group similar images, using region checking if requested
    try:
        # Determine similarity threshold - use preset if specified, otherwise use direct value
        similarity_threshold = args.similarity_threshold
        
        if args.similarity_preset:
            preset_threshold = cit.get_similarity_threshold(preset=args.similarity_preset)
            if preset_threshold != similarity_threshold:
                logger.info(f"Using similarity preset '{args.similarity_preset}' with threshold {preset_threshold}")
                similarity_threshold = preset_threshold
        
        if args.check_regions > 0:
            logger.info(f"Using region-based similarity with {args.check_regions} regions")
            
            similar_groups = cit.group_similar_images(
                embeddings,
                similarity_threshold=similarity_threshold,
                similarity_preset=args.similarity_preset,
                use_regions=args.check_regions,
                model=model if args.check_regions > 0 else None,
                processor=processor if args.check_regions > 0 else None,
                device=device if args.check_regions > 0 else None,
                logger=logger,
                show_progress=args.progress and cit.TQDM_AVAILABLE
            )
        else:
            similar_groups = cit.group_similar_images(
                embeddings,
                similarity_threshold=similarity_threshold,
                similarity_preset=args.similarity_preset,
                logger=logger,
                show_progress=args.progress and cit.TQDM_AVAILABLE
            )
    except Exception as e:
        logger.error(f"Error grouping similar images: {e}")
        return 1
    
    if not similar_groups:
        logger.info("No groups of images found.")
        return 0
    
    # Create output directory structure
    try:
        # Reset filename registry to ensure clean state
        cit.reset_filename_registry()
        
        results = cit.create_output_structure(
            similar_groups,
            output_dir,
            primary_metrics=args.primary_metrics,
            secondary_metrics=args.secondary_metrics,
            metric_weights=metric_weights,
            date_preference=args.date_preference,
            metric_overrides=metric_overrides,
            naming_pattern=args.naming_pattern,
            file_handling=args.file_handling,
            copy_best=args.copy_best,
            suffix=args.suffix,
            handle_long_paths=args.handle_long_paths,
            max_path_length=args.max_path_length,
            include_singletons=args.include_singletons,
            singletons_subdir=args.singletons_subdir,
            collision_strategy=args.collision_strategy,
            dryrun=args.dryrun,
            create_backlinks=args.create_backlinks,
            logger=logger,
            show_progress=args.progress and cit.TQDM_AVAILABLE
        )
    except Exception as e:
        logger.error(f"Error creating output structure: {e}")
        return 1
    
    # Collect results if requested
    if args.collect_results and not args.dryrun and results:
        try:
            collection_dir = args.collection_dir if args.collection_dir else os.path.join(output_dir, "best_collection")
            logger.info(f"Collecting best images into {collection_dir}")
            
            # Reset filename registry for collection to ensure clean state
            cit.reset_filename_registry()
            
            collected = cit.collect_best_images(
                output_dir,
                collection_dir,
                mode=args.collection_mode,
                handle_long_paths=args.handle_long_paths,
                max_path_length=args.max_path_length,
                include_singletons=args.include_singletons,
                singletons_subdir=args.singletons_subdir,
                create_backlinks=args.create_backlinks,
                collision_strategy=args.collision_strategy,
                logger=logger
            )
            
            logger.info(f"Collected {collected} best images")
        except Exception as e:
            logger.error(f"Error collecting best images: {e}")
    
    # Summary logging
    multi_image_groups = [g for g in similar_groups if len(g) > 1]
    singleton_groups = [g for g in similar_groups if len(g) == 1]
    
    logger.info(f"Summary:")
    logger.info(f"- Total images processed: {len(all_images)}")
    logger.info(f"- Groups with multiple images: {len(multi_image_groups)}")
    if args.include_singletons:
        logger.info(f"- Singleton images: {len(singleton_groups)}")
    logger.info(f"- Output directories created: {len(results)}")
    logger.info(f"- Total candidate images in groups: {sum(result['total_candidates'] for result in results)}")
    
    if args.dryrun:
        logger.info("This was a dry run. No files were actually created or modified.")
    
    # Log execution time
    end_time = time.time()
    logger.info(f"Total execution time: {end_time - start_time:.2f} seconds")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(130)
    except Exception as e:
        logging.exception("Unexpected error occurred.")
        sys.exit(1)