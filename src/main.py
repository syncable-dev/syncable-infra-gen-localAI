import argparse
import sys

from .setup_ollama import OllamaSetup
from .utils import load_config
from .chroma_manager import ChromaManager
from .embedder import Embedder
from .retriever import Retriever
from .query_handler import QueryHandler
from .infra_generator import InfraGenerator, ProjectNotEmbedded
from .infra_agent import run_infra_pipeline

def main():
    # 1) Ensure Ollama is running
    OllamaSetup().setup()

    # 2) Core components
    config = load_config()
    chroma_manager = ChromaManager(config['chroma_db_dir'])
    embedder = Embedder(config, chroma_manager)
    retriever = Retriever(config, chroma_manager)
    query_handler = QueryHandler(config, retriever)

    # 3) CLI
    parser = argparse.ArgumentParser(description="Local Codebase Assistant CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Embed
    parser_embed = subparsers.add_parser("embed", help="Embed a project")
    parser_embed.add_argument("project_dir", help="Path to project directory")
    parser_embed.add_argument("--name", help="Optional project name")

    # Ask (RAG-based)
    parser_ask = subparsers.add_parser("ask", help="Ask a question about a codebase")
    parser_ask.add_argument("question", nargs="+", help="Question to ask")
    parser_ask.add_argument("--project", help="Project name")

    # List
    subparsers.add_parser("list", help="List embedded projects")

    # Generate with original InfraGenerator
    parser_docker = subparsers.add_parser("generate-docker", help="Generate Dockerfile for a project")
    parser_docker.add_argument("--project", required=True, help="Project name")
    parser_compose = subparsers.add_parser("generate-compose", help="Generate docker-compose.yml for a project")
    parser_compose.add_argument("--project", required=True, help="Project name")

    # New: full multi-service infra
    parser_infra = subparsers.add_parser("generate-infra", help="Generate full infra for a repo")
    parser_infra.add_argument("source", help="Path or Git URL of the project")
    parser_infra.add_argument("-o", "--output", default="infra", help="Output folder")

    args = parser.parse_args()

    if args.command == "embed":
        embedder.embed_project(args.project_dir, args.name)

    elif args.command == "ask":
        projects = chroma_manager.get_all_projects()
        proj = args.project or (projects[0] if len(projects) == 1 else None)
        if not proj or proj not in projects:
            print("Specify --project from:", projects)
            sys.exit(1)
        answer = query_handler.ask(" ".join(args.question), project=proj)
        print(answer)

    elif args.command == "list":
        for p in chroma_manager.get_all_projects():
            print(p)

    elif args.command == "generate-docker":
        projects = chroma_manager.get_all_projects()
        if args.project not in projects:
            print("Available:", projects); sys.exit(1)
        try:
            infra = InfraGenerator(args.project, config, chroma_manager)
            infra.generate_dockerfile(retriever)
        except ProjectNotEmbedded as e:
            print(e)

    elif args.command == "generate-compose":
        projects = chroma_manager.get_all_projects()
        if args.project not in projects:
            print("Available:", projects); sys.exit(1)
        try:
            infra = InfraGenerator(args.project, config, chroma_manager)
            infra.generate_docker_compose(retriever)
        except ProjectNotEmbedded as e:
            print(e)

    elif args.command == "generate-infra":
        try:
            run_infra_pipeline(args.source, args.output)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(2)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
