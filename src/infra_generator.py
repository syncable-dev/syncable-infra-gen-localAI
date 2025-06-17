import os
import requests

from .chroma_manager import ChromaManager
from .retriever import Retriever
from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

class ProjectNotEmbedded(Exception):
    pass

class InfraGenerator:
    def __init__(self, project_name: str, config: dict, chroma_manager: ChromaManager):
        self.config = config
        self.chroma_manager = chroma_manager
        self.project_name = project_name
        self.project_dir = self._get_project_dir_from_metadata()
        self.language, self.metadata_file = self.detect_language_and_framework()
        self.deps = self.extract_dependencies()
        self.dockerfile_path = os.path.join(self.project_dir, "Dockerfile")
        self.compose_path = os.path.join(self.project_dir, "docker-compose.yml")

    def _get_project_dir_from_metadata(self) -> str:
        projects = self.chroma_manager.get_all_projects()
        if self.project_name not in projects:
            raise ProjectNotEmbedded(f"Project '{self.project_name}' is not embedded. Please embed it first.")
        md = self.chroma_manager.get_project_metadata(self.project_name)
        return md.get("project_dir")

    def detect_language_and_framework(self):
        from .utils import list_source_files
        files = list_source_files(self.project_dir, self.config["extensions"].values())
        if any(f.endswith("requirements.txt") for f in files):
            return "python", "requirements.txt"
        if any(f.endswith("pyproject.toml") for f in files):
            return "python", "pyproject.toml"
        if any(f.endswith("poetry.lock") for f in files):
            return "python", "poetry.lock"
        if any(f.endswith("package.json") for f in files):
            if any(f.endswith(".ts") for f in files):
                return "typescript", "package.json"
            return "javascript", "package.json"
        if any(f.endswith("go.mod") for f in files):
            return "go", "go.mod"
        if any(f.endswith("Cargo.toml") for f in files):
            return "rust", "Cargo.toml"
        return "unknown", None

    def extract_dependencies(self) -> str:
        if not self.metadata_file:
            return ""
        meta_path = os.path.join(self.project_dir, self.metadata_file)
        if not os.path.isfile(meta_path):
            return ""
        with open(meta_path, "r", encoding="utf-8") as f:
            return f.read()

    def _get_relevant_code_context(self, retriever: Retriever, max_chars: int = 4000) -> str:
        """
        Retrieve relevant code snippets for the project, truncated to fit within max_chars.
        """
        code_results = retriever.retrieve_chunks(
            "docker|compose|service|main|entrypoint|requirements|dependencies|config|setup|init", k=10, project=self.project_name
        )
        context = ""
        for proj, hits in code_results.items():
            for hit in hits:
                snippet = f"\n# From {hit['file_path']} (lines {hit['start_line']}-{hit['end_line']}):\n{hit['code']}\n"
                if len(context) + len(snippet) > max_chars:
                    return context
                context += snippet
        return context

    def generate_dockerfile(self, retriever: Retriever, max_context_chars: int = 40000) -> None:
        relevant_code = self._get_relevant_code_context(retriever, max_context_chars)
        prompt = (
            f"Generate a production-ready Dockerfile for a {self.language} project. "
            f"Here is the dependency manifest ({self.metadata_file}):\n\n{self.deps}\n"
            f"Relevant code context:\n{relevant_code}\n"
            f"Output only the Dockerfile content."
        )
        dockerfile_content = self._invoke_llm(prompt)
        self._write_file(self.dockerfile_path, dockerfile_content)
        print(f"Dockerfile generated at {self.dockerfile_path}")

    def generate_docker_compose(self, retriever: Retriever, max_context_chars: int = 40000) -> None:
        if not os.path.isfile(self.dockerfile_path):
            print(f"Warning: Dockerfile not found. Generating Dockerfile first...")
            self.generate_dockerfile(retriever, max_context_chars)
        relevant_code = self._get_relevant_code_context(retriever, max_context_chars)
        prompt = (
            f"Generate a docker-compose.yml file for a {self.language} project. "
            f"The following dependencies are found in {self.metadata_file}:\n\n{self.deps}\n"
            f"Relevant code context:\n{relevant_code}\n"
            f"Assume the app requires any detected services (e.g., Postgres, Redis). "
            f"Output only the docker-compose.yml content."
        )
        compose_content = self._invoke_llm(prompt)
        self._write_file(self.compose_path, compose_content)
        print(f"docker-compose.yml generated at {self.compose_path}")

    def generate_infrastructure(self, prompt: str, retriever: Retriever, query: str = None) -> str:
        """
        Generate infrastructure using LangChain's Ollama integration.
        Retrieves relevant code snippets and uses them in the prompt for generation.
        """
        relevant_code = ""
        if query:
            code_results = retriever.retrieve_chunks(query, k=5, project=self.project_name)
            for proj, hits in code_results.items():
                for hit in hits:
                    relevant_code += f"\n# From {hit['file_path']} (lines {hit['start_line']}-{hit['end_line']}):\n{hit['code']}\n"
        full_prompt = f"{prompt}\n\nRelevant code snippets:\n{relevant_code}"
        return self._invoke_llm(full_prompt)

    def _invoke_llm(self, prompt: str) -> str:
        """
        Helper to invoke the LLM with a prompt and return the response content.
        """
        llm = ChatOllama(
            base_url=self.config['ollama_base_url'],
            model=self.config['models']['qna_model']
        )
        chat_prompt = ChatPromptTemplate.from_template("""{input}""")
        chain = chat_prompt | llm
        response = chain.invoke({"input": prompt})
        return response.content

    def _write_file(self, path: str, content: str) -> None:
        """
        Helper to write content to a file, ensuring the directory exists.
        """
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
