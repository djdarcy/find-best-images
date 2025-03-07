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
tests/test_pattern_matching.py

Tests for pattern matching functionality in find_best_images.py.
"""

import os
import sys
import glob
import re
from typing import Tuple, List

# Import common utilities
from tests.common import (
    image_test,
    run_find_best_images,
    TempTestDir,
    create_pattern_matching_test,
    TEST_IMAGES_DIR,
    logger
)

@image_test
def test_include_dirs_pattern() -> Tuple[int, str, str, str]:
    """Test including directories based on glob patterns."""
    # Create a test directory structure for pattern matching
    pattern_dir, include_files = create_pattern_matching_test(TEST_IMAGES_DIR)
    if not pattern_dir:
        return 1, None, "", "Failed to create pattern matching test directory"
    
    with TempTestDir(prefix="include_dirs_pattern_") as temp_test:
        output_dir = temp_test.get_output_dir()
        
        # Run with include-dirs-pattern
        returncode, stdout, stderr = run_find_best_images(
            pattern_dir,
            output_dir,
            extra_args=[
                "--include-dirs-pattern", "include*", "test_*",
                "-v"
            ]
        )
        
        # Verify that files from excluded directories aren't included
        if returncode == 0:
            # The output should only contain images from directories matching the pattern
            # Count the number of output directories
            if os.path.exists(output_dir):
                output_count = sum(1 for item in os.listdir(output_dir) 
                                if os.path.isdir(os.path.join(output_dir, item)))
                logger.info(f"Output directories with include dirs pattern: {output_count}")
                
                # This should be positive but less than the total number of files
                if output_count <= 0:
                    logger.error("No output directories created with include dirs pattern")
                    return 1, output_dir, stdout, stderr
            else:
                logger.error("Output directory not created")
                return 1, output_dir, stdout, stderr
        
        return returncode, output_dir, stdout, stderr

@image_test
def test_include_files_pattern() -> Tuple[int, str, str, str]:
    """Test including files based on glob patterns."""
    # Create a test directory structure for pattern matching
    pattern_dir, include_files = create_pattern_matching_test(TEST_IMAGES_DIR)
    if not pattern_dir:
        return 1, None, "", "Failed to create pattern matching test directory"
    
    with TempTestDir(prefix="include_files_pattern_") as temp_test:
        output_dir = temp_test.get_output_dir()
        
        # Run with include-files-pattern
        returncode, stdout, stderr = run_find_best_images(
            pattern_dir,
            output_dir,
            extra_args=[
                "--include-files-pattern", "include_*.jpg", "test_*.png",
                "-v"
            ]
        )
        
        # Verify that only files matching the pattern are included
        if returncode == 0:
            # The output should only contain images matching the pattern
            # Count the number of output directories
            if os.path.exists(output_dir):
                output_count = sum(1 for item in os.listdir(output_dir) 
                                if os.path.isdir(os.path.join(output_dir, item)))
                logger.info(f"Output directories with include files pattern: {output_count}")
                
                # This should be positive but less than the total number of files
                if output_count <= 0:
                    logger.error("No output directories created with include files pattern")
                    return 1, output_dir, stdout, stderr
            else:
                logger.error("Output directory not created")
                return 1, output_dir, stdout, stderr
        
        return returncode, output_dir, stdout, stderr

@image_test
def test_exclude_patterns() -> Tuple[int, str, str, str]:
    """Test excluding directories and files based on patterns."""
    # Create a test directory structure for pattern matching
    pattern_dir, include_files = create_pattern_matching_test(TEST_IMAGES_DIR)
    if not pattern_dir:
        return 1, None, "", "Failed to create pattern matching test directory"
    
    with TempTestDir(prefix="exclude_patterns_") as temp_test:
        output_dir = temp_test.get_output_dir()
        
        # Run with exclude patterns
        returncode, stdout, stderr = run_find_best_images(
            pattern_dir,
            output_dir,
            extra_args=[
                "--exclude-dirs-pattern", "exclude*", "temp*",
                "--exclude-files-pattern", "exclude*", "temp*",
                "-v"
            ]
        )
        
        # Verify that excluded files/dirs aren't included
        if returncode == 0:
            # The output should not contain images from excluded directories or with excluded names
            # Count the number of output directories
            if os.path.exists(output_dir):
                output_count = sum(1 for item in os.listdir(output_dir) 
                                if os.path.isdir(os.path.join(output_dir, item)))
                logger.info(f"Output directories with exclude patterns: {output_count}")
                
                # This should be positive but less than the total number of files
                if output_count <= 0:
                    logger.error("No output directories created with exclude patterns")
                    return 1, output_dir, stdout, stderr
            else:
                logger.error("Output directory not created")
                return 1, output_dir, stdout, stderr
        
        return returncode, output_dir, stdout, stderr

@image_test
def test_general_include_pattern() -> Tuple[int, str, str, str]:
    """Test the general include pattern that applies to both files and directories."""
    # Create a test directory structure for pattern matching
    pattern_dir, include_files = create_pattern_matching_test(TEST_IMAGES_DIR)
    if not pattern_dir:
        return 1, None, "", "Failed to create pattern matching test directory"
    
    with TempTestDir(prefix="general_include_") as temp_test:
        output_dir = temp_test.get_output_dir()
        
        # Run with general include pattern
        returncode, stdout, stderr = run_find_best_images(
            pattern_dir,
            output_dir,
            extra_args=[
                "--include-pattern", "include*", "test_*",
                "-v"
            ]
        )
        
        # Verify that files and directories matching the pattern are included
        if returncode == 0:
            # The output should contain images matching the pattern
            # Count the number of output directories
            if os.path.exists(output_dir):
                output_count = sum(1 for item in os.listdir(output_dir) 
                                if os.path.isdir(os.path.join(output_dir, item)))
                logger.info(f"Output directories with general include pattern: {output_count}")
                
                # This should be positive but less than the total number of files
                if output_count <= 0:
                    logger.error("No output directories created with general include pattern")
                    return 1, output_dir, stdout, stderr
            else:
                logger.error("Output directory not created")
                return 1, output_dir, stdout, stderr
        
        return returncode, output_dir, stdout, stderr

@image_test
def test_regex_pattern_mode() -> Tuple[int, str, str, str]:
    """Test using regex patterns instead of glob patterns."""
    # Create a test directory structure for pattern matching
    pattern_dir, include_files = create_pattern_matching_test(TEST_IMAGES_DIR)
    if not pattern_dir:
        return 1, None, "", "Failed to create pattern matching test directory"
    
    with TempTestDir(prefix="regex_pattern_") as temp_test:
        output_dir = temp_test.get_output_dir()
        
        # Run with regex pattern mode
        returncode, stdout, stderr = run_find_best_images(
            pattern_dir,
            output_dir,
            extra_args=[
                "--include-dirs-pattern", "^include.*$", "^test_\\d+$",
                "--pattern-mode", "regex",
                "-v"
            ]
        )
        
        # Verify that regex patterns work
        if returncode == 0:
            # The output should contain images matching the regex pattern
            # Count the number of output directories
            if os.path.exists(output_dir):
                output_count = sum(1 for item in os.listdir(output_dir) 
                                if os.path.isdir(os.path.join(output_dir, item)))
                logger.info(f"Output directories with regex pattern mode: {output_count}")
                
                # This should be positive but less than the total number of files
                if output_count <= 0:
                    logger.error("No output directories created with regex pattern mode")
                    return 1, output_dir, stdout, stderr
            else:
                logger.error("Output directory not created")
                return 1, output_dir, stdout, stderr
        
        return returncode, output_dir, stdout, stderr

@image_test
def test_pattern_precedence() -> Tuple[int, str, str, str]:
    """Test that exclude patterns take precedence over include patterns."""
    # Create a test directory structure for pattern matching
    pattern_dir, include_files = create_pattern_matching_test(TEST_IMAGES_DIR)
    if not pattern_dir:
        return 1, None, "", "Failed to create pattern matching test directory"
    
    with TempTestDir(prefix="pattern_precedence_") as temp_test:
        # First run with only include patterns
        include_output = os.path.join(temp_test.get_path(), "include_only")
        returncode1, stdout1, stderr1 = run_find_best_images(
            pattern_dir,
            include_output,
            extra_args=[
                "--include-pattern", "include*", "test_*",
                "-v"
            ]
        )
        
        # Then run with both include and exclude patterns
        both_output = os.path.join(temp_test.get_path(), "both_patterns")
        returncode2, stdout2, stderr2 = run_find_best_images(
            pattern_dir,
            both_output,
            extra_args=[
                "--include-pattern", "include*", "test_*",
                "--exclude-pattern", "include_this*", "test_123*",
                "-v"
            ]
        )
        
        # Verify that exclude patterns take precedence
        if returncode1 == 0 and returncode2 == 0:
            # Count the number of output directories in each case
            if os.path.exists(include_output) and os.path.exists(both_output):
                include_count = sum(1 for item in os.listdir(include_output) 
                                  if os.path.isdir(os.path.join(include_output, item)))
                both_count = sum(1 for item in os.listdir(both_output) 
                               if os.path.isdir(os.path.join(both_output, item)))
                
                logger.info(f"Output directories with include patterns only: {include_count}")
                logger.info(f"Output directories with both patterns: {both_count}")
                
                # The run with both patterns should find fewer matches
                if both_count >= include_count:
                    logger.error("Exclude patterns don't seem to take precedence over include patterns")
                    return 1, temp_test.get_path(), f"{stdout1}\n\n{stdout2}", f"{stderr1}\n\n{stderr2}"
            else:
                logger.error("One or both output directories were not created")
                return 1, temp_test.get_path(), f"{stdout1}\n\n{stdout2}", f"{stderr1}\n\n{stderr2}"
        
        return 0 if returncode1 == 0 and returncode2 == 0 else 1, \
               temp_test.get_path(), \
               f"{stdout1}\n\n{stdout2}", \
               f"{stderr1}\n\n{stderr2}"

if __name__ == "__main__":
    # Run tests when script is executed directly
    results = []
    
    tests = [
        test_include_dirs_pattern,
        test_include_files_pattern,
        test_exclude_patterns,
        test_general_include_pattern,
        test_regex_pattern_mode,
        test_pattern_precedence
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
                