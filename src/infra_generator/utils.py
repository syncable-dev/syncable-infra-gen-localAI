# utils.py
import os
import yaml
import shutil
import pkg_resources
from typing import Optional

def load_config(custom_config_path: Optional[str] = None) -> dict:
    """
    Loads configuration with a fallback mechanism.

    1.  If `custom_config_path` is provided, it loads from that file.
    2.  If not, it looks for a config in `~/.config/infra-generator/config.yaml`.
    3.  If that doesn't exist, it loads the default `config.yaml` bundled with the package.
    """
    # Path 1: Custom path from user
    if custom_config_path and os.path.exists(custom_config_path):
        with open(custom_config_path, 'r') as f:
            return yaml.safe_load(f)

    # Path 2: User-specific config file
    user_config_path = os.path.expanduser("~/.config/infra-generator/config.yaml")
    if os.path.exists(user_config_path):
        with open(user_config_path, 'r') as f:
            return yaml.safe_load(f)

    # Path 3: Default package config
    try:
        # This reads the config bundled with the package
        default_config_str = pkg_resources.resource_string('infra_generator', 'config.yaml')
        return yaml.safe_load(default_config_str)
    except (pkg_resources.DistributionNotFound, FileNotFoundError):
        # Fallback for when the package is not installed (e.g., during development)
        dev_config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        if os.path.exists(dev_config_path):
            with open(dev_config_path, 'r') as f:
                return yaml.safe_load(f)
        else:
            raise FileNotFoundError(
                "Could not find the default config.yaml. "
                "Ensure it's in the same directory as this script or the package is installed correctly."
            )

def list_source_files(directory: str, extensions: list) -> list:
    file_list = []
    for root, _, files in os.walk(directory):
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                file_list.append(os.path.join(root, file))
    return file_list

def get_language_from_extension(filename: str, config: dict) -> str:
    ext = os.path.splitext(filename)[1]
    for lang, extension in config['extensions'].items():
        if extension == ext:
            return lang
    return 'unknown'

def get_project_name(project_dir: str) -> str:
    # Use the last folder name as project name
    return os.path.basename(os.path.abspath(project_dir))

def ensure_dir_exists(path: str):
    if not os.path.exists(path):
        os.makedirs(path)

def read_manifest_file(project_path: str, manifest: Optional[str]) -> str:
    """
    Read and return the contents of `manifest` under `project_path`, if it exists.
    """
    if not manifest:
        return ""
    path = os.path.join(project_path, manifest)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return ""