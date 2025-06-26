# utils.py
import os
import yaml
import shutil

import os
from typing import Optional

def load_config(config_path: str = None) -> dict:
    config_path = config_path or os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

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
