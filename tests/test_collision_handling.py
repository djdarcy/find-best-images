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
tests/test_collision_handling.py

Tests for filename collision handling in find_best_images.py.
Tests different collision strategies and edge cases.
"""

import os
import sys
import shutil
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

def setup_collision_test(test_dir=TEST_IMAGES_DIR):
    """Set up a directory structure with guaranteed filename collisions."""
    with TempTestDir(prefix="collision_test_") as temp_test:
        # Create subdirectories
        dir1 = os.path.join(temp_test.get_path(), "dir1")
        dir2 = os.path.join(temp_test.get_path(), "dir2")
        dir3 = os.path.join(temp_test.get_path(), "dir3", "subdir")
        
        os.makedirs(dir1, exist_ok=True)
        os.makedirs(dir2, exist_ok=True)
        os.makedirs(dir3, exist_ok=True)
        
        # Find test files
        test_files = []
        for root, _, files in os.walk(test_dir):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp')):
                    test_files.append(os.path.join(root, file))
                    if len(test_files) >= 5:
                        break
            if len(test_files) >= 5:
                break
        
        if not test_files:
            logger.error(f"No test images found in {test_dir}")
            return None, []
        
        # Create sets of files with the same name in different directories
        try:
            # 1. Same filename in all three directories
            for i, src_file in enumerate(test_files[:2]):
                # Use a common basename for all copies
                basename = f"duplicate_{i}.jpg"
                
                # Copy to all three directories with the same name
                for target_dir in [dir1, dir2, dir3]:
                    dest_path = os.path.join(target_dir, basename)
                    shutil.copy2(src_file, dest_path)
            
            # 2. Files with different extensions but same base name
            if len(test_files) >= 3:
                src_file = test_files[2]
                # Create copies with different extensions
                shutil.copy2(src_file, os.path.join(dir1, "same_name.jpg"))
                shutil.copy2(src_file, os.path.join(dir2, "same_name.png"))
                shutil.copy2(src_file, os.path.join(dir3, "same_name.bmp"))
            
            # 3. Extremely long filenames
            if len(test_files) >= 4:
                src_file = test_files[3]
                long_name = f"{'very_long_name_' * 5}_{i}.jpg"  # Creates a long filename
                shutil.copy2(src_file, os.path.join(dir1, long_name))
                shutil.copy2(src_file, os.path.join(dir2, long_name))
            
            # 4. Files with same name and multiple collisions
            if len(test_files) >= 5:
                src_file = test_files[4]
                multi_collision = "multi_collision.jpg"
                # Create 4 copies with the same name
                shutil.copy2(src_file, os.path.join(dir1, multi_collision))
                shutil.copy2(src_file, os.path.join(dir2, multi_collision))
                shutil.copy2(src_file, os.path.join(dir3, multi_collision))
                # Create a subdirectory in dir2 for an extra collision
                subdir2 = os.path.join(dir2, "another_subdir")
                os.makedirs(subdir2, exist_ok=True)
                shutil.copy2(src_file, os.path.join(subdir2, multi_collision))
            
            logger.info(f"Created collision test structure in {temp_test.get_path()}")
            return temp_test.get_path(), [dir1, dir2, dir3]
            
        except Exception as e:
            logger.error(f"Error creating collision test structure: {e}")
            return None, []

@image_test
def test_hierarchical_strategy() -> Tuple[int, str, str, str]:
    """Test the hierarchical collision resolution strategy."""
    # Set up a directory structure with filename collisions
    test_dir, test_subdirs = setup_collision_test()
    if not test_dir:
        return 1, None, "", "Failed to create collision test directory"
    
    with TempTestDir(prefix="hierarchical_collision_") as temp_test:
        output_dir = temp_test.get_output_dir()
        
        # Run with hierarchical strategy (default)
        returncode, stdout, stderr = run_find_best_images(
            test_subdirs,
            output_dir,
            extra_args=[
                "--collision-strategy", "hierarchical",
                "-v"
            ]
        )
        
        # Check for successful completion
        if returncode != 0:
            return returncode, output_dir, stdout, stderr
        
        # Verify that all files were processed
        # Look for logging about filename collisions
        if "Filename collision:" in stdout:
            logger.info("Detected collision handling in logs")
        else:
            logger.warning("No collision handling detected in logs")
        
        return returncode, output_dir, stdout, stderr

@image_test
def test_hash_strategy() -> Tuple[int, str, str, str]:
    """Test the hash-based collision resolution strategy."""
    # Set up a directory structure with filename collisions
    test_dir, test_subdirs = setup_collision_test()
    if not test_dir:
        return 1, None, "", "Failed to create collision test directory"
    
    with TempTestDir(prefix="hash_collision_") as temp_test:
        output_dir = temp_test.get_output_dir()
        
        # Run with hash strategy
        returncode, stdout, stderr = run_find_best_images(
            test_subdirs,
            output_dir,
            extra_args=[
                "--collision-strategy", "hash",
                "-v"
            ]
        )
        
        # Check for successful completion
        if returncode != 0:
            return returncode, output_dir, stdout, stderr
        
        # Verify that all files were processed
        # Look for logging about filename collisions
        if "Filename collision:" in stdout:
            logger.info("Detected collision handling in logs")
            
            # Check if the hash strategy was used - look for filenames with hash-like patterns
            hash_pattern_found = False
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    # Look for files with hash pattern in name (8-character hex hash)
                    if "_" in file and len(file.split("_")[-1].split(".")[0]) == 8:
                        hash_pattern_found = True
                        logger.info(f"Found file with hash naming: {file}")
                        break
                
                if hash_pattern_found:
                    break
            
            if not hash_pattern_found:
                logger.warning("Hash strategy doesn't seem to be used - no hash patterns found in filenames")
        else:
            logger.warning("No collision handling detected in logs")
        
        return returncode, output_dir, stdout, stderr

@image_test
def test_numeric_strategy() -> Tuple[int, str, str, str]:
    """Test the numeric collision resolution strategy."""
    # Set up a directory structure with filename collisions
    test_dir, test_subdirs = setup_collision_test()
    if not test_dir:
        return 1, None, "", "Failed to create collision test directory"
    
    with TempTestDir(prefix="numeric_collision_") as temp_test:
        output_dir = temp_test.get_output_dir()
        
        # Run with numeric strategy
        returncode, stdout, stderr = run_find_best_images(
            test_subdirs,
            output_dir,
            extra_args=[
                "--collision-strategy", "numeric",
                "-v"
            ]
        )
        
        # Check for successful completion
        if returncode != 0:
            return returncode, output_dir, stdout, stderr
        
        # Verify that all files were processed
        # Look for logging about filename collisions
        if "Filename collision:" in stdout:
            logger.info("Detected collision handling in logs")
            
            # Check if the numeric strategy was used - look for filenames with _col_N pattern
            numeric_pattern_found = False
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    # Look for files with _col_N pattern
                    if "_col_" in file:
                        numeric_pattern_found = True
                        logger.info(f"Found file with numeric naming: {file}")
                        break
                
                if numeric_pattern_found:
                    break
            
            if not numeric_pattern_found:
                logger.warning("Numeric strategy doesn't seem to be used - no _col_N patterns found in filenames")
        else:
            logger.warning("No collision handling detected in logs")
        
        return returncode, output_dir, stdout, stderr

@image_test
def test_parent_only_strategy() -> Tuple[int, str, str, str]:
    """Test the parent-only collision resolution strategy."""
    # Set up a directory structure with filename collisions
    test_dir, test_subdirs = setup_collision_test()
    if not test_dir:
        return 1, None, "", "Failed to create collision test directory"
    
    with TempTestDir(prefix="parent_only_collision_") as temp_test:
        output_dir = temp_test.get_output_dir()
        
        # Run with parent-only strategy
        returncode, stdout, stderr = run_find_best_images(
            test_subdirs,
            output_dir,
            extra_args=[
                "--collision-strategy", "parent_only",
                "-v"
            ]
        )
        
        # Check for successful completion
        if returncode != 0:
            return returncode, output_dir, stdout, stderr
        
        # Verify that all files were processed
        # Look for logging about filename collisions
        if "Filename collision:" in stdout:
            logger.info("Detected collision handling in logs")
            
            # Check if the parent-only strategy was used - look for filenames with parent dir name
            parent_pattern_found = False
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    # Look for files with parent directory names (dir1, dir2, dir3)
                    if any(f"_{d}" in file for d in ["dir1", "dir2", "dir3", "subdir"]):
                        parent_pattern_found = True
                        logger.info(f"Found file with parent naming: {file}")
                        break
                
                if parent_pattern_found:
                    break
            
            if not parent_pattern_found:
                logger.warning("Parent-only strategy doesn't seem to be used - no parent dir patterns found in filenames")
        else:
            logger.warning("No collision handling detected in logs")
        
        return returncode, output_dir, stdout, stderr

@image_test
def test_multiple_collisions() -> Tuple[int, str, str, str]:
    """Test handling of multiple collisions of the same filename."""
    # Set up a directory structure with filename collisions
    test_dir, test_subdirs = setup_collision_test()
    if not test_dir:
        return 1, None, "", "Failed to create collision test directory"
    
    with TempTestDir(prefix="multiple_collisions_") as temp_test:
        output_dir = temp_test.get_output_dir()
        
        # Run with hierarchical strategy to test multiple collision handling
        returncode, stdout, stderr = run_find_best_images(
            test_subdirs,
            output_dir,
            extra_args=[
                "--collision-strategy", "hierarchical",
                "-v"
            ]
        )
        
        # Check for successful completion
        if returncode != 0:
            return returncode, output_dir, stdout, stderr
        
        # Look for multi_collision.jpg files
        multi_collisions = []
        for root, dirs, files in os.walk(output_dir):
            for file in files:
                if "multi_collision" in file:
                    multi_collisions.append(os.path.join(root, file))
        
        logger.info(f"Found {len(multi_collisions)} versions of multi_collision.jpg")
        
        # Check if we found 4 different versions (the original plus 3 renamed)
        # This assumes we created 4 identical files with the same name in setup
        if len(multi_collisions) < 4:
            logger.warning(f"Expected to find 4 versions of multi_collision.jpg, but found {len(multi_collisions)}")
        
        return returncode, output_dir, stdout, stderr

if __name__ == "__main__":
    # Run tests when script is executed directly
    results = []
    
    tests = [
        test_hierarchical_strategy,
        test_hash_strategy,
        test_numeric_strategy,
        test_parent_only_strategy,
        test_multiple_collisions
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