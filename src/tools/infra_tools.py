import json
import logging
import os
from typing import Any, Dict, List

# Langchain and LLM components
from langchain.tools import BaseTool
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate

# Import the structured prompt templates we created
from ..prompt_templates import DOCKERFILE_SYSTEM_PROMPT, DOCKERFILE_USER_PROMPT, DOCKER_COMPOSE_SYSTEM_PROMPT, DOCKER_COMPOSE_USER_PROMPT

logger = logging.getLogger(__name__)

# --- Helper Functions ---

def _get_latest_docker_image_tag(image_name: str) -> str:
    """
    Helper to get a default stable tag for common service images.
    In a real system, this could be expanded to parse versions from service context.
    """
    latest_tags = {
        "postgres": "16-alpine",
        "redis": "7-alpine",
        "mysql": "8.0",
        "mongo": "7.0",
    }
    return latest_tags.get(image_name, "latest")

def _invoke_llm(system_prompt: str, user_prompt: str, context: dict, config: dict) -> str:
    """
    A standardized function to invoke the language model, passing templates
    and context separately to avoid formatting errors.
    """
    logger.info("Invoking LLM for infrastructure generation...")
    llm = ChatOllama(
        base_url=config['ollama_base_url'],
        model=config['models']['qna_model'], 
        temperature=config.get("temperature", 0.05)
    )
    
    chat_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(system_prompt),
        HumanMessagePromptTemplate.from_template(user_prompt)
    ])
    
    chain = chat_prompt | llm
    
    # Safely invoke the chain with the context dictionary
    response = chain.invoke(context)
    
    logger.info("LLM invocation complete.")
    return response.content.strip()

# --- Refactored Tools ---

class DockerfileServiceTool(BaseTool):
    name: str = "generate_service_dockerfile"
    description: str = (
        "Generate a production-ready Dockerfile for one service using RAG context and best-practice templates. "
        "Input JSON must include keys: service, summary, tree, code_context, config."
    )

    def _run(self, input_json: str) -> str:
        """
        This method now acts as an orchestrator. It prepares the context
        and calls the LLM with our high-quality, structured prompt templates.
        """
        data: Dict[str, Any] = json.loads(input_json)
        
        # 1. Prepare the context dictionary required by the prompt template
        svc = data["service"]
        context = {
            "project_name": svc.get("name", "unknown-service"),
            "summary": data.get("summary", "No summary provided."),
            "tree": "\n".join(data.get("tree", [])),
            "tree_list": data.get("tree_list", "[]"),
            "manifest_content": svc.get("manifest_content", "Manifest not found."),
            # Assuming the agent provides these context keys
            "entrypoint_content": data.get("code_context", ""),
            "other_relevant_snippets": "", # Can be enriched by the agent if needed
            # Use a default tag, as service-specific version detection is complex
            "latest_base_image_tag": f"{svc.get('language', 'generic')}:latest" 
        }

        # 2. Invoke the LLM using the helper and our templates
        dockerfile = _invoke_llm(
            DOCKERFILE_SYSTEM_PROMPT,
            DOCKERFILE_USER_PROMPT,
            context,
            data["config"]
        )

        # 3. Format the output artifact
        service_path = svc.get("path", "")
        artifact = {
            "path": os.path.join(service_path, "Dockerfile"),
            "content": dockerfile
        }
        return json.dumps(artifact)

    async def _arun(self, input_json: str) -> str:
        return self._run(input_json)


class ComposeTool(BaseTool):
    name: str = "generate_compose"
    description: str = (
        "Generate a docker-compose.yml for multiple services using RAG context and best-practice templates."
        "Input JSON must include: services, summary, tree, repo_code_context, config."
    )

    def _run(self, input_json: str) -> str:
        """
        Prepares context for the docker-compose template and invokes the LLM.
        """
        data: Dict[str, Any] = json.loads(input_json)
        
        # 1. Prepare the context dictionary
        # The compose prompt is simpler and can infer details from the service list
        context = {
            "project_name": data.get("project_name", "multi-service-project"),
            "summary": data.get("summary", "No summary provided."),
            "tree": "\n".join(data.get("tree", [])),
            # Pass the manifest/entrypoint content of the *first* service as a representative example
            "manifest_content": data["services"][0].get("manifest_content", "Manifest not found.") if data.get("services") else "",
            "entrypoint_content": data.get("repo_code_context", ""),
            "other_relevant_snippets": "",
            # Provide fresh tags for common services
            "postgres_image_tag": _get_latest_docker_image_tag("postgres"),
            "redis_image_tag": _get_latest_docker_image_tag("redis"),
        }

        # 2. Invoke the LLM with the compose templates
        compose_yml = _invoke_llm(
            DOCKER_COMPOSE_SYSTEM_PROMPT,
            DOCKER_COMPOSE_USER_PROMPT,
            context,
            data["config"]
        )

        # 3. Format the output artifact
        artifact = {
            "path": "docker-compose.yml",
            "content": compose_yml
        }
        return json.dumps(artifact)

    async def _arun(self, input_json: str) -> str:
        return self._run(input_json)
