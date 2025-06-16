import argparse
from .setup_ollama import OllamaSetup
from .utils import load_config
from .chroma_manager import ChromaManager
from .embedder import Embedder
from .retriever import Retriever
from .query_handler import QueryHandler
from .infra_generator import InfraGenerator, ProjectNotEmbedded

def main():
    # Always ensure Ollama is ready before using anything
    ollama = OllamaSetup()
    ollama.setup()

    config = load_config()
    chroma_manager = ChromaManager(config['chroma_db_dir'])
    embedder = Embedder(config, chroma_manager)
    retriever = Retriever(config, chroma_manager)
    query_handler = QueryHandler(config, retriever)

    parser = argparse.ArgumentParser(description="Local Codebase Assistant CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Embed
    parser_embed = subparsers.add_parser("embed", help="Embed a project")
    parser_embed.add_argument("project_dir", type=str, help="Path to project directory")
    parser_embed.add_argument("--name", type=str, default=None, help="Optional project name for reference")

    # Ask
    parser_ask = subparsers.add_parser("ask", help="Ask a question about a codebase")
    parser_ask.add_argument("question", type=str, nargs='+', help="Question to ask")
    parser_ask.add_argument("--project", type=str, default=None, help="Project name to search in (if not set, searches all projects)")

    # List
    parser_list = subparsers.add_parser("list", help="List all embedded projects")

    # Generate Dockerfile
    parser_docker = subparsers.add_parser("generate-docker", help="Generate Dockerfile for a project")
    parser_docker.add_argument("--project", type=str, required=True, help="Project name to generate Dockerfile for")

    # Generate Compose
    parser_compose = subparsers.add_parser("generate-compose", help="Generate docker-compose.yml for a project")
    parser_compose.add_argument("--project", type=str, required=True, help="Project name to generate docker-compose.yml for")

    args = parser.parse_args()

    if args.command == "embed":
        embedder.embed_project(args.project_dir, args.name)
    elif args.command == "ask":
        answer = query_handler.ask(' '.join(args.question), project=args.project)
        print(answer)
    elif args.command == "list":
        projects = chroma_manager.get_all_projects()
        if not projects:
            print("No projects embedded yet.")
        else:
            print("Embedded projects:")
            for proj in projects:
                print(f" - {proj}")
    elif args.command == "generate-docker":
        try:
            infra = InfraGenerator(args.project, config, chroma_manager)
            infra.generate_dockerfile()
        except ProjectNotEmbedded as e:
            print(str(e))
    elif args.command == "generate-compose":
        try:
            infra = InfraGenerator(args.project, config, chroma_manager)
            infra.generate_docker_compose()
        except ProjectNotEmbedded as e:
            print(str(e))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
