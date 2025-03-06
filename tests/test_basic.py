#!/usr/bin/env python3
"""
tests/test_basic.py

Basic functionality tests for find_best_images.py.
Tests core features and error handling.
"""

import os
import sys
import tempfile
from typing import Tuple

# Import common utilities
from tests.common import (
    image_test,
    run_find_best_images,
    TempTestDir,
    ensure_test_directory,
    TEST_IMAGES_DIR,
    logger
)

@image_test
def test_basic_functionality() -> Tuple[int, str, str, str]:
    """Test the basic functionality with default parameters."""
    # Ensure test directory exists
    if not ensure_test_directory(TEST_IMAGES_DIR):
        return 1, None, "", "Test directory not found"
    
    with TempTestDir(prefix="basic_test_") as temp_test:
        output_dir = temp_test.get_output_dir()
        
        # Run with default parameters
        returncode, stdout, stderr = run_find_best_images(
            TEST_IMAGES_DIR,
            output_dir,
            extra_args=["-v"]
        )
        
        return returncode, output_dir, stdout, stderr

@image_test
def test_recursive_option() -> Tuple[int, str, str, str]:
    """Test the recursive vs non-recursive options."""
    # Ensure test directory exists
    if not ensure_test_directory(TEST_IMAGES_DIR):
        return 1, None, "", "Test directory not found"
    
    with TempTestDir(prefix="recursive_test_") as temp_test:
        # Run with recursive option (default)
        recursive_output = os.path.join(temp_test.get_path(), "recursive")
        returncode_recursive, stdout_recursive, stderr_recursive = run_find_best_images(
            TEST_IMAGES_DIR,
            recursive_output,
            extra_args=["-r", "-v"]
        )
        
        # Run with non-recursive option
        nonrecursive_output = os.path.join(temp_test.get_path(), "nonrecursive")
        returncode_nonrecursive, stdout_nonrecursive, stderr_nonrecursive = run_find_best_images(
            TEST_IMAGES_DIR,
            nonrecursive_output,
            extra_args=["--no-recursive", "-v"]
        )
        
        # Verify different results between recursive and non-recursive
        if returncode_recursive == 0 and returncode_nonrecursive == 0:
            # Count the number of output directories in each case
            recursive_count = sum(1 for item in os.listdir(recursive_output) 
                                if os.path.isdir(os.path.join(recursive_output, item)))
            nonrecursive_count = sum(1 for item in os.listdir(nonrecursive_output) 
                                   if os.path.isdir(os.path.join(nonrecursive_output, item)))
            
            logger.info(f"Recursive directories: {recursive_count}")
            logger.info(f"Non-recursive directories: {nonrecursive_count}")
            
            # We expect recursive to find more images
            if recursive_count <= nonrecursive_count:
                logger.warning("Recursive search did not find more directories than non-recursive!")
                return 1, temp_test.get_path(), stdout_recursive, stderr_recursive
        
        return 0 if returncode_recursive == 0 and returncode_nonrecursive == 0 else 1, \
               temp_test.get_path(), \
               f"{stdout_recursive}\n\n{stdout_nonrecursive}", \
               f"{stderr_recursive}\n\n{stderr_nonrecursive}"

@image_test
def test_error_handling() -> Tuple[int, str, str, str]:
    """Test error handling for various scenarios."""
    with TempTestDir(prefix="error_test_") as temp_test:
        results = []
        
        # Test 1: Non-existent input directory
        nonexistent_output = os.path.join(temp_test.get_path(), "nonexistent")
        returncode1, stdout1, stderr1 = run_find_best_images(
            "this_directory_does_not_exist",
            nonexistent_output,
            extra_args=["-v"]
        )
        results.append(("nonexistent_input", returncode1, stdout1, stderr1))
        
        # Test 2: Output directory exists without --force
        existing_output = tempfile.mkdtemp(dir=temp_test.get_path(), prefix="existing_output_")
        returncode2, stdout2, stderr2 = run_find_best_images(
            TEST_IMAGES_DIR,
            existing_output,
            extra_args=["-v"]
        )
        results.append(("existing_output", returncode2, stdout2, stderr2))
        
        # Test 3: Output directory exists with --force
        returncode3, stdout3, stderr3 = run_find_best_images(
            TEST_IMAGES_DIR,
            existing_output,
            extra_args=["--force", "-v"]
        )
        results.append(("existing_output_force", returncode3, stdout3, stderr3))
        
        # Check results
        # Nonexistent input should fail
        if returncode1 == 0:
            logger.error("Test with nonexistent input directory should have failed!")
            return 1, temp_test.get_path(), stdout1, stderr1
        
        # Existing output without --force should fail
        if returncode2 == 0:
            logger.error("Test with existing output directory without --force should have failed!")
            return 1, temp_test.get_path(), stdout2, stderr2
        
        # Existing output with --force should succeed
        if returncode3 != 0:
            logger.error("Test with existing output directory with --force should have succeeded!")
            return 1, temp_test.get_path(), stdout3, stderr3
        
        return 0, temp_test.get_path(), \
               "\n\n".join(f"Test {name}:\n{stdout}" for name, _, stdout, _ in results), \
               "\n\n".join(f"Test {name}:\n{stderr}" for name, _, _, stderr in results)

@image_test
def test_dryrun_mode() -> Tuple[int, str, str, str]:
    """Test the dryrun mode to ensure it doesn't create files."""
    # Ensure test directory exists
    if not ensure_test_directory(TEST_IMAGES_DIR):
        return 1, None, "", "Test directory not found"
    
    with TempTestDir(prefix="dryrun_test_") as temp_test:
        output_dir = os.path.join(temp_test.get_path(), "dryrun_output")
        
        # Run in dryrun mode
        returncode, stdout, stderr = run_find_best_images(
            TEST_IMAGES_DIR,
            output_dir,
            extra_args=["--dryrun", "-v"]
        )
        
        # Check that no files were created (except maybe the output directory itself)
        if os.path.exists(output_dir) and os.path.isdir(output_dir):
            items = os.listdir(output_dir)
            if items:
                logger.error(f"Dryrun mode created files: {items}")
                return 1, output_dir, stdout, stderr
        
        return returncode, output_dir, stdout, stderr

if __name__ == "__main__":
    # Run tests when script is executed directly
    results = []
    
    tests = [
        test_basic_functionality,
        test_recursive_option,
        test_error_handling,
        test_dryrun_mode
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