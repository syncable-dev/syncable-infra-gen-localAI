import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List

from .chroma_manager import ChromaManager
from .embedder import Embedder
from .infra_generator import InfraGenerator
from .query_handler import QueryHandler
from .retriever import Retriever
from .tools.git_tools import GitIngestTool
from .tools.infra_tools import ComposeTool, DockerfileServiceTool
from .utils import load_config

logger = logging.getLogger(__name__)


def llm_parse_tree(tree_str: str, config: dict) -> list:
    """
    Use the LLM to parse a pretty-printed directory tree string into a list of
    relative manifest file paths only.
    """
    from langchain_ollama import ChatOllama

    manifest_filenames = [
        "package.json",
        "requirements.txt",
        "pyproject.toml",
        "Pipfile",
        "environment.yml",
        "setup.py",
        "poetry.lock",
        "yarn.lock",
        "Dockerfile",
        "go.mod",
        "go.sum",
        "Gemfile",
        "composer.json",
        "Cargo.toml",
        "Cargo.lock",
        "build.gradle",
        "pom.xml",
    ]
    manifest_patterns = ", ".join(f'"{name}"' for name in manifest_filenames)
    llm = ChatOllama(
        base_url=config["ollama_base_url"],
        model=config["models"]["qna_model"],
        temperature=0.0,
    )
    prompt = f"""
    Given the following directory tree (as output by the `tree` command),
    extract and return a JSON list of all file paths (relative to the root)
    that are manifest files. Manifest files are any files with the following
    names: {manifest_patterns}.
    Do not include any other files or directories. Output only the JSON list,
    nothing else.

    Directory tree:
    {tree_str}
    """
    result = llm.invoke(prompt).content.strip()
    try:
        file_list = json.loads(result)
        if isinstance(file_list, list):
            return file_list
    except Exception:
        pass
    # fallback: return empty list if LLM fails
    return []


def run_infra_pipeline(source: str, output_folder: str) -> None:
    config = load_config()

    # --- Setup core components ---
    chroma_manager = ChromaManager(config["chroma_db_dir"])
    embedder = Embedder(config, chroma_manager)
    retriever = Retriever(config, chroma_manager)
    query_handler = QueryHandler(config, retriever)

    project_name = Path(source).stem
    t0 = time.time()

    # --- Embed project if it's new ---
    if project_name not in chroma_manager.get_all_projects():
        logger.info(f"Project '{project_name}' not found. Embedding source: {source}")
        t_embed = time.time()
        embedder.embed_project(source, project_name)
        logger.info(f"Embedding complete. Time taken: {time.time() - t_embed:.1f}s")
    else:
        logger.info(f"Project '{project_name}' already embedded.")

    # 1) Ingest project summary
    logger.info("Ingesting project summary...")
    t_ingest = time.time()
    ingest_tool = GitIngestTool(
        exclude_patterns=set(config.get("exclude_patterns", []))
    )
    ingest_res = ingest_tool.run(source)
    ingest_data: Dict[str, Any] = json.loads(ingest_res)
    summary: str = ingest_data["summary"]
    logger.info(f"Project summary: {summary}")
    logger.info(
        f"Project summary ingestion complete. Time taken: "
        f"{time.time() - t_ingest:.1f}s"
    )

    # Use file tree from ingest
    tree = ingest_data.get("tree") or []
    logger.info(f"Project tree datatype: {type(tree)}")
    logger.info(f"Project tree: {tree}")
    # If tree is a string, use LLM to parse it robustly
    if isinstance(tree, str):
        all_file_paths = llm_parse_tree(tree, config)
        logger.info(
            f"LLM parsed {len(all_file_paths)} manifest file paths from pretty "
            "tree."
        )
        manifest_paths = all_file_paths
    else:
        all_file_paths = tree
        manifest_paths = tree  # fallback, but should be list of strings

    # Read manifest file contents
    manifest_files = []
    for fpath in manifest_paths:
        abs_path = os.path.join(source, fpath)
        try:
            with open(abs_path, "r", encoding="utf-8") as mf:
                content = mf.read()
        except Exception as e:
            logger.warning(f"Could not read manifest {abs_path}: {e}")
            content = ""
        manifest_files.append({"path": fpath, "content": content})

    # 3) Detect services and versions
    logger.info("Detecting services and versions...")
    t_detect = time.time()
    infra_gen = InfraGenerator(project_name, config, chroma_manager)
    services = infra_gen._detect_services_and_versions(manifest_files)
    logger.info(
        f"Service detection complete. Found {len(services)} service(s). "
        f"Time taken: {time.time() - t_detect:.1f}s"
    )
    if not services:
        raise RuntimeError(
            f"Could not detect any services in {source}. Check for manifest "
            "files (e.g., package.json, requirements.txt)."
        )

    artifacts: List[Dict[str, Any]] = []

    # 4) Generate Dockerfile for each detected service
    docker_tool = DockerfileServiceTool()
    for svc in services:
        logger.info(f"Preparing to generate Dockerfile for service: '{svc['name']}'")
        t_docker = time.time()
        svc_ctx = query_handler.build_context(
            query=(
                f"code snippets for {svc['name']} {svc['language']} service "
                "entrypoint, server setup, and dependencies"
            ),
            k=config.get("rag_k", 5),
            project=project_name,
            max_context_length=config.get("max_code_context_chars", 2000),
        )

        payload = {
            "service": svc,
            "summary": summary,
            "tree": all_file_paths,  # pass the list of file paths, not manifest dicts
            "tree_list": json.dumps(
                all_file_paths, indent=2
            ),  # pretty JSON for LLM prompt
            "code_context": svc_ctx,
            "config": config,
        }
        art_json = docker_tool.run(json.dumps(payload))
        artifacts.append(json.loads(art_json))
        logger.info(
            f"Dockerfile for '{svc['name']}' generated in {time.time() - t_docker:.1f}s"
        )

    # 5) Generate docker-compose.yml for all services
    logger.info("Preparing to generate docker-compose.yml for all services...")
    t_compose = time.time()
    repo_ctx = query_handler.build_context(
        query=(
            "top-level configuration, docker-compose examples, "
            "inter-service communication"
        ),
        k=config.get("rag_k", 5),
        project=project_name,
        max_context_length=config.get("max_code_context_chars", 2000),
    )
    compose_tool = ComposeTool()
    comp_payload = {
        "project_name": project_name,
        "services": services,
        "summary": summary,
        "tree": all_file_paths,  # pass the list of file paths, not manifest dicts
        "tree_list": json.dumps(all_file_paths, indent=2),  # pretty JSON for LLM prompt
        "repo_code_context": repo_ctx,
        "config": config,
    }
    comp_art_json = compose_tool.run(json.dumps(comp_payload))
    artifacts.append(json.loads(comp_art_json))
    logger.info(f"docker-compose.yml generated in {time.time() - t_compose:.1f}s")

    # 6) Write all generated artifacts to the specified output folder
    logger.info("Writing all generated artifacts to disk...")
    t_write = time.time()
    output_path = os.path.join(source, output_folder)
    for art in artifacts:
        dest = os.path.join(output_path, art["path"])
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(art["content"])
        logger.info("Wrote %s", dest)
    logger.info(f"All artifacts written in {time.time() - t_write:.1f}s")
    logger.info(
        "Infrastructure generation pipeline finished successfully. "
        f"Total time: {time.time() - t0:.1f}s"
<<<<<<< HEAD
    )
=======
    )
>>>>>>> main
