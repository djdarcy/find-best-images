#!/usr/bin/env python3
"""
debug_imports.py

A dynamic diagnostic tool to check module imports within a package.
Usage:
    python debug_imports.py <package_name> [--package-path <path>]

Features:
- Scans the specified package directory for all .py modules (excluding __init__.py).
- Verifies that the package has an __init__.py.
- Creates a backup of __init__.py and injects temporary debug code.
- Checks each module for importability, printing detailed debug info with ANSI colors.
- Automatically restores __init__.py after testing and cleans up the backup if unchanged.
"""

import sys
import os
import argparse
import importlib
import time
import filecmp

# Import colorama and initialize it for ANSI color support on Windows
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
except ImportError:
    # If colorama is not installed, define dummy color codes.
    class Fore:
        RED = ""
        GREEN = ""
        YELLOW = ""
        BLUE = ""
        CYAN = ""
    class Style:
        RESET_ALL = ""

# Define Symbols for Output (Compatible with Consolas)
CHECK = "*"
CROSS = "X"
WARN = "!"
INFO = "-"
RESTORE = "~"

DEBUG_MARKER_START = "# DEBUG INJECTION START\n"
DEBUG_MARKER_END = "# DEBUG INJECTION END\n"

def get_python_modules(package_name, package_root):
    """Find all .py modules inside the given package directory.
    
    Args:
        package_name (str): Name of the package (used for qualified names).
        package_root (str): Absolute path to the parent directory containing the package.
    
    Returns:
        (list, str): A tuple with a list of fully qualified module names and the path to __init__.py.
    """
    package_path = os.path.join(package_root, package_name)
    package_path = os.path.abspath(package_path)
    
    if not os.path.isdir(package_path):
        print(f"{Fore.RED}{CROSS} Error: '{package_path}' is not a valid directory!{Style.RESET_ALL}")
        sys.exit(1)
    
    init_file = os.path.join(package_path, "__init__.py")
    if not os.path.exists(init_file):
        print(f"{Fore.RED}{CROSS} Error: '{package_name}' is missing __init__.py and is not a package!{Style.RESET_ALL}")
        sys.exit(1)
    
    # List .py files (exclude __init__.py)
    modules = [
        os.path.splitext(f)[0] for f in os.listdir(package_path)
        if f.endswith(".py") and f != "__init__.py"
    ]
    
    qualified_modules = [f"{package_name}.{mod}" for mod in modules]
    
    return qualified_modules, init_file

def backup_init_file(init_file):
    """Create a backup of __init__.py."""
    backup_file = init_file + ".bak"
    try:
        with open(init_file, "r", encoding="utf-8") as f:
            content = f.read()
        with open(backup_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"{Fore.CYAN}{INFO} Backup created: {backup_file}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}{CROSS} Failed to create backup of {init_file}: {e}{Style.RESET_ALL}")
        sys.exit(1)
    return backup_file

def inject_debugging_into_init(init_file):
    """Inject debug information into __init__.py and return the original content.
    
    This function first checks if the debug markers are already present.
    """
    try:
        with open(init_file, "r", encoding="utf-8") as f:
            original_content = f.readlines()
    except Exception as e:
        print(f"{Fore.RED}{CROSS} Error reading {init_file}: {e}{Style.RESET_ALL}")
        sys.exit(1)
    
    # Check if debug injection is already present
    for line in original_content:
        if DEBUG_MARKER_START.strip() in line:
            print(f"{Fore.YELLOW}{WARN} Debug injection markers already found in {init_file}. Skipping injection.{Style.RESET_ALL}")
            return original_content  # Return original content without change
    
    debug_lines = [
        DEBUG_MARKER_START,
        'import sys, os\n',
        'print(f"DEBUG: (Injected) sys.path = {sys.path}")\n',
        'print(f"DEBUG: (Injected) Package location = {os.path.abspath(__file__)}")\n',
        DEBUG_MARKER_END
    ]
    
    modified_content = debug_lines + original_content
    
    try:
        with open(init_file, "w", encoding="utf-8") as f:
            f.writelines(modified_content)
        print(f"{Fore.CYAN}{INFO} Injected debug information into {init_file}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}{CROSS} Error writing to {init_file}: {e}{Style.RESET_ALL}")
        sys.exit(1)
    
    return original_content

def restore_init_file(init_file, original_content):
    """Restore the original __init__.py content."""
    try:
        with open(init_file, "w", encoding="utf-8") as f:
            f.writelines(original_content)
        print(f"{Fore.CYAN}{RESTORE} Restored original {init_file}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}{CROSS} Failed to restore {init_file}: {e}{Style.RESET_ALL}")

def cleanup_backup(backup_file, init_file):
    """Compare the backup file and the current __init__.py; remove the backup if they are identical."""
    try:
        if filecmp.cmp(backup_file, init_file, shallow=False):
            os.remove(backup_file)
            print(f"{Fore.CYAN}{INFO} Backup file {backup_file} is identical and has been removed.{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}{WARN} Backup file {backup_file} differs from the restored file; not removed.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}{CROSS} Error during backup cleanup: {e}{Style.RESET_ALL}")

def check_import(module_name):
    """Check if a module can be imported and print debug info."""
    print(f"\n{Fore.BLUE}{INFO} Checking module: {module_name}{Style.RESET_ALL}")
    try:
        # Explicitly import importlib.util to avoid attribute issues
        import importlib.util
        spec = importlib.util.find_spec(module_name)
        if spec is None:
            print(f"{Fore.RED}{CROSS} Module '{module_name}' NOT FOUND in sys.path{Style.RESET_ALL}")
        else:
            print(f"{Fore.GREEN}{CHECK} Module '{module_name}' FOUND at {spec.origin}{Style.RESET_ALL}")
        
        mod = importlib.import_module(module_name)
        print(f"{Fore.GREEN}{CHECK} Successfully imported '{module_name}'!{Style.RESET_ALL}")
        return mod
    except Exception as e:
        print(f"{Fore.RED}{CROSS} Import failed for '{module_name}': {e}{Style.RESET_ALL}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Dynamically debug and test imports within a Python package."
    )
    parser.add_argument("package_name", help="Name of the package (subfolder) to check.")
    parser.add_argument("--package-path", default=None,
                        help="Absolute path to the parent directory containing the package. Defaults to the parent directory of this script.")
    
    args = parser.parse_args()
    
    # Determine package root: use provided value or default to the parent of the script's directory.
    if args.package_path:
        package_root = os.path.abspath(args.package_path)
    else:
        # First, try the current working directory
        cwd_package_root = os.path.join(os.getcwd(), args.package_name)
        if os.path.isdir(cwd_package_root):
            package_root = os.path.abspath(os.getcwd())
        else:
            # Fallback to the parent of the script's directory
            package_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    # Insert package_root into sys.path to allow package imports.
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    
    print(f"{Fore.YELLOW}{INFO} DEBUG: sys.path = {sys.path}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{INFO} Using package root: {package_root}{Style.RESET_ALL}")
    
    modules_to_check, init_file = get_python_modules(args.package_name, package_root)
    print(f"{Fore.YELLOW}{INFO} Found package '{args.package_name}' at {os.path.join(package_root, args.package_name)}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{INFO} Modules to check: {modules_to_check}{Style.RESET_ALL}")
    
    backup_file = backup_init_file(init_file)
    original_init_content = inject_debugging_into_init(init_file)
    
    try:
        time.sleep(0.5)  # Slight pause for clarity in output
        for module in modules_to_check:
            check_import(module)
    finally:
        restore_init_file(init_file, original_init_content)
        # Cleanup backup if restored __init__.py is identical to backup
        cleanup_backup(backup_file, init_file)
