import os
import shutil
import argparse
import subprocess
from PIL import Image
from sys import platform as _platform

DEFAULT_EXTENSIONS = ['bmp', 'jpg', 'jpeg', 'png', 'webp', 'gif', 'tiff', 'tif', 'jp2', 'heif', 'heic']

def parse_arguments():
    epilog_text = (
        "Note: If you encounter issues with symbolic links on Windows, especially with network drives or UNC paths, \n"
        "you may need to enable local to remote symbolic link evaluations. This can be done by running the command: \n"
        "'fsutil behavior set SymlinkEvaluation L2L:0 L2R:0 R2R:1 R2L:1' in an elevated command prompt.\n"
        "\n"
        "Examples:\n"
        "  Search for large images in both dimensions and output to a file (create flat link structure):\n"
        "    imgsrch.py -B 1080 -op gte -r -o images_bigger_than_1080_in_both_dims.txt -l check_biggest_images -ls flat\n"
        "\n"
        "  Search for large images in one dimension and output to a file (create nested link structure):\n"
        "    imgsrch.py -O 1080 -op gte -r -o images_bigger_than_1080_in_one_dim.txt -l check_big_images -ls nested\n"
    )

    parser = argparse.ArgumentParser(
        description="Search for images based on various criteria.",
        epilog=epilog_text,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("-p", "--path", type=str, default=os.getcwd(), help="Starting directory for search.")
    parser.add_argument("-xd", "--exclude", action="append", help="Directories to exclude from search.")
    parser.add_argument("-m", "--filemask", type=str, help="Filemask for filtering files.")
    parser.add_argument("-e", "--ext", type=str, help="File extension to filter images.")
    parser.add_argument("-x", "--regex", type=str, help="Regex pattern for file matching.")
    parser.add_argument("-r", "--recursive", action="store_true", help="Recursively search through directories.")
    parser.add_argument("-W", "--width", type=int, help="Width to search for.")
    parser.add_argument("-H", "--height", type=int, help="Height to search for.")
    parser.add_argument("-B", "--both", type=int, help="Size for both width and height.")
    parser.add_argument("-O", "--eitheror", type=int, help="Size for either width or height.")
    parser.add_argument("-op", "--operation", choices=["gt", "lt", "eq", "gte", "lte", "neq"], help="Operation for size comparison.")
    parser.add_argument("-ex", "--exif", action="store_true", help="Search for images with EXIF data.")
    parser.add_argument("-ed", "--exifdetail", type=str, help="Specific EXIF detail to search for.")
    parser.add_argument("-v", "--verbosity", action="count", default=0, help="Increase output verbosity.")
    parser.add_argument("-o", "--output", type=str, help="Output file to write results.")
    parser.add_argument("-l", "--link", type=str, help="Directory to create symbolic links for matching files.")
    parser.add_argument("-ls", "--link-structure", type=str, choices=["nested", "flat"], default="nested", help="Structure of the symbolic links directory: nested or flat.")
    parser.add_argument("-?", action="help", help="Show this help message and exit")
    return parser.parse_args()

def is_image_file(filename, ext, filemask):
    if ext:
        return filename.lower().endswith('.' + ext.lower())
    elif filemask:
        return filemask in filename
    else:
        return any(filename.lower().endswith('.' + e) for e in DEFAULT_EXTENSIONS)

def compare_dimension(dimension, target, operation):
    if operation == "gt":
        return dimension > target
    elif operation == "lt":
        return dimension < target
    elif operation == "eq":
        return dimension == target
    elif operation == "gte":
        return dimension >= target
    elif operation == "lte":
        return dimension <= target
    elif operation == "neq":
        return dimension != target

def matches_criteria(image_path, args):
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            if args.width and not compare_dimension(width, args.width, args.operation):
                return False
            if args.height and not compare_dimension(height, args.height, args.operation):
                return False
            if args.both and not (compare_dimension(width, args.both, args.operation) and compare_dimension(height, args.both, args.operation)):
                return False
            if args.eitheror and not (compare_dimension(width, args.eitheror, args.operation) or compare_dimension(height, args.eitheror, args.operation)):
                return False
            return True
    except Exception as e:
        if args.verbosity > 1:
            print(f"Error processing {image_path}: {e}")
        return False

def print_image_info(image_path, args, output_file=None):
    info = image_path
    if args.verbosity >= 1:
        try:
            with Image.open(image_path) as img:
                width, height = img.size
                print(f"Dimensions: {width}x{height}")
                if args.verbosity >= 2 and "exif" in img.info:
                    print("EXIF data:")
                    for tag, value in img._getexif().items():
                        print(f"  {tag}: {value}")
        except Exception as e:
            if args.verbosity > 1:
                print(f"Error accessing image data for {image_path}: {e}")
    
    if output_file:
        with open(output_file, "a", encoding="utf-8") as file:
            file.write(info + "\n")
    else:
        print(info)

def search_images(start_path, args):
    output_file = args.output if args.output else None

    for root, dirs, files in os.walk(start_path):
        for file in files:
            if args.exclude is not None and any(os.path.abspath(root).startswith(os.path.abspath(excluded_dir)) for excluded_dir in args.exclude):
                continue  # Skip this directory
            if is_image_file(file, args.ext, args.filemask):
                full_path = os.path.join(root, file)
                if matches_criteria(full_path, args):
                    print_image_info(full_path, args, output_file)
                    if args.link:
                        relative_path = os.path.relpath(full_path, start_path)
                        create_symbolic_link(full_path, args.link, start_path, relative_path, args.link_structure)
        if not args.recursive:
            break

def create_symbolic_link(source_path, base_link_dir, start_path, relative_path, link_structure):
    if not os.path.exists(base_link_dir):
        os.makedirs(base_link_dir)

    file_ext = os.path.splitext(source_path)[1]
    if link_structure == "flat":
        # Replace path separators with fullwidth reverse solidus and prepend the base directory name
        relative_path_from_base = os.path.dirname(os.path.relpath(source_path, start_path))
        unique_name = os.path.basename(source_path) + "---" + relative_path_from_base.replace(os.sep, '\uFF3C') + file_ext
        link_path = os.path.join(base_link_dir, unique_name)
    else:
        relative_dir = os.path.relpath(os.path.dirname(source_path), start_path)
        link_dir = os.path.join(base_link_dir, relative_dir)
        if not os.path.exists(link_dir):
            os.makedirs(link_dir)
        link_path = os.path.join(link_dir, os.path.basename(source_path))

    if not os.path.exists(link_path):
        # The source path needs to be absolute to work correctly when called from another directory
        source_path = os.path.abspath(source_path)
        link_path = os.path.abspath(link_path)
        if _platform == "win32":
            subprocess.run(["mklink", link_path, source_path], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            os.symlink(source_path, link_path)


if __name__ == "__main__":
    args = parse_arguments()
    search_images(args.path, args)
