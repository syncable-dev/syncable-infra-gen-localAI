# local-AI-infra-generation

**local-AI-infra-generation** leverages local Large Language Models (LLMs) to analyze code repositories and automatically generate infrastructure files such as Dockerfiles and docker-compose.yml. All processing is performed locally, ensuring privacy and control over your codebase.

---

## Features

- **Codebase Embedding:** Index and embed your codebase for semantic search and retrieval.
- **Natural Language Q&A:** Ask questions about your codebase and receive context-aware answers.
- **Automated Infrastructure Generation:** Generate Dockerfiles and docker-compose.yml files tailored to your project.
- **Multi-language Support:** Works with Python, JavaScript, TypeScript, and Go projects.

---

## Getting Started

### 1. Prerequisites

- **Python 3.11+**  
  Ensure you have Python 3.11 or higher installed.  
  _Check with:_  
  ```sh
  python --version
  ```

- **[Ollama](https://ollama.com/download)**  
  Download and install Ollama for local LLM inference.

- **C/C++ Build Tools**  
  Required for building [tree-sitter-languages](https://pypi.org/project/tree-sitter-languages/).

### 2. Installation

Create and activate a virtual environment:
```sh
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

Install the package from this repository:

```sh
pip install .
```

This will install the `infra-gen` command-line tool and all necessary dependencies.

---

## Usage

### 1. Start Ollama

Make sure the Ollama server is running in the background:

```sh
ollama serve &
```

### 2. Run the CLI

Once installed, you can use the `infra-gen` command.

```sh
infra-gen --help
```

#### Common Commands

- **Embed a Project:**
  ```sh
  infra-gen embed /path/to/your/project
  ```

- **Ask a Question:**
  ```sh
  infra-gen ask "How does authentication work?" --project your_project_name
  ```

- **List Embedded Projects:**
  ```sh
  infra-gen list
  ```

- **Generate Full Infrastructure (Dockerfile, Compose, etc.):**
  ```sh
  infra-gen generate-infra /path/to/your/project --output ./infra
  ```

- **Generate Only a Dockerfile:**
  ```sh
  infra-gen generate-docker --project your_project_name
  ```

- **Generate Only a docker-compose.yml:**
  ```sh
  infra-gen generate-compose --project your_project_name
  ```

---

## Configuration

The tool uses a `config.yaml` file for settings. The configuration is loaded in the following order of priority:

1.  **Via `--config` flag:** Provide a direct path to a `.yaml` file.
    ```sh
    infra-gen --config /path/to/my-config.yaml embed /path/to/project
    ```
2.  **User-level config:** Place a file at `~/.config/infra-generator/config.yaml`.
3.  **Default package config:** If no other config is found, a default version bundled with the package is used.

You can customize model names, ChromaDB storage directories, Ollama URLs, and more in your custom config file.

---

## Development

If you want to contribute to the development of this tool, you can install it in editable mode.

1.  Clone the repository:
    ```sh
    git clone https://github.com/yourusername/local-AI-infra-generation.git
    cd local-AI-infra-generation
    ```
2.  Create and activate a virtual environment:
    ```sh
    python -m venv .venv
    source .venv/bin/activate
    ```
3.  Install in editable mode:
    ```sh
    pip install -e .
    ```
This allows you to make changes to the source code and have them reflected immediately when you run the `infra-gen` command.

### Running Tests

_TODO: Add unit tests and instructions for running them._

---

## Troubleshooting

- **Ollama not found:**  
  Ensure Ollama is installed and available in your PATH.

- **tree-sitter language .so files missing:**  
  If you encounter errors about missing `.so` files, ensure [tree-sitter-languages](https://pypi.org/project/tree-sitter-languages/) is installed and built correctly.

- **Model download issues:**  
  The first run will download required models. Ensure you have a stable internet connection.

---

## TODO

- [ ] Add comprehensive unit and integration tests.
- [ ] Improve error handling and user feedback.
- [ ] Add support for more programming languages (e.g., Java, Rust).
- [ ] Enhance prompt templates for better infrastructure generation.
- [ ] Add web or GUI interface.
- [ ] Document API for programmatic usage.
- [ ] Support for private model registries and custom LLMs.
- [ ] Optimize embedding and retrieval for large codebases.
- [ ] Add CI/CD pipeline for automated testing and deployment.

---

## License

This project is licensed under the [Apache 2.0 License](LICENSE).
