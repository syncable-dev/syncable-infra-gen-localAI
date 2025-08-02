# Synchronous usage
from gitingest import ingest

if __name__ == "__main__":
    # Example usage of the ingest function
    # include_patterns = {
    # "*.py", "*.toml", "*.yml", "*.yaml", "*.json",
    # "Dockerfile", "docker-compose.yml", "requirements.txt",
    # "pyproject.toml", "package.json"
    # }
    exclude_patterns = {
        "__pycache__/",
        "*.egg-info/",
        "test/",
        "prompt/",
        "data/",
        ".git/",
        ".venv/",
        "env/",
        "build/",
        "dist/",
        "*.lock",
        # JS/TS/Node build artifacts and dependencies only
        "node_modules/",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "vite.config.*",
        "next.config.*",
        "webpack.config.*",
        "babel.config.*",
        # Go build artifacts only
        "vendor/",
        # Rust build artifacts only
        "target/",
        # License and prompts
        "LICENSE",
        "license*",
        "prompt/",
        "prompts/",
        # Python/Ruby/other language init/meta files
        "__init__.py",
        "__init__.pyc",
        "__init__.pyo",
        "__init__.pyw",
        "__init__.cpython-*",
        "__main__.py",
        "__main__.pyc",
        "__main__.pyo",
        "__main__.pyw",
        "__main__.cpython-*",
        "__about__.py",
        "__version__.py",
        "__meta__.py",
        "__init__.rb",
        "__init__.js",
        "__init__.ts",
    }
    summary, tree, content = ingest(
        "../local-ai-infra-generation",
        # include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
    )
    print("Summary:", summary)
    print("Tree structure:", tree)
    # print("Content:", content)