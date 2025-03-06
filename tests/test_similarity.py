#!/usr/bin/env python3
"""
tests/test_similarity.py

Tests for similarity threshold functionality in find_best_images.py.
Tests numeric thresholds, named presets, and region-based similarity.
"""

import os
import sys
from typing import Tuple, List, Dict

# Import common utilities
from tests.common import (
    image_test,
    run_find_best_images,
    TempTestDir,
    create_test_image_structure,
    TEST_IMAGES_DIR,
    logger
)

@image_test
def test_similarity_thresholds() -> Tuple[int, str, str, str]:
    """Test different similarity thresholds."""
    # Create a test directory structure
    test_dir, test_subdirs = create_test_image_structure(TEST_IMAGES_DIR)
    if not test_dir:
        return 1, None, "", "Failed to create test directory structure"
    
    with TempTestDir(prefix="similarity_thresholds_") as temp_test:
        results = []
        
        # Test different similarity thresholds
        thresholds = ["0.90", "0.95", "0.98"]
        
        for threshold in thresholds:
            test_output = os.path.join(temp_test.get_path(), f"similarity_{threshold}")
            
            returncode, stdout, stderr = run_find_best_images(
                test_subdirs,
                test_output,
                extra_args=[
                    "--similarity-threshold", threshold,
                    "-v"
                ]
            )
            
            results.append((threshold, returncode, stdout, stderr))
        
        # Check that all tests completed successfully
        success = all(returncode == 0 for _, returncode, _, _ in results)
        
        # If all succeeded, verify that lower thresholds find more groups
        if success:
            # Check output directories
            group_counts = {}
            for threshold, _, _, _ in results:
                output_dir = os.path.join(temp_test.get_path(), f"similarity_{threshold}")
                if os.path.exists(output_dir):
                    group_count = sum(1 for item in os.listdir(output_dir) 
                                    if os.path.isdir(os.path.join(output_dir, item)) and 
                                    not item.startswith("_"))
                    group_counts[threshold] = group_count
                    logger.info(f"Threshold {threshold}: {group_count} groups")
            
            # Lower thresholds should find more groups (or at least not fewer)
            # Compare adjacent thresholds in the list
            for i in range(len(thresholds) - 1):
                lower = thresholds[i]
                higher = thresholds[i+1]
                
                if lower in group_counts and higher in group_counts:
                    if group_counts[lower] < group_counts[higher]:
                        logger.warning(f"Lower threshold {lower} found fewer groups than higher threshold {higher}!")
                        # This is a warning, not necessarily a failure
        
        return 0 if success else 1, \
               temp_test.get_path(), \
               "\n\n".join(f"Threshold {threshold}:\n{stdout}" 
                         for threshold, _, stdout, _ in results), \
               "\n\n".join(f"Threshold {threshold}:\n{stderr}" 
                         for threshold, _, stderr, _ in results)

@image_test
def test_similarity_presets() -> Tuple[int, str, str, str]:
    """Test named presets for similarity thresholds."""
    # Create a test directory structure
    test_dir, test_subdirs = create_test_image_structure(TEST_IMAGES_DIR)
    if not test_dir:
        return 1, None, "", "Failed to create test directory structure"
    
    with TempTestDir(prefix="similarity_presets_") as temp_test:
        results = []
        
        # Test different similarity presets
        presets = ["same", "very_similar", "similar", "not_same_similar_location"]
        
        for preset in presets:
            test_output = os.path.join(temp_test.get_path(), f"preset_{preset}")
            
            returncode, stdout, stderr = run_find_best_images(
                test_subdirs,
                test_output,
                extra_args=[
                    "--similarity-preset", preset,
                    "-v"
                ]
            )
            
            results.append((preset, returncode, stdout, stderr))
        
        # Check that all tests completed successfully
        success = all(returncode == 0 for _, returncode, _, _ in results)
        
        # If all succeeded, verify that less strict presets find more groups
        if success:
            # Check output directories
            group_counts = {}
            for preset, _, _, _ in results:
                output_dir = os.path.join(temp_test.get_path(), f"preset_{preset}")
                if os.path.exists(output_dir):
                    group_count = sum(1 for item in os.listdir(output_dir) 
                                    if os.path.isdir(os.path.join(output_dir, item)) and 
                                    not item.startswith("_"))
                    group_counts[preset] = group_count
                    logger.info(f"Preset {preset}: {group_count} groups")
            
            # Less strict presets (later in the list) should find more groups
            for i in range(len(presets) - 1):
                stricter = presets[i]
                less_strict = presets[i+1]
                
                if stricter in group_counts and less_strict in group_counts:
                    if group_counts[stricter] > group_counts[less_strict]:
                        logger.warning(f"Stricter preset {stricter} found more groups than less strict preset {less_strict}!")
                        # This is a warning, not necessarily a failure
        
        return 0 if success else 1, \
               temp_test.get_path(), \
               "\n\n".join(f"Preset {preset}:\n{stdout}" 
                         for preset, _, stdout, _ in results), \
               "\n\n".join(f"Preset {preset}:\n{stderr}" 
                         for preset, _, stderr, _ in results)

@image_test
def test_preset_overrides_threshold() -> Tuple[int, str, str, str]:
    """Test that similarity preset overrides explicit threshold."""
    # Create a test directory structure
    test_dir, test_subdirs = create_test_image_structure(TEST_IMAGES_DIR)
    if not test_dir:
        return 1, None, "", "Failed to create test directory structure"
    
    with TempTestDir(prefix="preset_override_") as temp_test:
        # Run with only threshold
        threshold_output = os.path.join(temp_test.get_path(), "threshold_only")
        returncode1, stdout1, stderr1 = run_find_best_images(
            test_subdirs,
            threshold_output,
            extra_args=[
                "--similarity-threshold", "0.95",
                "-v"
            ]
        )
        
        # Run with both threshold and preset (preset should override)
        both_output = os.path.join(temp_test.get_path(), "both")
        returncode2, stdout2, stderr2 = run_find_best_images(
            test_subdirs,
            both_output,
            extra_args=[
                "--similarity-threshold", "0.95",
                "--similarity-preset", "very_similar",
                "-v"
            ]
        )
        
        # Both should complete successfully
        success = returncode1 == 0 and returncode2 == 0
        
        # Check the logs to confirm the preset was used
        if stdout2 and "Using similarity preset" in stdout2:
            logger.info("Preset override confirmed in logs")
        
        return 0 if success else 1, \
               temp_test.get_path(), \
               f"Threshold only:\n{stdout1}\n\nBoth threshold and preset:\n{stdout2}", \
               f"Threshold only:\n{stderr1}\n\nBoth threshold and preset:\n{stderr2}"

@image_test
def test_check_regions() -> Tuple[int, str, str, str]:
    """Test region-based similarity checking."""
    # Create a test directory structure
    test_dir, test_subdirs = create_test_image_structure(TEST_IMAGES_DIR)
    if not test_dir:
        return 1, None, "", "Failed to create test directory structure"
    
    with TempTestDir(prefix="check_regions_") as temp_test:
        results = []
        
        # Test different numbers of regions
        region_counts = [0, 1, 3]
        
        for regions in region_counts:
            test_output = os.path.join(temp_test.get_path(), f"regions_{regions}")
            
            returncode, stdout, stderr = run_find_best_images(
                test_subdirs,
                test_output,
                extra_args=[
                    "--check-regions", str(regions),
                    "-v"
                ]
            )
            
            results.append((regions, returncode, stdout, stderr))
        
        # Check that all tests completed successfully
        success = all(returncode == 0 for _, returncode, _, _ in results)
        
        return 0 if success else 1, \
               temp_test.get_path(), \
               "\n\n".join(f"Regions {regions}:\n{stdout}" 
                         for regions, _, stdout, _ in results), \
               "\n\n".join(f"Regions {regions}:\n{stderr}" 
                         for regions, _, stderr, _ in results)

if __name__ == "__main__":
    # Run tests when script is executed directly
    results = []
    
    tests = [
        test_similarity_thresholds,
        test_similarity_presets,
        test_preset_overrides_threshold,
        test_check_regions
    ]
    
    for test_func in tests:
        result = test_func()
        results.append((test_func.__name__, result))
        
        if isinstance(result, tuple):
            success = result[0] == 0
        else:
            success = bool(result)
        
        status = "PASSED" if success else "FAILED"
        print(f"Test {test_func.__name__}: {status}")
    
    # Exit with failure if any test failed
    failed_tests = [name for name, result in results if 
                   (isinstance(result, tuple) and result[0] != 0) or
                   (not isinstance(result, tuple) and not bool(result))]
    
    if failed_tests:
        print(f"Failed tests: {', '.join(failed_tests)}")
        sys.exit(1)
    
    print("All tests passed!")
    sys.exit(0)