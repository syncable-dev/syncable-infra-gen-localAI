import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from .utils import load_config
from .chroma_manager import ChromaManager
from .embedder import Embedder
from .retriever import Retriever
from .query_handler import QueryHandler
from .tools.git_tools import GitIngestTool, DetectServicesTool
from .tools.infra_tools import DockerfileServiceTool, ComposeTool

logger = logging.getLogger(__name__)


def run_infra_pipeline(
    source: str,
    output_folder: str
) -> None:
    """
    1) Ingest via gitingest
    2) Ensure embedded in Chroma
    3) RAG-retrieve repo-level & per-service snippets via QueryHandler
    4) Detect services (manifest-based)
    5) Infer missing metadata (entrypoint, port, env, depends_on)
    6) Generate Dockerfile per service
    7) Generate docker-compose.yml
    8) Write all artifacts under source/output_folder/
    """
    config = load_config()

    # --- Setup embedding & retrieval ---
    chroma_manager = ChromaManager(config["chroma_db_dir"])
    embedder = Embedder(config, chroma_manager)
    retriever = Retriever(config, chroma_manager)
    query_handler = QueryHandler(config, retriever)

    # Embed project if new
    project_name = Path(source).stem
    if project_name not in chroma_manager.get_all_projects():
        embedder.embed_project(source, project_name)

    # 1) Ingest via gitingest
    ingest_tool = GitIngestTool(exclude_patterns=set(config.get("exclude_patterns", [])))
    ingest_res = ingest_tool.run(source)
    ingest_data: Dict[str, Any] = json.loads(ingest_res)
    summary: str = ingest_data["summary"]
    tree: List[str] = ingest_data["tree"]
    content: Dict[str, str] = ingest_data["content"]

    # 2) Build repo-level context for Compose
    repo_ctx = query_handler.build_context(
        query="docker compose service",
        k=config.get("rag_k", 5),
        project=project_name,
        max_context_length=config.get("max_code_context_chars", 2000),
    )

    # 3) Detect services by manifest
    services: List[Dict[str, Any]] = json.loads(
        DetectServicesTool().run(ingest_res)
    )
    if not services:
        raise RuntimeError(f"No services detected in {source}")

    artifacts: List[Dict[str, Any]] = []

    # 4) For each service, RAG-retrieve and generate Dockerfile
    docker_tool = DockerfileServiceTool()
    for svc in services:
        # 4a) Per-service context
        svc_ctx = query_handler.build_context(
            query=f"{svc['name']} service dockerfile",
            k=config.get("rag_k", 5),
            project=project_name,
            max_context_length=config.get("max_code_context_chars", 2000),
        )

        # 4b) Read .dockerignore and .env* from ingest content
        dockerignore = content.get(os.path.join(svc["path"], ".dockerignore"), "")
        env_file = ""
        for name in (".env", ".env.example"):
            p = os.path.join(svc["path"], name)
            if p in content:
                env_file = content[p]
                break

        payload = {
            "project_path": source,
            "service": svc,
            "summary": summary,
            "tree": tree,
            "code_context": svc_ctx,
            "dockerignore": dockerignore,
            "env_file": env_file,
            "config": config
        }
        art = docker_tool.run(json.dumps(payload))
        artifacts.append(json.loads(art))

    # 5) Generate docker-compose.yml
    compose_tool = ComposeTool()
    comp_payload = {
        "services": services,
        "summary": summary,
        "tree": tree,
        "repo_code_context": repo_ctx,
        "config": config
    }
    comp_art = compose_tool.run(json.dumps(comp_payload))
    artifacts.append(json.loads(comp_art))

    # 6) Write out files
    for art in artifacts:
        dest = os.path.join(source, output_folder, art["path"])
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(art["content"])
        logger.info("Wrote %s", dest)
