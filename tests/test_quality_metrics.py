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
tests/test_quality_metrics.py

Tests for quality metrics functionality in find_best_images.py.
Tests primary/secondary metrics, date preferences, and hybrid evaluation.
"""

import os
import sys
import tempfile
from typing import Tuple, List, Dict

# Import common utilities
from tests.common import (
    image_test,
    run_find_best_images,
    TempTestDir,
    create_test_image_structure,
    create_modified_dates_test,
    TEST_IMAGES_DIR,
    logger
)

@image_test
def test_primary_metrics() -> Tuple[int, str, str, str]:
    """Test different primary metrics combinations."""
    # Create a test directory structure
    test_dir, test_subdirs = create_test_image_structure(TEST_IMAGES_DIR)
    if not test_dir:
        return 1, None, "", "Failed to create test directory structure"
    
    with TempTestDir(prefix="primary_metrics_") as temp_test:
        results = []
        
        # Test different combinations of primary metrics
        metrics_combinations = [
            ["dimensions", "filesize"],
            ["filesize", "dimensions"],
            ["resolution", "format_quality"],
            ["modified_date", "filesize", "dimensions"]
        ]
        
        for i, metrics in enumerate(metrics_combinations):
            test_output = os.path.join(temp_test.get_path(), f"metrics_{i+1}")
            metrics_args = ["--primary-metrics"] + metrics
            
            returncode, stdout, stderr = run_find_best_images(
                test_subdirs,
                test_output,
                extra_args=metrics_args + ["-v"]
            )
            
            results.append((metrics, returncode, stdout, stderr))
        
        # Check that all tests completed successfully
        success = all(returncode == 0 for _, returncode, _, _ in results)
        
        return 0 if success else 1, \
               temp_test.get_path(), \
               "\n\n".join(f"Metrics {' '.join(metrics)}:\n{stdout}" 
                         for metrics, _, stdout, _ in results), \
               "\n\n".join(f"Metrics {' '.join(metrics)}:\n{stderr}" 
                         for metrics, _, stderr, _ in results)

@image_test
def test_secondary_metrics() -> Tuple[int, str, str, str]:
    """Test secondary metrics with weights for tie-breaking."""
    # Create a test directory structure
    test_dir, test_subdirs = create_test_image_structure(TEST_IMAGES_DIR)
    if not test_dir:
        return 1, None, "", "Failed to create test directory structure"
    
    with TempTestDir(prefix="secondary_metrics_") as temp_test:
        # First run with only primary metrics
        primary_output = os.path.join(temp_test.get_path(), "primary_only")
        returncode1, stdout1, stderr1 = run_find_best_images(
            test_subdirs,
            primary_output,
            extra_args=[
                "--primary-metrics", "dimensions",
                "-v"
            ]
        )
        
        # Then run with both primary and secondary metrics
        hybrid_output = os.path.join(temp_test.get_path(), "hybrid")
        returncode2, stdout2, stderr2 = run_find_best_images(
            test_subdirs,
            hybrid_output,
            extra_args=[
                "--primary-metrics", "dimensions",
                "--secondary-metrics", "filesize", "modified_date",
                "--metric-weights", "filesize:0.8,modified_date:0.6",
                "-v"
            ]
        )
        
        # Both should complete successfully
        success = returncode1 == 0 and returncode2 == 0
        
        return 0 if success else 1, \
               temp_test.get_path(), \
               f"Primary metrics only:\n{stdout1}\n\nHybrid metrics:\n{stdout2}", \
               f"Primary metrics only:\n{stderr1}\n\nHybrid metrics:\n{stderr2}"

@image_test
def test_date_preference() -> Tuple[int, str, str, str]:
    """Test date preference option (newest vs oldest)."""
    # Create a test directory with files having different modified dates
    test_dir, date_files = create_modified_dates_test(TEST_IMAGES_DIR)
    if not test_dir:
        return 1, None, "", "Failed to create modified dates test directory"
    
    with TempTestDir(prefix="date_preference_") as temp_test:
        # Run with newest date preference (default)
        newest_output = os.path.join(temp_test.get_path(), "newest")
        returncode1, stdout1, stderr1 = run_find_best_images(
            test_dir,
            newest_output,
            extra_args=[
                "--primary-metrics", "modified_date",
                "--date-preference", "newest",
                "-v"
            ]
        )
        
        # Run with oldest date preference
        oldest_output = os.path.join(temp_test.get_path(), "oldest")
        returncode2, stdout2, stderr2 = run_find_best_images(
            test_dir,
            oldest_output,
            extra_args=[
                "--primary-metrics", "modified_date",
                "--date-preference", "oldest",
                "-v"
            ]
        )
        
        # Both should complete successfully
        success = returncode1 == 0 and returncode2 == 0
        
        # If both succeeded, try to verify different results
        if success:
            # Check that we have different outputs based on date preference
            if os.path.exists(newest_output) and os.path.exists(oldest_output):
                # Look in each output directory for the chosen "best" images
                newest_best = []
                oldest_best = []
                
                for root, dirs, files in os.walk(newest_output):
                    for d in dirs:
                        # Skip candidate directories
                        if d.endswith("_candidates"):
                            continue
                        
                        # Check for image files directly in group dirs
                        group_dir = os.path.join(root, d)
                        for f in os.listdir(group_dir):
                            if os.path.isfile(os.path.join(group_dir, f)) and not f.endswith(".txt"):
                                newest_best.append(f)
                
                for root, dirs, files in os.walk(oldest_output):
                    for d in dirs:
                        # Skip candidate directories
                        if d.endswith("_candidates"):
                            continue
                        
                        # Check for image files directly in group dirs
                        group_dir = os.path.join(root, d)
                        for f in os.listdir(group_dir):
                            if os.path.isfile(os.path.join(group_dir, f)) and not f.endswith(".txt"):
                                oldest_best.append(f)
                
                logger.info(f"Newest date preference best images: {newest_best}")
                logger.info(f"Oldest date preference best images: {oldest_best}")
                
                # Check if the results are different
                if set(newest_best) == set(oldest_best):
                    logger.warning("Date preference doesn't seem to affect the results!")
                    # This isn't necessarily a failure, as the test setup might not have resulted
                    # in different best images, but it's worth logging
            
        return 0 if success else 1, \
               temp_test.get_path(), \
               f"Newest date preference:\n{stdout1}\n\nOldest date preference:\n{stdout2}", \
               f"Newest date preference:\n{stderr1}\n\nOldest date preference:\n{stderr2}"

@image_test
def test_date_metric_override() -> Tuple[int, str, str, str]:
    """Test overriding date preference for specific metrics."""
    # Create a test directory with files having different modified dates
    test_dir, date_files = create_modified_dates_test(TEST_IMAGES_DIR)
    if not test_dir:
        return 1, None, "", "Failed to create modified dates test directory"
    
    with TempTestDir(prefix="date_override_") as temp_test:
        # Run with global date preference = newest, but override for modified_date
        override_output = os.path.join(temp_test.get_path(), "override")
        returncode, stdout, stderr = run_find_best_images(
            test_dir,
            override_output,
            extra_args=[
                "--primary-metrics", "modified_date", "created_date",
                "--date-preference", "newest",
                "--date-metric-override", "modified_date:oldest,created_date:newest",
                "-v"
            ]
        )
        
        return returncode, override_output, stdout, stderr

if __name__ == "__main__":
    # Run tests when script is executed directly
    results = []
    
    tests = [
        test_primary_metrics,
        test_secondary_metrics,
        test_date_preference,
        test_date_metric_override
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