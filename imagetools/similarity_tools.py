#!/usr/bin/env python3
"""
similarity_tools.py

Functions for computing CLIP embeddings and image similarity.
Part of the refactored common_imagetools functionality.

Updates include:
- Named presets for similarity thresholds
- Enhanced region-based similarity calculations
"""

import os
import sys
import logging
import pickle
import tempfile
import time
from pathlib import Path

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
    
try:
    import torch
    from transformers import CLIPProcessor, CLIPModel
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

from imagetools import TQDM_AVAILABLE, tqdm

# Global constants
DEFAULT_MODEL_NAME = "openai/clip-vit-base-patch32"

# Similarity threshold presets
SIMILARITY_PRESETS = {
    "same": 0.989,             # Almost identical images
    "almost_same": 0.978,      # Very slight differences
    "very_similar": 0.96,      # Visually very similar
    "similar": 0.94,           # Noticeably similar
    "not_same_same_location": 0.90,  # Different but same scene/location
    "not_same_very_similar_location": 0.80,  # Different but similar scene
    "not_same_similar_location": 0.70,  # Different with some common elements
    "dissimilar": 0.60         # Largely different images
}

def check_dependencies():
    """Check if required dependencies are available for similarity computation."""
    missing = []
    if not PILLOW_AVAILABLE:
        missing.append("PIL/Pillow")
    if not TRANSFORMERS_AVAILABLE:
        missing.append("torch and transformers")
    
    return missing

# -----------------------------
# CLIP Model and Embedding Functions
# -----------------------------
def load_clip_model(model_name=DEFAULT_MODEL_NAME, device="auto"):
    """Load the CLIP model and processor."""
    if not TRANSFORMERS_AVAILABLE:
        raise ImportError("torch and transformers are required for CLIP models")
        
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    
    try:
        model = CLIPModel.from_pretrained(model_name)
        processor = CLIPProcessor.from_pretrained(model_name)
        model.to(device)
        return model, processor, device
    except Exception as e:
        raise RuntimeError(f"Failed to load CLIP model {model_name}: {e}")

def compute_embedding(image_path, model, processor, device):
    """Compute the embedding for a single image."""
    if not TRANSFORMERS_AVAILABLE or not PILLOW_AVAILABLE:
        raise ImportError("Required dependencies missing for embedding computation")
        
    try:
        image = Image.open(image_path).convert('RGB')
        inputs = processor(images=image, return_tensors="pt")
        pixel_values = inputs["pixel_values"].to(device)
        with torch.no_grad():
            outputs = model.get_image_features(pixel_values)
        return outputs.squeeze(0).cpu()
    except Exception as e:
        logging.warning(f"Error computing embedding for {image_path}: {e}")
        return None

def extract_image_region(image_path, region_type="center", size=512):
    """Extract a specific region from an image for more detailed comparison."""
    if not PILLOW_AVAILABLE:
        raise ImportError("PIL/Pillow is required for image processing")
        
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            
            # Ensure size fits within the image
            size = min(size, width, height)
            
            if region_type == "center":
                # Extract center region
                left = (width - size) // 2
                top = (height - size) // 2
                right = left + size
                bottom = top + size
                return img.crop((left, top, right, bottom))
            elif region_type == "top_left":
                return img.crop((0, 0, size, size))
            elif region_type == "top_right":
                return img.crop((width - size, 0, width, size))
            elif region_type == "bottom_left":
                return img.crop((0, height - size, size, height))
            elif region_type == "bottom_right":
                return img.crop((width - size, height - size, width, height))
            else:
                # Default to center
                left = (width - size) // 2
                top = (height - size) // 2
                right = left + size
                bottom = top + size
                return img.crop((left, top, right, bottom))
    except Exception as e:
        logging.warning(f"Error extracting region from {image_path}: {e}")
        return None

class TemporaryRegionFiles:
    """Context manager for temporary region files."""
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="image_regions_")
        self.files = []
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Clean up all temporary files
        for file in self.files:
            try:
                if os.path.exists(file):
                    os.remove(file)
            except Exception as e:
                logging.warning(f"Error removing temporary file {file}: {e}")
        
        # Remove temporary directory
        try:
            os.rmdir(self.temp_dir)
        except Exception as e:
            logging.warning(f"Error removing temporary directory {self.temp_dir}: {e}")
    
    def create_temp_file(self, suffix=".png"):
        """Create a temporary file path in the temporary directory."""
        fd, temp_path = tempfile.mkstemp(suffix=suffix, dir=self.temp_dir)
        os.close(fd)
        self.files.append(temp_path)
        return temp_path

def compute_region_similarity(img1_path, img2_path, model, processor, device, regions=1):
    """Compare specific regions of two images for enhanced similarity checking."""
    if not TRANSFORMERS_AVAILABLE or not PILLOW_AVAILABLE:
        raise ImportError("Required dependencies missing for region similarity computation")
        
    try:
        # First compute whole-image similarity
        embedding1 = compute_embedding(img1_path, model, processor, device)
        embedding2 = compute_embedding(img2_path, model, processor, device)
        
        if embedding1 is None or embedding2 is None:
            return 0.0
            
        full_sim = cosine_similarity(embedding1, embedding2)
        
        if regions <= 1:
            return full_sim
            
        # Create context manager for temporary files
        with TemporaryRegionFiles() as temp_files:
            # Calculate similarity for additional regions
            region_similarities = [full_sim]  # Start with the full image similarity
            
            region_types = ["center"]
            if regions > 1:
                region_types.extend(["top_left", "top_right", "bottom_left", "bottom_right"])
            
            # Limit to requested number of regions
            region_types = region_types[:regions]
            
            for region_type in region_types:
                region1 = extract_image_region(img1_path, region_type)
                region2 = extract_image_region(img2_path, region_type)
                
                if region1 and region2:
                    # Save regions temporarily
                    temp1 = temp_files.create_temp_file(suffix=f"_region1_{region_type}.png")
                    temp2 = temp_files.create_temp_file(suffix=f"_region2_{region_type}.png")
                    region1.save(temp1)
                    region2.save(temp2)
                    
                    # Compute embeddings and similarity
                    r_embedding1 = compute_embedding(temp1, model, processor, device)
                    r_embedding2 = compute_embedding(temp2, model, processor, device)
                    
                    if r_embedding1 is not None and r_embedding2 is not None:
                        region_sim = cosine_similarity(r_embedding1, r_embedding2)
                        region_similarities.append(region_sim)
        
        # Calculate weighted average, giving more weight to the full image similarity
        weights = [2.0] + [1.0] * (len(region_similarities) - 1)
        weighted_sum = sum(w * s for w, s in zip(weights, region_similarities))
        return weighted_sum / sum(weights)
    except Exception as e:
        logging.warning(f"Error computing region similarity: {e}")
        return full_sim  # Fall back to full image similarity if region comparison fails

def compute_embeddings_batch(image_paths, model, processor, device, batch_size=16, show_progress=True):
    """Compute embeddings for a list of images in batches."""
    if not TRANSFORMERS_AVAILABLE or not PILLOW_AVAILABLE:
        raise ImportError("Required dependencies missing for embedding computation")
    
    embeddings = {}
    
    # Setup progress bar if available and requested
    if show_progress and TQDM_AVAILABLE:
        iterator = tqdm(image_paths, desc="Computing embeddings")
    else:
        iterator = image_paths

    current_batch = []
    current_paths = []
    
    for image_path in iterator:
        try:
            image = Image.open(image_path).convert('RGB')
            current_batch.append(image)
            current_paths.append(image_path)
            
            if len(current_batch) >= batch_size:
                inputs = processor(images=current_batch, return_tensors="pt", padding=True)
                pixel_values = inputs["pixel_values"].to(device)
                
                with torch.no_grad():
                    outputs = model.get_image_features(pixel_values)
                
                for idx, path in enumerate(current_paths):
                    embeddings[path] = outputs[idx].cpu()
                
                current_batch, current_paths = [], []
                
        except Exception as e:
            logging.warning(f"Error processing {image_path}: {e}")
    
    # Process any remaining images
    if current_batch:
        try:
            inputs = processor(images=current_batch, return_tensors="pt", padding=True)
            pixel_values = inputs["pixel_values"].to(device)
            
            with torch.no_grad():
                outputs = model.get_image_features(pixel_values)
            
            for idx, path in enumerate(current_paths):
                embeddings[path] = outputs[idx].cpu()
                
        except Exception as e:
            logging.warning(f"Error processing final batch: {e}")
    
    return embeddings

def cosine_similarity(embedding1, embedding2):
    """Calculate cosine similarity between two embeddings."""
    if not TRANSFORMERS_AVAILABLE:
        raise ImportError("torch is required for similarity computation")
        
    return torch.nn.functional.cosine_similarity(embedding1.unsqueeze(0),
                                                 embedding2.unsqueeze(0), dim=1).item()

# -----------------------------
# Grouping Functions
# -----------------------------
def get_similarity_threshold(preset=None, threshold=None):
    """
    Get similarity threshold value from preset name or direct value.
    
    Args:
        preset: Named preset from SIMILARITY_PRESETS
        threshold: Direct threshold value (0-1)
        
    Returns:
        Similarity threshold value
    """
    if preset and preset in SIMILARITY_PRESETS:
        return SIMILARITY_PRESETS[preset]
    elif threshold is not None:
        return threshold
    else:
        # Default to "very_similar" preset
        return SIMILARITY_PRESETS["very_similar"]

def group_similar_images(embeddings, similarity_threshold=0.96, similarity_preset=None,
                        use_regions=0, model=None, processor=None, device=None,
                        logger=None, show_progress=True):
    """
    Group images based on a similarity threshold.
    
    Args:
        embeddings: Dictionary mapping image paths to their embeddings
        similarity_threshold: Direct threshold value (0-1)
        similarity_preset: Named preset from SIMILARITY_PRESETS
        use_regions: Number of image regions to check for similarity (0-5)
        model: CLIP model for region comparison (required if use_regions > 0)
        processor: CLIP processor for region comparison (required if use_regions > 0)
        device: Device for model inference (required if use_regions > 0)
        logger: Logger instance
        show_progress: Whether to show progress bar
        
    Returns:
        List of sets, where each set contains paths to similar images
    """
    if not TRANSFORMERS_AVAILABLE:
        raise ImportError("torch is required for similarity computation")
        
    if logger is None:
        logger = logging.getLogger("similarity_tools")
    
    # Get threshold value from preset or direct value
    threshold = get_similarity_threshold(similarity_preset, similarity_threshold)
        
    image_paths = list(embeddings.keys())
    num_images = len(image_paths)
    
    logger.info(f"Grouping {num_images} images with similarity >= {threshold:.4f}" + 
                (f" (preset: {similarity_preset})" if similarity_preset else ""))
    
    # Initialize groups with each image in its own group
    groups = [{path} for path in image_paths]
    
    # Calculate all pairwise comparisons
    comparisons = [(i, j) for i in range(num_images) for j in range(i+1, num_images)]
    
    # Setup progress bar if available and requested
    if show_progress and TQDM_AVAILABLE:
        iterator = tqdm(comparisons, desc="Comparing images", total=len(comparisons))
    else:
        iterator = comparisons
    
    for i, j in iterator:
        path_i = image_paths[i]
        path_j = image_paths[j]
        
        # Skip if embeddings are missing
        if path_i not in embeddings or path_j not in embeddings:
            continue
            
        # Calculate similarity
        if use_regions > 0 and model and processor and device:
            # Use region-based similarity for more accuracy
            sim = compute_region_similarity(path_i, path_j, model, processor, device, regions=use_regions)
        else:
            # Use standard embedding similarity
            sim = cosine_similarity(embeddings[path_i], embeddings[path_j])
        
        # If similar, merge groups
        if sim >= threshold:
            # Find which groups contain these images
            group_i = next(g for g in groups if path_i in g)
            group_j = next(g for g in groups if path_j in g)
            
            # If they're not already in the same group, merge them
            if group_i != group_j:
                group_i.update(group_j)
                groups.remove(group_j)
    
    # Return all groups, including singletons (will be filtered later if needed)
    logger.info(f"Found {len(groups)} total groups ({len([g for g in groups if len(g) > 1])} with multiple images)")
    
    return groups

# -----------------------------
# Caching Embeddings
# -----------------------------
def save_cache(embeddings, cache_file, logger=None):
    """Save embeddings to a pickle cache file."""
    if logger is None:
        logger = logging.getLogger("similarity_tools")
        
    try:
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, 'wb') as f:
            pickle.dump(embeddings, f)
        logger.info(f"Cache saved to {cache_file}")
        return True
    except Exception as e:
        logger.warning(f"Failed to save cache: {e}")
        return False

def load_cache(cache_file, logger=None):
    """Load embeddings from a pickle cache file."""
    if logger is None:
        logger = logging.getLogger("similarity_tools")
        
    if not os.path.exists(cache_file):
        logger.debug(f"Cache file not found: {cache_file}")
        return {}
        
    try:
        with open(cache_file, 'rb') as f:
            embeddings = pickle.load(f)
        logger.info(f"Loaded {len(embeddings)} cached embeddings")
        return embeddings
    except Exception as e:
        logger.warning(f"Failed to load cache: {e}")
        return {}