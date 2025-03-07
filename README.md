# Find Best Images

**Find Best Images** is a versatile tool for scanning directories to identify and organize the highest quality versions among similar images. Leveraging advanced similarity metrics—including deep learning-based embeddings and multiple quality measures—this tool automates the process of deduplication and organization of image collections. It is especially useful for artists, photographers, and AI trainers who need to curate the best images from large datasets.

## Features

- **Multi-Directory Scanning:** Recursively search one or more directories for images.
- **Advanced Filtering:** Include or exclude directories and files using glob or regex patterns.
- **Quality Evaluation:** Use primary (strict order) and secondary (weighted) metrics to determine image quality.
- **Deep Similarity Analysis:** Employ CLIP embeddings and region-based similarity checks to detect duplicates.
- **Output Organization:** Automatically create structured output directories with best images and candidate subfolders.
- **Filename Collision Handling:** Robust strategies (hierarchical, hash, numeric, parent-only) to resolve naming conflicts.
- **Results Collection:** Optionally consolidate best images into a single collection directory.
- **Flexible File Operations:** Choose between symlink, copy, or move operations, with optional backlinking.
- **Configurable Date Preferences:** Select between “newest” or “oldest” based on your needs.

## Typical Use Cases

1. **Digital Asset Management:**
   Manage and deduplicate image collections from multiple sources, such as photography projects, social media organization, or generation runs.

2. **Dataset Curation:**
   Automatically curate large datasets (e.g., 4000+ images) by selecting the best images for AI training.

3. **Creative Workflows:**
   Use the tool as a pre-processor for artistic projects or game development, ensuring only the highest quality images are used.

## Installation

### Option 1: Clone the Repository

```bash
git clone https://github.com/djdarcy/find-best-images.git
cd find-best-images
```

Install the required dependencies (*though it is recommended to configure a virtual environment before running *`pip install`*, see below*):

```bash
pip install -r requirements.txt
```

### Option 2: pip Install

Install directly from GitHub:

```bash
pip install git+https://github.com/djdarcy/find-best-images.git
```

Or, if you want to install in editable mode:

```bash
git clone https://github.com/djdarcy/find-best-images.git
cd find-best-images
pip install -e .
```

## Setting Up a Virtual Environment

To ensure package dependencies are properly managed and avoid conflicts with system-wide Python installations, it is recommended to use a virtual environment.

### Create and Activate a Virtual Environment

- **On macOS/Linux:**

  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

- **On Windows:**

  ```powershell
  python -m venv venv
  venv\Scripts\activate
  ```

Once the virtual environment is activated, install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage Examples

### Basic Command

```bash
python find_best_images.py -i "path/to/input1" -i "path/to/input2" -o "path/to/output" -r
```

### Advanced Example for AI Dataset Curation

```bash
python find_best_images.py -i "d:\" --recursive --copy-best --collect-results \
  --include-dirs-pattern "(__training|input)" \
  --exclude-dirs-pattern "(output|wip)" \
  --pattern-mode regex \
  --output-dir "GAN_BestImages" --force
```

*This command recursively scans `d:\` while including only directories with names like `__training` or `input` and excluding directories related to outputs and non-relevant sources.*

## Command Reference Table

| Command/Option             | Description                                           |
|----------------------------|-------------------------------------------------------|
| `-i`, `--input-dir`        | Specify input directories to scan (multiple allowed). |
| `-o`, `--output-dir`       | Directory to store organized images.                  |
| `-r`, `--recursive`        | Recursively scan subdirectories.                      |
| `--copy-best`              | Copy best images instead of linking them.             |
| `--collect-results`        | Collect best images into a single directory.          |
| `--include-dirs-pattern`   | Include directories matching glob/regex patterns.     |
| `--exclude-dirs-pattern`   | Exclude directories matching glob/regex patterns.     |
| `--pattern-mode`           | Pattern mode: `glob` (default) or `regex`.            |
| `--primary-metrics`        | Primary quality metrics, evaluated in strict order.   |
| `--secondary-metrics`      | Secondary metrics if primary metrics tie.             |
| `--force`                  | Force operation even if output directories exist.     |

## FAQ

**What's the difference between dimensions and resolution?**

- **Dimensions**: Pixel width and height (e.g., 4000x3000).
- **Resolution**: Pixel density (e.g., 300 DPI), important for print quality.

**Can I preview changes before applying them?**

- Use `--dryrun` to simulate changes without modifying your files.

**Does it support cloud storage?**

- Currently supports local file systems; cloud storage integration is possible, but it's far down the roadmap.

## Contributing

Contributions, issues, and feature requests are welcome!

- **Future enhancements:**
  - More advanced AI-driven similarity checks.
  - Picture-in-picture analysis beyond simple region checks.
  - Improved UI for interactive selections.
  - Cloud storage integration.

1. Fork the repository.
2. Create a feature branch (e.g., `feature/new-metric`).
3. Commit your changes.
4. Open a pull request detailing your improvements.

Please review our [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

If you find this project useful, please consider giving it a star on GitHub and sharing it with others. Or, you can always:

[!["Buy Me A Coffee"](https://camo.githubusercontent.com/0b448aabee402aaf7b3b256ae471e7dc66bcf174fad7d6bb52b27138b2364e47/68747470733a2f2f7777772e6275796d6561636f666665652e636f6d2f6173736574732f696d672f637573746f6d5f696d616765732f6f72616e67655f696d672e706e67)](https://www.buymeacoffee.com/djdarcy)

For any questions, feel free to open an issue or reach out directly.

## License

find-best-images, Copyright (C) 2025 Dustin Darcy

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program. If not, see [http://www.gnu.org/licenses/](http://www.gnu.org/licenses/).

