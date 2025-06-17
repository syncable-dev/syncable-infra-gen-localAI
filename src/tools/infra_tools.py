# file: tools/infra_tools.py

import json
import logging
from typing import Any, Dict, List

from langchain.tools import BaseTool
from ..llm_utils import call_llm
from ..utils import read_manifest_file

logger = logging.getLogger(__name__)


class DockerfileServiceTool(BaseTool):
    name: str = "generate_service_dockerfile"
    description: str = (
        "Generate a production-ready Dockerfile for one service. "
        "Input JSON must include keys: project_path, service, summary, tree, "
        "code_context, dockerignore, env_file, config."
    )

    def _run(self, input_json: str) -> str:
        data: Dict[str, Any] = json.loads(input_json)
        project = data["project_path"]
        svc = data["service"]
        summary = data["summary"]
        tree: List[str] = data["tree"]
        code_ctx = data.get("code_context", "")
        dockerignore = data.get("dockerignore", "")
        env_file = data.get("env_file", "")
        config = data["config"]

        svc_path = svc["path"]
        manifest_content = read_manifest_file(project, svc.get("manifest"))

        # build the file list under this service
        if svc_path:
            file_list = [p for p in tree if p.startswith(f"{svc_path}/")]
        else:
            file_list = [p for p in tree if "/" not in p]

        prompt = f"""
            Generate a production-ready Dockerfile for service `{svc['name']}`:
            - Path: `{svc_path or '.'}`
            - Language: {svc.get('language')}
            - Dependency manifest ({svc.get('manifest')}):
            {manifest_content}

            - .dockerignore patterns:
            {dockerignore}

            - Example env file:
            {env_file}

            - Project summary:
            {summary}

            - Relevant code snippets:
            {code_ctx}
            - Files under this service:
            {chr(10).join(f"- {p}" for p in file_list)}

            Include any detected entrypoint ({svc.get('entrypoint')}), port ({svc.get('port')}), 
            environment ({svc.get('env')}), and dependencies ({svc.get('depends_on')}). 
            Output only the Dockerfile content.
            """.strip()

        dockerfile = call_llm(
            prompt,
            base_url=config["ollama_base_url"],
            model=config["models"]["infra_model"],
            temperature=config.get("temperature", 0.0),
        )

        artifact = {
            "path": f"{svc_path}/Dockerfile" if svc_path else "Dockerfile",
            "content": dockerfile.strip()
        }
        return json.dumps(artifact)

    async def _arun(self, input_json: str) -> str:
        return self._run(input_json)


class ComposeTool(BaseTool):
    name: str = "generate_compose"
    description: str = (
        "Generate a docker-compose.yml for multiple services. "
        "Input JSON must include: services, summary, tree, repo_code_context, config."
    )

    def _run(self, input_json: str) -> str:
        data: Dict[str, Any] = json.loads(input_json)
        services: List[Dict[str, Any]] = data["services"]
        summary = data["summary"]
        tree: List[str] = data["tree"]
        repo_ctx = data.get("repo_code_context", "")
        config = data["config"]

        svc_lines = []
        for svc in services:
            svc_lines.append(
                f"- {svc['name']}: path={svc['path'] or '.'}, lang={svc.get('language')}, "
                f"port={svc.get('port')}, entrypoint={svc.get('entrypoint')}, "
                f"env={svc.get('env')}, depends_on={svc.get('depends_on')}"
            )
        services_block = "\n".join(svc_lines)

        prompt = f"""
Generate a docker-compose.yml for this project:
- Project summary:
{summary}

- File tree:
{chr(10).join(f"- {p}" for p in tree)}

- Repository code snippets:
{repo_ctx}
- Services:
{services_block}


Each service should `build:` from its path, use its generated Dockerfile,
map its port, set entrypoint/env, and declare any `depends_on`. 
Output only the docker-compose.yml content.
""".strip()

        compose_yml = call_llm(
            prompt,
            base_url=config["ollama_base_url"],
            model=config["models"]["infra_model"],
            temperature=config.get("temperature", 0.0),
        )

        artifact = {
            "path": "docker-compose.yml",
            "content": compose_yml.strip()
        }
        return json.dumps(artifact)

    async def _arun(self, input_json: str) -> str:
        return self._run(input_json)