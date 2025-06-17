# file: tools/git_tools.py

import os
import json
import logging
from typing import Any, Dict, List, Optional

from langchain.tools import BaseTool
from gitingest import ingest

logger = logging.getLogger(__name__)

DEFAULT_EXCLUDE_PATTERNS = {
    # Python build and cache
    "__pycache__/", "*.egg-info/", ".venv/", "env/", "build/", "dist/", "*.lock",
    # Test, prompt, and data folders
    "test/", "prompt/", "prompts/", "data/",
    # VCS and system
    ".git/",
    # JS/TS/Node build artifacts and dependencies
    "node_modules/", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "vite.config.*", "next.config.*", "webpack.config.*", "babel.config.*",
    # Go and Rust build artifacts
    "vendor/", "target/",
    # License and meta files
    "LICENSE", "license*",
    # Python/Ruby/other language init/meta files
    "__init__.py", "__main__.py", "__about__.py", "__version__.py",
}



class GitIngestTool(BaseTool):
    name: str = "git_ingest"
    description: str = (
        "Ingest a Git repo (local path or URL) via gitingest, excluding noisy files. "
        "Returns JSON with summary (str), tree (list of paths), and content (dict)."
    )

    def __init__(self, exclude_patterns: Optional[set[str]] = None):
        super().__init__()
        self.exclude_patterns = exclude_patterns or DEFAULT_EXCLUDE_PATTERNS

    def _run(self, source: str) -> str:
        summary, tree, content = ingest(
            source,
            exclude_patterns=self.exclude_patterns
        )
        return json.dumps({
            "project_path": source,
            "summary": summary,
            "tree": tree,
            "content": content
        })

    async def _arun(self, source: str) -> str:
        return self._run(source)


class DetectServicesTool(BaseTool):
    name: str = "detect_services"
    description: str = (
        "Detect standalone services by finding manifest files in the repo tree. "
        "Returns JSON list of {name, path, language, manifest}."
    )

    def _run(self, ingest_json: str) -> str:
        data: Dict[str, Any] = json.loads(ingest_json)
        tree: List[str] = data["tree"]
        services: Dict[str, Dict[str, Any]] = {}

        # Map manifest → language
        known = {
            "requirements.txt": "python",
            "pyproject.toml":  "python",
            "poetry.lock":     "python",
            "package.json":    "javascript",
            "go.mod":          "go",
            "Cargo.toml":      "rust",
        }

        for path in tree:
            for manifest, lang in known.items():
                if path.endswith(manifest):
                    # directory containing the manifest
                    dir_path = os.path.dirname(path)
                    print(dir_path)
                    name = os.path.basename(dir_path) or os.path.basename(data["project_path"])
                    services[dir_path] = {
                        "name": name,
                        "path": dir_path,
                        "language": lang,
                        "manifest": manifest
                    }
                    break

        return json.dumps(list(services.values()))

    async def _arun(self, ingest_json: str) -> str:
        return self._run(ingest_json)
