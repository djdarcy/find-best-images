#!/usr/bin/env python3
#
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
tests/common.py

Common utilities and functions for image tool tests.
Provides shared test fixtures, helper functions, and test decorators.
"""

import os
import sys
import shutil
import tempfile
import time
import subprocess
import platform
import logging
import json
from pathlib import Path
from functools import wraps
from typing import List, Dict, Any, Callable, Optional, Tuple, Union

# Ensure parent directory is in path so we can import the main module
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Try to import our module
try:
    import imagetools as cit
except ImportError:
    print("Error: imagetools module not found. Make sure it's in the correct location.")
    sys.exit(1)

# Constants
SCRIPT_NAME = "find_best_images.py"
VALIDATION_SCRIPT = "validate_test_results.py"
TEST_IMAGES_DIR = os.path.join(parent_dir, "test_materials_2025.03.04")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("image_tests")

def print_header(message: str) -> str:
    """Print a formatted header for test sections."""
    header = "\n" + "=" * 80 + f"\n {message}\n" + "=" * 80
    print(header)
    return header

def run_command(cmd: List[str], verbose: bool = True, capture_output: bool = True) -> Tuple[int, str, str]:
    """Run a shell command and return the result."""
    if verbose:
        print(f"\nRunning command: {' '.join(cmd)}")
    
    start_time = time.time()
    
    if capture_output:
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        returncode = process.returncode
    else:
        process = subprocess.run(cmd)
        stdout, stderr = "", ""
        returncode = process.returncode
        
    elapsed_time = time.time() - start_time
    
    if verbose and capture_output:
        print(f"Command completed in {elapsed_time:.2f} seconds with exit code {returncode}")
        
        if stdout:
            print("\nSTDOUT:")
            print(stdout[:1000] + ("..." if len(stdout) > 1000 else ""))
        
        if stderr:
            print("\nSTDERR:")
            print(stderr[:1000] + ("..." if len(stderr) > 1000 else ""))
    
    return returncode, stdout, stderr

def ensure_test_directory(test_dir: str = TEST_IMAGES_DIR) -> bool:
    """Ensure the test directory exists with test images."""
    # Convert to absolute path
    test_dir = os.path.abspath(test_dir)
    
    if os.path.exists(test_dir) and os.path.isdir(test_dir):
        # Count the number of image files
        image_count = 0
        for root, _, files in os.walk(test_dir):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp')):
                    image_count += 1
        
        logger.info(f"Found {image_count} images in test directory: {test_dir}")
        if image_count > 0:
            return True
    
    logger.error(f"Test directory {test_dir} doesn't exist or doesn't have images.")
    return False

class TempTestDir:
    """Context manager for creating and cleaning up temporary test directories."""
    def __init__(self, prefix: str = "find_best_images_test_", keep_files: bool = False):
        self.prefix = prefix
        self.keep_files = keep_files
        self.temp_dir = None
        self.subdirs = []
    
    def __enter__(self) -> 'TempTestDir':
        self.temp_dir = tempfile.mkdtemp(prefix=self.prefix)
        logger.debug(f"Created temporary directory: {self.temp_dir}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.keep_files and self.temp_dir:
            try:
                shutil.rmtree(self.temp_dir)
                logger.debug(f"Removed temporary directory: {self.temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary directory {self.temp_dir}: {e}")
    
    def create_subdir(self, name: str) -> str:
        """Create a subdirectory within the temporary directory."""
        subdir = os.path.join(self.temp_dir, name)
        os.makedirs(subdir, exist_ok=True)
        self.subdirs.append(subdir)
        return subdir
    
    def get_output_dir(self) -> str:
        """Get a path for an output directory within the temporary directory."""
        output_dir = os.path.join(self.temp_dir, "output")
        return output_dir
    
    def get_path(self) -> str:
        """Get the path to the temporary directory."""
        return self.temp_dir

def create_test_image_structure(test_dir: str = TEST_IMAGES_DIR, num_variants: int = 3) -> Tuple[str, List[str]]:
    """Create a test directory structure with variant images."""
    with TempTestDir(prefix="find_best_images_test_struct_") as temp_test:
        # Create subdirectories
        dir1 = temp_test.create_subdir("dir1")
        dir2 = temp_test.create_subdir("dir2")
        dir3 = os.path.join(temp_test.get_path(), "dir3", "subdir")
        os.makedirs(dir3, exist_ok=True)
        
        # Find test files to use as source
        test_files = []
        for root, _, files in os.walk(test_dir):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp')):
                    test_files.append(os.path.join(root, file))
        
        if not test_files:
            logger.error(f"No test images found in {test_dir}")
            return None, []
        
        logger.info(f"Found {len(test_files)} test images")
        
        # Create variants of test files with slight modifications
        test_groups = []
        processed_files = []
        
        try:
            # Create duplicates with variations for testing
            for src_file in test_files[:min(5, len(test_files))]:  # Use up to 5 source images
                group_files = []
                
                # Create variants with different sizes, formats, and names
                from PIL import Image
                with Image.open(src_file) as img:
                    base_name = os.path.splitext(os.path.basename(src_file))[0]
                    
                    # Original file
                    dest_path = os.path.join(dir1, os.path.basename(src_file))
                    shutil.copy2(src_file, dest_path)
                    group_files.append(dest_path)
                    processed_files.append(dest_path)
                    
                    # Resized smaller variant
                    smaller = img.resize((img.width // 2, img.height // 2))
                    small_path = os.path.join(dir2, f"{base_name}_small.jpg")
                    smaller.save(small_path, "JPEG", quality=85)
                    group_files.append(small_path)
                    processed_files.append(small_path)
                    
                    # PNG variant
                    png_path = os.path.join(dir2, f"{base_name}.png")
                    img.save(png_path, "PNG")
                    group_files.append(png_path)
                    processed_files.append(png_path)
                    
                    # Another variant with different name in dir3
                    renamed_path = os.path.join(dir3, f"variant_{base_name}.jpg")
                    shutil.copy2(src_file, renamed_path)
                    group_files.append(renamed_path)
                    processed_files.append(renamed_path)
                
                test_groups.append(group_files)
        
        except Exception as e:
            logger.error(f"Error creating test variants: {e}")
            return temp_test.get_path(), [dir1, dir2, dir3]
        
        # Also include some singleton files (no duplicates)
        try:
            for i, src_file in enumerate(test_files[5:10]):
                dest_dir = [dir1, dir2, dir3][i % 3]
                dest_path = os.path.join(dest_dir, f"unique_{i}_{os.path.basename(src_file)}")
                shutil.copy2(src_file, dest_path)
                processed_files.append(dest_path)
        except Exception as e:
            logger.error(f"Error creating singleton files: {e}")
        
        logger.info(f"Created test structure with {len(processed_files)} total files in {len(test_groups)} groups")
        # Set keep_files to True to prevent cleanup when exiting the context manager
        temp_test.keep_files = True
        return temp_test.get_path(), [dir1, dir2, dir3]

def create_long_path_test(test_dir: str = TEST_IMAGES_DIR) -> Tuple[str, List[str]]:
    """Create a test directory with very long paths."""
    with TempTestDir(prefix="find_best_images_longpath_") as temp_test:
        # Create a deeply nested directory structure
        long_dir = os.path.join(temp_test.get_path(), "a" * 30, "b" * 30, "c" * 30)
        os.makedirs(long_dir, exist_ok=True)
        
        # Find test files
        test_files = []
        for root, _, files in os.walk(test_dir):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp')):
                    test_files.append(os.path.join(root, file))
                    if len(test_files) >= 5:  # We only need a few files
                        break
            if len(test_files) >= 5:
                break
        
        if not test_files:
            logger.error(f"No test images found in {test_dir}")
            return None, []
        
        # Copy files with long names
        long_files = []
        try:
            for i, src_file in enumerate(test_files):
                name, ext = os.path.splitext(os.path.basename(src_file))
                long_name = f"{name}_{'x' * (50 - len(name))}{ext}"
                dest_path = os.path.join(long_dir, long_name)
                shutil.copy2(src_file, dest_path)
                long_files.append(dest_path)
                logger.debug(f"Created long path file: {dest_path}")
        except Exception as e:
            logger.error(f"Error creating long path files: {e}")
        
        # Set keep_files to True to prevent cleanup
        temp_test.keep_files = True
        return temp_test.get_path(), long_files

def create_modified_dates_test(test_dir: str = TEST_IMAGES_DIR) -> Tuple[str, List[str]]:
    """Create a test directory with files having different modified dates."""
    with TempTestDir(prefix="find_best_images_dates_") as temp_test:
        dates_dir = temp_test.create_subdir("different_dates")
        
        # Find test files
        test_files = []
        for root, _, files in os.walk(test_dir):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp')):
                    test_files.append(os.path.join(root, file))
                    if len(test_files) >= 3:  # We only need a few files
                        break
            if len(test_files) >= 3:
                break
        
        if not test_files:
            logger.error(f"No test images found in {test_dir}")
            return None, []
        
        date_files = []
        # Create variants with different dates
        try:
            current_time = time.time()
            for i, src_file in enumerate(test_files):
                name, ext = os.path.splitext(os.path.basename(src_file))
                
                # Create several copies with different timestamps
                for j in range(3):
                    variant_name = f"{name}_variant{j}{ext}"
                    dest_path = os.path.join(dates_dir, variant_name)
                    shutil.copy2(src_file, dest_path)
                    
                    # Set different modification times
                    new_time = current_time - (86400 * (1 + j * 7))  # 1 day, 1 week, 1 month ago
                    os.utime(dest_path, (new_time, new_time))
                    date_files.append(dest_path)
                    
                    logger.debug(f"Created {dest_path} with modified time {time.ctime(new_time)}")
        except Exception as e:
            logger.error(f"Error creating date variant files: {e}")
        
        # Set keep_files to True to prevent cleanup
        temp_test.keep_files = True
        return temp_test.get_path(), date_files

def create_pattern_matching_test(test_dir: str = TEST_IMAGES_DIR) -> Tuple[str, List[str]]:
    """Create a test directory structure for pattern matching."""
    with TempTestDir(prefix="find_best_images_patterns_") as temp_test:
        # Create directory structure with various patterns
        patterns_dir = temp_test.get_path()
        
        # Create directories with different naming patterns
        include_dirs = [
            "include_this_dir",
            "include_me_too",
            "include_nested",
            "test_123",
            "test_456",
            "img_dir"
        ]
        
        exclude_dirs = [
            "exclude_this_dir",
            "temp",
            "backup_files",
            "exclude_me"
        ]
        
        # Create all directories
        for d in include_dirs + exclude_dirs:
            os.makedirs(os.path.join(patterns_dir, d), exist_ok=True)
        
        # Create a nested structure
        os.makedirs(os.path.join(patterns_dir, "include_nested", "level1", "level2"), exist_ok=True)
        os.makedirs(os.path.join(patterns_dir, "exclude_this_dir", "hidden_include"), exist_ok=True)
        
        # Find test files
        test_files = []
        for root, _, files in os.walk(test_dir):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp')):
                    test_files.append(os.path.join(root, file))
        
        if not test_files:
            logger.error(f"No test images found in {test_dir}")
            return None, []
        
        # Copy files with different naming patterns
        processed_files = []
        try:
            # Files to include
            include_patterns = [
                "include_image_{}.jpg",
                "test_photo_{}.png",
                "img_{}_final.jpg"
            ]
            
            # Files to exclude
            exclude_patterns = [
                "exclude_this_{}.jpg",
                "temp_{}.png",
                "backup_{}.jpg"
            ]
            
            # Distribute test images across directories with different names
            file_index = 0
            for dir_name in include_dirs:
                dir_path = os.path.join(patterns_dir, dir_name)
                
                # Add include pattern files
                for pattern in include_patterns:
                    if file_index < len(test_files):
                        dest_name = pattern.format(file_index)
                        dest_path = os.path.join(dir_path, dest_name)
                        shutil.copy2(test_files[file_index], dest_path)
                        processed_files.append(dest_path)
                        file_index = (file_index + 1) % len(test_files)
                
                # Add exclude pattern files
                for pattern in exclude_patterns:
                    if file_index < len(test_files):
                        dest_name = pattern.format(file_index)
                        dest_path = os.path.join(dir_path, dest_name)
                        shutil.copy2(test_files[file_index], dest_path)
                        file_index = (file_index + 1) % len(test_files)
            
            # Also add files to nested directories
            nested_dir = os.path.join(patterns_dir, "include_nested", "level1", "level2")
            for i in range(3):
                if file_index < len(test_files):
                    dest_name = f"nested_file_{i}.jpg"
                    dest_path = os.path.join(nested_dir, dest_name)
                    shutil.copy2(test_files[file_index], dest_path)
                    processed_files.append(dest_path)
                    file_index = (file_index + 1) % len(test_files)
            
            # Add some files to excluded directories
            hidden_dir = os.path.join(patterns_dir, "exclude_this_dir", "hidden_include")
            for i in range(2):
                if file_index < len(test_files):
                    dest_name = f"hidden_file_{i}.jpg"
                    dest_path = os.path.join(hidden_dir, dest_name)
                    shutil.copy2(test_files[file_index], dest_path)
                    file_index = (file_index + 1) % len(test_files)
            
        except Exception as e:
            logger.error(f"Error creating pattern matching test files: {e}")
        
        logger.info(f"Created pattern matching test with {len(processed_files)} include-pattern files")
        
        # Set keep_files to True to prevent cleanup
        temp_test.keep_files = True
        return patterns_dir, processed_files


class TestResult:
    """Container for test results."""
    def __init__(self, name: str, success: bool, output_dir: Optional[str] = None,
                returncode: int = 0, stdout: str = "", stderr: str = "",
                details: Dict[str, Any] = None):
        self.name = name
        self.success = success
        self.output_dir = output_dir
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.details = details or {}
        self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert test result to dictionary."""
        return {
            "name": self.name,
            "success": self.success,
            "output_dir": self.output_dir,
            "returncode": self.returncode,
            "stdout_length": len(self.stdout),
            "stderr_length": len(self.stderr),
            "details": self.details,
            "timestamp": self.timestamp,
            "time": time.ctime(self.timestamp)
        }
    
    def __str__(self) -> str:
        """String representation of test result."""
        status = "PASSED" if self.success else "FAILED"
        return f"Test {self.name}: {status} (returncode={self.returncode})"

from functools import wraps

def image_test(name: str = None):
    """Decorator for image tests that supports an optional custom test name."""
    def decorator(test_func):
        # Compute the test name once, using the provided name or defaulting to the function's __name__
        computed_test_name = name if name is not None else test_func.__name__
        
        @wraps(test_func)
        def wrapper(*args, **kwargs):
            print_header(f"Running test: {computed_test_name}")
            
            try:
                # Run the test function
                result = test_func(*args, **kwargs)
                
                # If the test returns a TestResult, return it directly
                if isinstance(result, TestResult):
                    return result
                
                # Otherwise, convert the result to a TestResult
                if isinstance(result, tuple) and len(result) >= 1:
                    returncode = result[0]
                    output_dir = result[1] if len(result) > 1 else None
                    stdout = result[2] if len(result) > 2 else ""
                    stderr = result[3] if len(result) > 3 else ""
                    success = (returncode == 0)
                    return TestResult(computed_test_name, success, output_dir, returncode, stdout, stderr)
                
                # If result is just a boolean, create a simple TestResult
                if isinstance(result, bool):
                    return TestResult(computed_test_name, result)
                
                # Default to success if the test completed without error
                return TestResult(computed_test_name, True)
            
            except Exception as e:
                logger.exception(f"Error running test {computed_test_name}: {e}")
                return TestResult(computed_test_name, False, details={"error": str(e)})
        
        # Store the original function for documentation and attach the test name
        wrapper.original_func = test_func
        wrapper.test_name = computed_test_name
        return wrapper
    
    # Handle the case where the decorator is used without parameters
    if callable(name):
        func = name
        name = None
        return decorator(func)
    
    return decorator


def validate_test_output(test_dir: str, verbose: int = 0) -> Tuple[bool, str]:
    """Validate test output using the validation script."""
    if not os.path.exists(test_dir):
        logger.error(f"Test directory {test_dir} does not exist")
        return False, "Test directory does not exist"
    
    # Run validation script
    validation_script = os.path.join(parent_dir, VALIDATION_SCRIPT)
    if not os.path.exists(validation_script):
        logger.error(f"Validation script {validation_script} not found")
        return False, "Validation script not found"
    
    cmd = [
        sys.executable,
        validation_script,
        test_dir,
        "-v" * verbose
    ]
    
    returncode, stdout, stderr = run_command(cmd)
    return returncode == 0, stdout

def run_find_best_images(
    input_dirs: Union[str, List[str]],
    output_dir: str,
    script_path: str = SCRIPT_NAME,
    extra_args: List[str] = None,
    verbose: bool = True
) -> Tuple[int, str, str]:
    """Run find_best_images.py with the specified arguments."""
    script_path = os.path.join(parent_dir, script_path)
    if not os.path.exists(script_path):
        logger.error(f"Script {script_path} not found")
        return 1, "", f"Script {script_path} not found"
    
    # Ensure input_dirs is a list
    if isinstance(input_dirs, str):
        input_dirs = [input_dirs]
    
    # Build command
    cmd = [sys.executable, script_path]
    
    # Add input directories
    for input_dir in input_dirs:
        cmd.extend(["-i", input_dir])
    
    # Add output directory
    cmd.extend(["-o", output_dir])
    
    # Add extra arguments
    if extra_args:
        cmd.extend(extra_args)
    
    # Run command
    return run_command(cmd, verbose=verbose)

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
                long_name = f"{'very_long_name_' * 5}_{3}.jpg"  # Creates a long filename
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
            
            return temp_test.get_path(), [dir1, dir2, dir3]
        except Exception as e:
            logger.error(f"Error creating collision test structure: {e}")
            return None, []
