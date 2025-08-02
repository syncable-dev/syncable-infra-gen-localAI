import json
import logging
import os
import re
import time

from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain_ollama import ChatOllama

from .chroma_manager import ChromaManager
from .prompt_templates import (
    DOCKER_COMPOSE_SYSTEM_PROMPT,
    DOCKER_COMPOSE_USER_PROMPT,
    DOCKERFILE_SYSTEM_PROMPT,
    DOCKERFILE_USER_PROMPT,
)
from .retriever import Retriever


class ProjectNotEmbedded(Exception):
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
        self.dockerfile_path = os.path.join(self.project_dir, "Dockerfile")
        self.compose_path = os.path.join(self.project_dir, "docker-compose.yml")

    def _get_project_dir_from_metadata(self) -> str:
        """
        Retrieves the project directory path from the metadata stored in ChromaDB.
        """
        projects = self.chroma_manager.get_all_projects()
        if self.project_name not in projects:
            raise ProjectNotEmbedded(
                f"Project '{self.project_name}' is not embedded. "
                "Please embed it first."
            )
        md = self.chroma_manager.get_project_metadata(self.project_name)
        print(f"Found project metadata: {md}")
        return md.get("project_dir")

    def _detect_services_and_versions(self, manifest_files: list) -> list:
        logger = logging.getLogger("infra-generator")
        t0 = time.time()
        logger.info(
            f"Received {len(manifest_files)} manifest files for service detection."
        )
        services = []
        for mf in manifest_files:
            mf_path = mf.get("path")
            content = mf.get("content", "")
            llm_prompt = f"""
            Given the following manifest file content and filename, extract:
            - The programming language (python, node, go, etc)
            - The main version (e.g. 3.11 for python, 20 for node, 1.22 for go)
            - The service name (use the folder name or 'root_service' if at root)
            Output as JSON: {{\"language\":..., \"version\":..., \"service_name\":...}}
            Manifest filename: {mf_path}\nContent:\n{content}
            """
            print(f"LLM prompt for {mf_path}:\n{llm_prompt}")
            llm = ChatOllama(
                base_url=self.config["ollama_base_url"],
                model=self.config["models"]["qna_model"],
                temperature=0.0,
            )
            t_llm = time.time()
            result = llm.invoke(llm_prompt).content.strip()
            logger.info(
                f"LLM manifest parse for {mf_path} took {time.time() - t_llm:.1f}s"
            )
            try:
                parsed = json.loads(result)
            except Exception:
                parsed = {
                    "language": "unknown",
                    "version": None,
                    "service_name": os.path.basename(os.path.dirname(mf_path))
                    or "root_service",
                }
            services.append(
                {
                    "name": parsed.get(
                        "service_name",
                        os.path.basename(os.path.dirname(mf_path)) or "root_service",
                    ),
                    "path": os.path.dirname(mf_path),
                    "language": parsed.get("language", "unknown"),
                    "manifest_path": mf_path,
                    "manifest_content": content,
                    "version": parsed.get("version"),
                }
            )
        logger.info(
            f"Service/manifest detection for {len(manifest_files)} manifest(s) "
            f"took {time.time() - t0:.1f}s"
        )
        return services

    def _gather_context_for_prompt(
        self,
        retriever: Retriever,
        summary: str = None,
        tree: list = None,
        max_chars: int = 8000,
    ) -> dict:
        logger = logging.getLogger("infra-generator")
        t0 = time.time()
        context = {
            "project_name": self.project_name,
            "manifest_content": "",
            "entrypoint_content": "",
            "other_relevant_snippets": "",
            "detected_language_version": None,
            "language_guess": "unknown",
            "summary": summary or "",
            "tree": "\n".join(tree) if tree else "",
            "tree_list": json.dumps(tree, indent=2) if tree else "[]",
        }
        services = self._detect_services_and_versions(tree or [])
        if services:
            svc = services[0]
            context["manifest_content"] = svc["manifest_content"]
            context["detected_language_version"] = svc["version"]
            context["language_guess"] = svc["language"]
        entry_candidates = [
            f
            for f in (tree or [])
            if any(
                x in f
                for x in ["app.py", "main.py", "server.js", "index.js", "main.go"]
            )
        ]
        if entry_candidates:
            entry_path = os.path.join(self.project_dir, entry_candidates[0])
            try:
                with open(entry_path, "r", encoding="utf-8") as f:
                    context["entrypoint_content"] = f.read()
            except Exception:
                pass
        service_query = (
            "database connection string or redis client or postgres setup or "
            "mongo configuration or environment variables"
        )
        t_retrieve = time.time()
        service_results = retriever.retrieve_chunks(
            service_query, k=10, project=self.project_name
        )
        logger.info(
            f"Retriever query for additional code snippets took "
            f"{time.time() - t_retrieve:.1f}s"
        )
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
        logger.info(f"Context gathering took {time.time() - t0:.1f}s")
        return context

    def _invoke_llm(
        self, system_prompt_template: str, user_prompt_template: str, context: dict
    ) -> str:
        logger = logging.getLogger("infra-generator")
        t0 = time.time()
        llm = ChatOllama(
            base_url=self.config["ollama_base_url"],
            model=self.config["models"]["qna_model"],
            temperature=0.05,
        )
        chat_prompt_template = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(system_prompt_template),
                HumanMessagePromptTemplate.from_template(user_prompt_template),
            ]
        )
        chain = chat_prompt_template | llm
        response = chain.invoke(context)
        content = response.content.strip()
        if content.startswith("```") and content.endswith("```"):
            content = re.sub(r"^```[a-zA-Z]*\n", "", content, 1)
            content = re.sub(r"\n```$", "", content)
        logger.info(
            f"LLM invocation for prompt '{system_prompt_template[:30]}...' "
            f"took {time.time() - t0:.1f}s"
        )
        return content

    def _write_file(self, path: str, content: str) -> None:
        logger = logging.getLogger("infra-generator")
        t0 = time.time()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Wrote file {path} in {time.time() - t0:.1f}s")

    def _get_latest_docker_image_tag(
        self, image_name: str, version: str | None = None
    ) -> str:
        if image_name == "python" and version:
            return f"{version}-slim-buster"
        elif image_name in ["node", "javascript", "typescript"] and version:
            major_version = str(version).split(".")[0]
            return f"{major_version}-alpine"
        elif image_name == "go" and version:
            return f"{version}-alpine"
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
        return latest_tags.get(image_name, "latest")

    def _clean_docker_output(self, content: str) -> str:
        """
        Clean LLM output to remove markdown/code block wrappers, #GOOD/#BAD
        comments, and any non-Dockerfile/Compose content. Handles triple
        backticks and language specifiers robustly.
        """
        # Remove all code block wrappers (triple backticks, with or without language)
        content = re.sub(r"^\s*```[a-zA-Z]*\s*", "", content, flags=re.MULTILINE)
        content = re.sub(r"\s*```\s*$", "", content, flags=re.MULTILINE)
        # Remove #GOOD/#BAD and any example comments
        content = re.sub(r"(?m)^\s*#\s*(GOOD|BAD).*$", "", content)
        # Remove any lines that are just whitespace
        content = "\n".join([line for line in content.splitlines() if line.strip()])
        return content

    def generate_dockerfile(
        self, retriever: Retriever, summary: str = None, tree: list = None
    ) -> None:
        context = self._gather_context_for_prompt(retriever, summary=summary, tree=tree)
        base_image_name = context.get("language_guess", "unknown")
        detected_version = context.get("detected_language_version")
        latest_base_image_tag = self._get_latest_docker_image_tag(
            base_image_name, version=detected_version
        )
        context["latest_base_image_tag"] = latest_base_image_tag
        dockerfile_content = self._invoke_llm(
            DOCKERFILE_SYSTEM_PROMPT, DOCKERFILE_USER_PROMPT, context
        )
        dockerfile_content = self._clean_docker_output(dockerfile_content)
        self._write_file(self.dockerfile_path, dockerfile_content)

    def generate_docker_compose(
        self, retriever: Retriever, summary: str = None, tree: list = None
    ) -> None:
        if not os.path.isfile(self.dockerfile_path):
            self.generate_dockerfile(retriever, summary=summary, tree=tree)
        context = self._gather_context_for_prompt(retriever, summary=summary, tree=tree)
        context["postgres_image_tag"] = self._get_latest_docker_image_tag("postgres")
        context["redis_image_tag"] = self._get_latest_docker_image_tag("redis")
        compose_content = self._invoke_llm(
            DOCKER_COMPOSE_SYSTEM_PROMPT, DOCKER_COMPOSE_USER_PROMPT, context
        )
        compose_content = self._clean_docker_output(compose_content)
        self._write_file(self.compose_path, compose_content)

    def generate_generic_infrastructure(
        self, prompt: str, retriever: Retriever, tree: list = None, summary: str = None
    ) -> str:
        context = self._gather_context_for_prompt(retriever, summary=summary, tree=tree)
        context["user_specific_request"] = prompt
        generic_system_prompt = (
            "You are a world-class Cloud Infrastructure Engineer. Your task is to "
            "generate Infrastructure as Code (IaC). Prioritize security, "
            "scalability, reliability, and cost-effectiveness. Adhere to the "
            "principle of least privilege, idempotence, and maintainability. "
            "Output ONLY the requested IaC content, without conversational text "
            "or markdown wrappers."
        )
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
