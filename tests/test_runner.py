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
tests/test_runner.py

Main test runner script that discovers and executes tests for find_best_images.py.
"""

import os
import sys
import argparse
import importlib
import inspect
import json
import time
import logging
from typing import List, Dict, Any, Callable, Set, Tuple

# Ensure parent directory is in path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Make tests directory available for direct imports
tests_dir = os.path.dirname(os.path.abspath(__file__))
if tests_dir not in sys.path:
    sys.path.insert(0, tests_dir)

# Import common utilities - use direct import to avoid circular dependencies
from common import TestResult, print_header, ensure_test_directory, logger
sys.path.insert(0, parent_dir)

def discover_tests(test_dir: str = None) -> Dict[str, List[Callable]]:
    """
    Discover all test functions in the tests directory.
    
    Args:
        test_dir: Directory containing test modules (default: directory of this script)
        
    Returns:
        Dictionary mapping module names to lists of test functions
    """
    if test_dir is None:
        test_dir = os.path.dirname(os.path.abspath(__file__))
    
    test_modules = {}
    
    # Find all Python files in the test directory
    for filename in os.listdir(test_dir):
        if filename.startswith("test_") and filename.endswith(".py") and filename != "test_runner.py":
            module_name = filename[:-3]  # Remove .py extension
            
            try:
                # Try different import approaches
                try:
                    # Try direct import
                    module = importlib.import_module(module_name)
                except ImportError:
                    try:
                        # Try with tests prefix
                        module = importlib.import_module(f"tests.{module_name}")
                    except ImportError:
                        # Try fully qualified path
                        spec = importlib.util.spec_from_file_location(
                            module_name, os.path.join(test_dir, filename))
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                
                # Find all test functions in the module
                test_functions = []
                for name, obj in inspect.getmembers(module):
                    if (name.startswith("test_") or hasattr(obj, "test_name")) and callable(obj):
                        test_functions.append(obj)
                
                if test_functions:
                    test_modules[module_name] = test_functions
            
            except ImportError as e:
                logger.error(f"Error importing module {module_name}: {e}")
                logger.error(f"sys.path: {sys.path}")
    
    return test_modules

def run_tests(tests_to_run: Dict[str, List[Callable]], 
             keep_temp_files: bool = False) -> Dict[str, TestResult]:
    """
    Run the specified tests.
    
    Args:
        tests_to_run: Dictionary mapping module names to lists of test functions
        keep_temp_files: Whether to keep temporary files created during tests
        
    Returns:
        Dictionary mapping test names to TestResult objects
    """
    results = {}
    
    # Create a temporary environment variable to signal that tests should keep files
    if keep_temp_files:
        os.environ["KEEP_TEST_FILES"] = "1"
    else:
        os.environ.pop("KEEP_TEST_FILES", None)
    
    # Run all tests
    for module_name, test_functions in tests_to_run.items():
        print_header(f"Running tests from module: {module_name}")
        
        for test_func in test_functions:
            test_name = getattr(test_func, "test_name", test_func.__name__)
            
            print(f"\nRunning test: {test_name}")
            start_time = time.time()
            
            try:
                # Run the test function
                result = test_func()
                
                # Ensure we have a TestResult object
                if not isinstance(result, TestResult):
                    if isinstance(result, tuple) and len(result) >= 1:
                        returncode = result[0]
                        output_dir = result[1] if len(result) > 1 else None
                        stdout = result[2] if len(result) > 2 else ""
                        stderr = result[3] if len(result) > 3 else ""
                        success = returncode == 0
                        result = TestResult(test_name, success, output_dir, returncode, stdout, stderr)
                    elif isinstance(result, bool):
                        result = TestResult(test_name, result)
                    else:
                        # Default to success if the test completed without error
                        result = TestResult(test_name, True)
                
                results[test_name] = result
                
                elapsed_time = time.time() - start_time
                status = "PASSED" if result.success else "FAILED"
                print(f"Test {test_name} {status} in {elapsed_time:.2f} seconds")
            
            except Exception as e:
                logger.exception(f"Error running test {test_name}: {e}")
                results[test_name] = TestResult(test_name, False, details={"error": str(e)})
                print(f"Test {test_name} FAILED with exception: {e}")
    
    return results

def validate_results(results: Dict[str, TestResult], verbose: int = 0) -> Dict[str, Any]:
    """
    Validate test results using the validation script.
    
    Args:
        results: Dictionary mapping test names to TestResult objects
        verbose: Verbosity level for validation
        
    Returns:
        Dictionary with validation information
    """
    # Import here to avoid circular dependencies
    from common import validate_test_output
    
    validation_results = {}
    
    print_header("Validating test results")
    
    for test_name, result in results.items():
        if not result.success:
            validation_results[test_name] = {
                "validated": False,
                "reason": "Test failed, skipping validation"
            }
            continue
        
        if not result.output_dir or not os.path.exists(result.output_dir):
            validation_results[test_name] = {
                "validated": False,
                "reason": "No output directory to validate"
            }
            continue
        
        print(f"Validating output for test: {test_name}")
        validated, output = validate_test_output(result.output_dir, verbose)
        
        validation_results[test_name] = {
            "validated": validated,
            "output": output
        }
    
    return validation_results

def summarize_results(test_results: Dict[str, TestResult], 
                     validation_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a summary of test and validation results.
    
    Args:
        test_results: Dictionary mapping test names to TestResult objects
        validation_results: Dictionary with validation information
        
    Returns:
        Dictionary with test summary information
    """
    import platform
    
    tests_passed = sum(1 for result in test_results.values() if result.success)
    validations_passed = sum(1 for result in validation_results.values() 
                           if result.get("validated", False))
    
    summary = {
        "timestamp": time.time(),
        "time": time.ctime(),
        "platform": platform.platform(),
        "python_version": sys.version,
        "total_tests": len(test_results),
        "tests_passed": tests_passed,
        "validations_passed": validations_passed,
        "test_details": {name: result.to_dict() for name, result in test_results.items()},
        "validation_details": validation_results
    }
    
    return summary

def save_results(summary: Dict[str, Any], output_file: str = None) -> str:
    """
    Save test results to a JSON file.
    
    Args:
        summary: Test summary dictionary
        output_file: Path to output file (default: "test_results_{timestamp}.json")
        
    Returns:
        Path to the output file
    """
    if output_file is None:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_file = f"test_results_{timestamp}.json"
    
    with open(output_file, "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"Test results saved to {output_file}")
    return output_file

def print_summary(summary: Dict[str, Any]):
    """Print a summary of test results."""
    print_header("Test Summary")
    
    print(f"Tests: {summary['tests_passed']}/{summary['total_tests']} passed")
    print(f"Validations: {summary['validations_passed']}/{summary['total_tests']} passed")
    
    print("\nTest Details:")
    for name, details in summary["test_details"].items():
        status = "PASSED" if details["success"] else "FAILED"
        print(f"  {name}: {status}")
    
    print("\nValidation Details:")
    for name, details in summary["validation_details"].items():
        status = "PASSED" if details.get("validated", False) else "FAILED"
        print(f"  {name}: {status}")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run tests for find_best_images.py")
    
    parser.add_argument("--tests", nargs="+", 
                      help="Specific tests to run (format: module_name or module_name.test_name)")
    parser.add_argument("--skip", nargs="+",
                      help="Tests to skip (format: module_name or module_name.test_name)")
    parser.add_argument("--keep-files", action="store_true",
                      help="Keep temporary files created during tests")
    parser.add_argument("--no-validate", action="store_true",
                      help="Skip validation of test results")
    parser.add_argument("--verbose", "-v", action="count", default=0,
                      help="Increase verbosity (can be used multiple times)")
    parser.add_argument("--output", "-o",
                      help="Save test results to the specified file")
    parser.add_argument("--test-dir",
                      help="Directory containing test images")
    
    return parser.parse_args()

def main():
    """Main function to run tests."""
    args = parse_args()
    
    # Check for test images
    test_dir = args.test_dir
    if not test_dir:
        # Try to find test images in common locations
        potential_dirs = ["./test_materials_2025.03.04", "../test_materials_2025.03.04", "../../test_materials_2025.03.04"]
        for potential_dir in potential_dirs:
            if os.path.exists(potential_dir) and os.path.isdir(potential_dir):
                test_dir = potential_dir
                break
    
    if not ensure_test_directory(test_dir):
        sys.exit(1)
    
    # Set verbosity level
    if args.verbose >= 2:
        logger.setLevel(logging.DEBUG)
    elif args.verbose >= 1:
        logger.setLevel(logging.INFO)
    
    # Discover tests
    all_tests = discover_tests()
    logger.info(f"Discovered {sum(len(tests) for tests in all_tests.values())} tests in {len(all_tests)} modules")
    
    # Filter tests based on command line arguments
    tests_to_run = {}
    
    if args.tests:
        # Only include specified tests
        for test_spec in args.tests:
            if "." in test_spec:
                # Format: module_name.test_name
                module_name, test_name = test_spec.split(".", 1)
                if module_name in all_tests:
                    module_tests = [t for t in all_tests[module_name] 
                                  if getattr(t, "test_name", t.__name__) == test_name]
                    if module_tests:
                        tests_to_run.setdefault(module_name, []).extend(module_tests)
            else:
                # Format: module_name
                if test_spec in all_tests:
                    tests_to_run[test_spec] = all_tests[test_spec]
    else:
        # Include all tests
        tests_to_run = all_tests
    
    # Apply skip filter
    if args.skip:
        for skip_spec in args.skip:
            if "." in skip_spec:
                # Format: module_name.test_name
                module_name, test_name = skip_spec.split(".", 1)
                if module_name in tests_to_run:
                    tests_to_run[module_name] = [t for t in tests_to_run[module_name] 
                                              if getattr(t, "test_name", t.__name__) != test_name]
            else:
                # Format: module_name
                tests_to_run.pop(skip_spec, None)
    
    # Run tests
    print_header("Running Tests")
    test_results = run_tests(tests_to_run, keep_temp_files=args.keep_files)
    
    # Validate results
    validation_results = {}
    if not args.no_validate:
        validation_results = validate_results(test_results, verbose=args.verbose)
    
    # Create summary
    summary = summarize_results(test_results, validation_results)
    
    # Save results if requested
    if args.output:
        save_results(summary, args.output)
    
    # Print summary
    print_summary(summary)
    
    # Return success if all tests pass
    return 0 if summary["tests_passed"] == summary["total_tests"] else 1

if __name__ == "__main__":
    sys.exit(main())