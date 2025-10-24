"""
Path Helper for Strategy Scripts
Dynamically finds project root and constructs absolute paths.
"""
import os
from pathlib import Path

def get_project_root():
    """
    Find the project root directory (fabio_valentini folder).
    Works from any subfolder within the project.
    """
    current_file = Path(__file__).resolve()

    # Navigate up until we find the project root
    # The project root contains 'data/', 'outputs/', and 'config.py'
    current = current_file.parent

    while current != current.parent:
        # Check if this is the project root
        if (current / 'data').exists() and (current / 'outputs').exists():
            return current
        current = current.parent

    raise RuntimeError("Could not find project root (fabio_valentini folder)")

def get_data_path(filename=''):
    """Get absolute path to data/ folder or specific file in data/"""
    root = get_project_root()
    if filename:
        return str(root / 'data' / filename)
    return str(root / 'data')

def get_output_path(filename=''):
    """Get absolute path to outputs/ folder or specific file in outputs/"""
    root = get_project_root()
    outputs_dir = root / 'outputs'
    outputs_dir.mkdir(exist_ok=True)  # Create if doesn't exist
    if filename:
        return str(outputs_dir / filename)
    return str(outputs_dir)

def get_charts_path(filename=''):
    """Get absolute path to charts/ folder or specific file in charts/"""
    root = get_project_root()
    charts_dir = root / 'charts'
    charts_dir.mkdir(exist_ok=True)  # Create if doesn't exist
    if filename:
        return str(charts_dir / filename)
    return str(charts_dir)

def get_config_path():
    """Get absolute path to config.py"""
    root = get_project_root()
    return str(root / 'config.py')

# Convenience function to add project root to sys.path for imports
def setup_project_imports():
    """Add project root to sys.path to allow imports from root"""
    import sys
    root = str(get_project_root())
    if root not in sys.path:
        sys.path.insert(0, root)
