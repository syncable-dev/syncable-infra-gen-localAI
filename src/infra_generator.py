import os
import requests
import json
import re
from collections import defaultdict

from .chroma_manager import ChromaManager
from .retriever import Retriever
from .prompt_templates import DOCKERFILE_SYSTEM_PROMPT, DOCKERFILE_USER_PROMPT, DOCKER_COMPOSE_SYSTEM_PROMPT, DOCKER_COMPOSE_USER_PROMPT


from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate

class ProjectNotEmbedded(Exception):
    """Custom exception for when a project is not found in the vector store."""
    pass

class InfraGenerator:
    """
    Generates infrastructure artifacts like Dockerfiles and Docker Compose files
    by leveraging a Large Language Model (LLM) enriched with context from
    a Retrieval-Augmented Generation (RAG) system.
    """
    def __init__(self, project_name: str, config: dict, chroma_manager: ChromaManager):
        self.config = config
        self.chroma_manager = chroma_manager
        self.project_name = project_name
        self.project_dir = self._get_project_dir_from_metadata()

        # Define paths for saving the generated artifacts.
        self.dockerfile_path = os.path.join(self.project_dir, "Dockerfile")
        self.compose_path = os.path.join(self.project_dir, "docker-compose.yml")

    def _get_project_dir_from_metadata(self) -> str:
        """
        Retrieves the project directory path from the metadata stored in ChromaDB.
        """
        projects = self.chroma_manager.get_all_projects()
        if self.project_name not in projects:
            raise ProjectNotEmbedded(f"Project '{self.project_name}' is not embedded. Please embed it first.")
        md = self.chroma_manager.get_project_metadata(self.project_name)
        print(f"Found project metadata: {md}")
        return md.get("project_dir")
    
    def _parse_version_from_manifest(self, manifest_content: str, manifest_filename: str) -> str | None:
        """
        Parses the required language version from a manifest file.
        """
        if "pyproject.toml" in manifest_filename:
            match = re.search(r'python\s*=\s*["\']\^?(\d+\.\d+)', manifest_content)
            if match:
                return match.group(1)
        elif "package.json" in manifest_filename:
            try:
                data = json.loads(manifest_content)
                node_version_spec = data.get("engines", {}).get("node")
                if node_version_spec:
                    match = re.search(r'(\d+)', node_version_spec)
                    if match:
                        return match.group(1)
            except json.JSONDecodeError:
                return None
        elif "go.mod" in manifest_filename:
            match = re.search(r'go\s+(\d+\.\d+)', manifest_content)
            if match:
                return match.group(1)
        return None

    def _get_latest_docker_image_tag(self, image_name: str, version: str | None = None) -> str:
        """
        Constructs a Docker image tag for supported languages.
        """
        print(f"Determining Docker tag for '{image_name}' with detected version '{version}'...")
        if image_name == "python" and version:
            return f"{version}-slim-buster"
        elif image_name in ["node", "javascript", "typescript"] and version:
            major_version = version.split('.')[0]
            return f"{major_version}-alpine"
        elif image_name == "go" and version:
            return f"{version}-alpine"

        print(f"Version for '{image_name}' not detected or language not explicitly supported for version parsing. Using default.")
        latest_tags = {
            "python": "3.11-slim-buster",
            "node": "20-alpine",
            "javascript": "20-alpine",
            "typescript": "20-alpine",
            "go": "1.22-alpine",
            "nginx": "1.25-alpine",
            "postgres": "16-alpine",
            "redis": "7-alpine",
            "rust": "1.78-slim-buster",
        }
        
        if image_name not in latest_tags:
            print(f"Support for '{image_name}' is not implemented yet. Falling back to 'latest'.")
            return "latest"
        return latest_tags.get(image_name)

    def _gather_context_for_prompt(self, retriever: Retriever, summary: str = None, tree: list = None, max_chars: int = 8000) -> dict:
        """
        Gathers context using RAG, including manifest content and language version.
        """
        print("Gathering context using targeted RAG queries...")
        context = {
            "project_name": self.project_name,
            "manifest_content": "Not found.",
            "entrypoint_content": "Not found.",
            "other_relevant_snippets": "No other relevant snippets found.",
            "detected_language_version": None,
            "language_guess": "unknown",
            "summary": summary or "Not found.",
            "tree": "\n".join(tree) if tree else "Not found."
        }
        manifest_query = "content of package.json or requirements.txt or pyproject.toml or go.mod"
        manifest_results = retriever.retrieve_chunks(manifest_query, k=1, project=self.project_name)
        if manifest_results.get(self.project_name):
            manifest_hit = manifest_results[self.project_name][0]
            context["manifest_content"] = manifest_hit['code']
            manifest_filename = manifest_hit.get('file_path', '')
            print(f"Successfully retrieved dependency manifest: {manifest_filename}")
            
            version = self._parse_version_from_manifest(context["manifest_content"], manifest_filename)
            if version:
                context["detected_language_version"] = version
                print(f"Successfully parsed language version from manifest: {version}")
            
            if "py" in manifest_filename: context["language_guess"] = "python"
            elif "package.json" in manifest_filename: context["language_guess"] = "node"
            elif "go.mod" in manifest_filename: context["language_guess"] = "go"

        entrypoint_query = "content of app.py or main.py or server.js or index.js or main.go"
        entrypoint_results = retriever.retrieve_chunks(entrypoint_query, k=1, project=self.project_name)
        if entrypoint_results.get(self.project_name):
            context["entrypoint_content"] = entrypoint_results[self.project_name][0]['code']
            print("Successfully retrieved entrypoint file.")

        service_query = "database connection string or redis client or postgres setup or mongo configuration or environment variables"
        service_results = retriever.retrieve_chunks(service_query, k=10, project=self.project_name)
        
        snippets = []
        current_len = 0
        if service_results.get(self.project_name):
            for hit in service_results[self.project_name]:
                snippet = f"\n# From file: {hit['file_path']}\n{hit['code']}\n"
                if current_len + len(snippet) <= max_chars:
                    snippets.append(snippet)
                    current_len += len(snippet)
                else:
                    break
        if snippets:
            context["other_relevant_snippets"] = "".join(snippets)
            print(f"Successfully retrieved {len(snippets)} relevant code snippets.")
        
        return context

    def _invoke_llm(self, system_prompt_template: str, user_prompt_template: str, context: dict) -> str:
        """
        Invokes the language model by passing templates and context separately.
        This prevents KeyErrors from curly braces in the RAG-retrieved content.
        """
        print("Invoking the Language Model...")
        llm = ChatOllama(
            base_url=self.config['ollama_base_url'],
            model=self.config['models']['qna_model'],
            temperature=0.05
        )
        chat_prompt_template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_prompt_template),
            HumanMessagePromptTemplate.from_template(user_prompt_template)
        ])
        chain = chat_prompt_template | llm
        # Pass the context dictionary here for safe formatting by langchain
        response = chain.invoke(context)
        
        content = response.content.strip()
        if content.startswith("```") and content.endswith("```"):
            content = re.sub(r'^```[a-zA-Z]*\n', '', content, 1)
            content = re.sub(r'\n```$', '', content)
        print("LLM invocation complete.")
        return content

    def _write_file(self, path: str, content: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def generate_dockerfile(self, retriever: Retriever, summary: str = None, tree: list = None) -> None:
        """
        Orchestrates Dockerfile generation using the corrected LLM invocation pattern.
        """
        context = self._gather_context_for_prompt(retriever, summary=summary, tree=tree)
        base_image_name = context.get("language_guess", "unknown")
        detected_version = context.get("detected_language_version")
        latest_base_image_tag = self._get_latest_docker_image_tag(base_image_name, version=detected_version)
        context["latest_base_image_tag"] = latest_base_image_tag

        # Pass templates and context to the LLM invoker, do not pre-format.
        dockerfile_content = self._invoke_llm(
            DOCKERFILE_SYSTEM_PROMPT, 
            DOCKERFILE_USER_PROMPT, 
            context
        )
        self._write_file(self.dockerfile_path, dockerfile_content)
        print(f"SUCCESS: Dockerfile generated at {self.dockerfile_path}")

    def generate_docker_compose(self, retriever: Retriever, summary: str = None, tree: list = None) -> None:
        """
        Orchestrates Docker Compose generation using the corrected LLM invocation pattern.
        """
        if not os.path.isfile(self.dockerfile_path):
            print("Dockerfile not found. Generating it first as it is a dependency for docker-compose.")
            self.generate_dockerfile(retriever, summary=summary, tree=tree)

        context = self._gather_context_for_prompt(retriever, summary=summary, tree=tree)
        context["postgres_image_tag"] = self._get_latest_docker_image_tag("postgres")
        context["redis_image_tag"] = self._get_latest_docker_image_tag("redis")
        
        # Pass templates and context to the LLM invoker, do not pre-format.
        compose_content = self._invoke_llm(
            DOCKER_COMPOSE_SYSTEM_PROMPT, 
            DOCKER_COMPOSE_USER_PROMPT, 
            context
        )
        self._write_file(self.compose_path, compose_content)
        print(f"SUCCESS: docker-compose.yml generated at {self.compose_path}")

    def generate_generic_infrastructure(self, prompt: str, retriever: Retriever) -> str:
        """
        Handles generic IaC requests using the corrected LLM invocation pattern.
        """
        context = self._gather_context_for_prompt(retriever)
        context['user_specific_request'] = prompt

        generic_system_prompt = """
        You are a world-class Cloud Infrastructure Engineer. Your task is to generate Infrastructure as Code (IaC).
        Prioritize security, scalability, reliability, and cost-effectiveness. Adhere to the principle of least privilege, idempotence, and maintainability.
        Output ONLY the requested IaC content, without conversational text or markdown wrappers.
        """
        
        generic_user_template = """
        **User's Infrastructure Request:**
        {user_specific_request}
        
        ---
        **CONTEXT ABOUT THE APPLICATION**

        **Project Name:** {project_name}

        **Dependency Manifest (e.g., package.json, requirements.txt):**
        ```
        {manifest_content}
        ```
        
        **Main Entrypoint File:**
        ```
        {entrypoint_content}
        ```
        
        **Other Relevant Code Snippets:**
        ```
        {other_relevant_snippets}
        ```
        ---
        Based on the user's request and the provided application context, generate the required IaC.
        """
        
        return self._invoke_llm(generic_system_prompt, generic_user_template, context)
