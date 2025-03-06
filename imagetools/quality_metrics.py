#!/usr/bin/env python3
"""
quality_metrics.py

Functions for assessing image quality and selecting the best images.
Part of the refactored common_imagetools functionality.

Updates include:
- Hybrid evaluation supporting ordered and weighted metrics
- Enhanced date-based metric evaluation with configurable preferences
- Improved metric handling for diverse use cases
"""

import os
import sys
import logging
import platform
import time
from datetime import datetime

from imagetools import (
    PILLOW_AVAILABLE, 
    Image
)

# Try importing optional dependencies
# try:
#     from PIL import Image
#     PILLOW_AVAILABLE = True
# except ImportError:
#     PILLOW_AVAILABLE = False

# Import from our modules
from .core_imagetools import FILE_FORMAT_QUALITY, get_image_dimensions

# Default weights for metrics
DEFAULT_METRIC_WEIGHTS = {
    "dimensions": 1.0,
    "resolution": 0.9,
    "format_quality": 0.8,
    "filesize": 0.7,
    "modified_date": 0.6,
    "created_date": 0.5
}

def get_image_filesize(image_path):
    """Get the filesize of an image."""
    try:
        return os.path.getsize(image_path)
    except Exception as e:
        logging.warning(f"Error getting filesize for {image_path}: {e}")
        return 0

def get_image_modified_time(image_path):
    """Get the modification time of an image."""
    try:
        return os.path.getmtime(image_path)
    except Exception as e:
        logging.warning(f"Error getting modification time for {image_path}: {e}")
        return 0

def get_image_created_time(image_path):
    """Get the creation time of an image."""
    try:
        if platform.system() == "Windows":
            return os.path.getctime(image_path)
        else:
            # On Unix, creation time is not always available
            stat = os.stat(image_path)
            # Use the earlier of mtime and ctime for Unix
            return min(stat.st_mtime, stat.st_ctime)
    except Exception as e:
        logging.warning(f"Error getting creation time for {image_path}: {e}")
        return 0

def get_image_quality(image_path, metric="dimensions", date_preference="newest"):
    """
    Determine image quality based on a metric.
    
    Args:
        image_path: Path to the image file
        metric: Quality metric to use
        date_preference: For date metrics, prefer "newest" or "oldest"
    
    Returns:
        A numeric quality value (higher is better)
    """
    if not PILLOW_AVAILABLE and metric in ["dimensions", "resolution"]:
        raise ImportError("PIL/Pillow is required for image processing")
        
    try:
        if metric == "filesize":
            return os.path.getsize(image_path)
        elif metric == "modified_date":
            date_value = os.path.getmtime(image_path)
            # Invert value if we prefer oldest files (smaller timestamp = older)
            return -date_value if date_preference == "oldest" else date_value
        elif metric == "created_date":
            date_value = get_image_created_time(image_path)
            # Invert value if we prefer oldest files
            return -date_value if date_preference == "oldest" else date_value
        elif metric == "format_quality":
            # Get file extension and look up its quality ranking
            ext = os.path.splitext(image_path)[1].lower()
            return FILE_FORMAT_QUALITY.get(ext, 0)  # Default to 0 if extension not recognized
        
        with Image.open(image_path) as img:
            width, height = img.size
            
            if metric == "dimensions":
                # Use the minimum dimension as the quality metric
                return min(width, height)
            elif metric == "resolution":
                # Total pixel count
                return width * height
            else:
                # Default to resolution
                return width * height
                
    except Exception as e:
        logging.warning(f"Error determining quality for {image_path}: {e}")
        return 0

def get_metric_overrides(metric_overrides_str):
    """Parse metric overrides from a string format.
    
    Format: "metric1:preference1,metric2:preference2"
    Example: "modified_date:oldest,created_date:newest"
    
    Returns dict of {metric: preference}
    """
    if not metric_overrides_str:
        return {}
        
    overrides = {}
    try:
        for pair in metric_overrides_str.split(','):
            if ':' in pair:
                metric, preference = pair.strip().split(':')
                if preference in ("newest", "oldest"):
                    overrides[metric.strip()] = preference
    except Exception as e:
        logging.warning(f"Error parsing metric overrides {metric_overrides_str}: {e}")
    
    return overrides

def find_best_image_hybrid(image_group, primary_metrics=None, secondary_metrics=None, 
                          metric_weights=None, date_preference="newest", 
                          metric_overrides=None, margin_threshold=0.05, logger=None):
    """
    Select the best image using a hybrid approach of ordered primary metrics followed by
    weighted evaluation of secondary metrics for ties.
    
    Args:
        image_group: A set or list of image paths
        primary_metrics: List of metrics to use in strict order
        secondary_metrics: List of metrics to use with weights for tie-breaking
        metric_weights: Dictionary mapping metrics to their weights
        date_preference: Global preference for date metrics ("newest" or "oldest")
        metric_overrides: Dictionary of per-metric preference overrides
        margin_threshold: Tolerance percentage for considering weighted values equal
        logger: Optional logger for debug output
        
    Returns:
        The path to the best image
    """
    if logger is None:
        logger = logging.getLogger("quality_metrics")
        
    candidates = list(image_group)
    
    if not primary_metrics:
        # Default quality metrics in priority order
        primary_metrics = ["dimensions", "format_quality", "filesize", "modified_date"]
    
    if not secondary_metrics:
        secondary_metrics = []
    
    if not metric_weights:
        metric_weights = DEFAULT_METRIC_WEIGHTS
    
    if not metric_overrides:
        metric_overrides = {}
        
    if len(candidates) <= 1:  # Empty group or single candidate
        return candidates[0] if candidates else None
    
    # Step 1: Apply ordered evaluation with primary metrics
    for metric in primary_metrics:
        if len(candidates) <= 1:
            break
        
        # Determine date preference for this specific metric
        metric_date_pref = metric_overrides.get(metric, date_preference)
        
        # Get quality values for all remaining candidates
        qualities = [(img, get_image_quality(img, metric, metric_date_pref)) for img in candidates]
        
        if logger and logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Evaluating metric: {metric} (preference: {metric_date_pref})")
            for img, quality in qualities:
                logger.debug(f"  {os.path.basename(img)}: {quality}")
        
        # Find the best quality score
        best_quality = max(q[1] for q in qualities)
        
        # Keep only candidates with the best quality for this metric
        candidates = [img for img, quality in qualities if quality == best_quality]
        
        if logger and logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Remaining candidates after {metric}: {len(candidates)}")
    
    # If we have a single candidate after primary metrics, return it
    if len(candidates) == 1:
        return candidates[0]
    
    # Step 2: If we still have ties, use weighted evaluation with secondary metrics
    if secondary_metrics and len(candidates) > 1:
        if logger and logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Using weighted evaluation for {len(candidates)} remaining candidates")
        
        # Calculate weighted scores
        candidate_scores = []
        
        # Track metric values for normalization
        metric_values = {metric: [] for metric in secondary_metrics}
        
        # First pass: collect all values for normalization
        for img in candidates:
            for metric in secondary_metrics:
                if metric in metric_weights:  # Only consider metrics with weights
                    metric_date_pref = metric_overrides.get(metric, date_preference)
                    value = get_image_quality(img, metric, metric_date_pref)
                    metric_values[metric].append(value)
        
        # Calculate min and max for each metric for normalization
        metric_ranges = {}
        for metric, values in metric_values.items():
            if values:
                metric_min = min(values)
                metric_max = max(values)
                # Avoid division by zero - if all values are the same, normalization = 1
                metric_ranges[metric] = (metric_min, metric_max, 
                                        metric_max - metric_min if metric_max > metric_min else 1)
        
        # Second pass: calculate normalized weighted scores
        for img in candidates:
            total_score = 0
            for metric in secondary_metrics:
                if metric in metric_weights and metric in metric_ranges:
                    metric_date_pref = metric_overrides.get(metric, date_preference)
                    value = get_image_quality(img, metric, metric_date_pref)
                    
                    # Normalize to 0-1 range
                    min_val, max_val, range_val = metric_ranges[metric]
                    normalized = (value - min_val) / range_val if range_val else 1
                    
                    # Apply weight
                    weighted_score = normalized * metric_weights[metric]
                    total_score += weighted_score
                    
                    if logger and logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"  {os.path.basename(img)} - {metric}: {value} -> {weighted_score:.4f}")
            
            candidate_scores.append((img, total_score))
            
            if logger and logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"  {os.path.basename(img)} total score: {total_score:.4f}")
        
        # Sort by score (highest first)
        candidate_scores.sort(key=lambda x: x[1], reverse=True)
        
        if not candidate_scores:
            return None
        
        # Return the highest scored image
        return candidate_scores[0][0]
    
    # If no secondary metrics or empty candidate list, return the first candidate
    return candidates[0] if candidates else None

# Keep these for backward compatibility
def find_best_image(image_group, quality_metrics=None, date_preference="newest", metric_overrides=None):
    """
    Select the best image from a group using multiple prioritized quality metrics.
    
    Args:
        image_group: A set or list of image paths
        quality_metrics: List of metrics to use, in priority order
        date_preference: Preference for date metrics ("newest" or "oldest")
        metric_overrides: Dictionary of per-metric preference overrides
        
    Returns:
        The path to the best image
    """
    return find_best_image_hybrid(
        image_group, 
        primary_metrics=quality_metrics, 
        secondary_metrics=[], 
        date_preference=date_preference,
        metric_overrides=metric_overrides
    )

def find_best_image_weighted(image_group, quality_metrics=None, weights=None, 
                            date_preference="newest", metric_overrides=None, margin_threshold=0.05):
    """
    Select the best image from a group using weighted quality metrics.
    
    Args:
        image_group: A set or list of image paths
        quality_metrics: List of metrics to use (dimensions, filesize, resolution, etc.)
        weights: Dictionary mapping metrics to their weights (higher = more important)
        date_preference: Preference for date metrics ("newest" or "oldest")
        metric_overrides: Dictionary of per-metric preference overrides
        margin_threshold: Tolerance percentage for considering values equal (0.05 = 5%)
        
    Returns:
        The path to the best image
    """
    if not quality_metrics:
        # Default quality metrics
        quality_metrics = ["dimensions", "format_quality", "filesize", "modified_date"]
    
    return find_best_image_hybrid(
        image_group, 
        primary_metrics=[], 
        secondary_metrics=quality_metrics, 
        metric_weights=weights,
        date_preference=date_preference,
        metric_overrides=metric_overrides,
        margin_threshold=margin_threshold
    )