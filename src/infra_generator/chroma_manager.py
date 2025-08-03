import os
<<<<<<< HEAD

import chromadb

=======
import chromadb
from chromadb.config import Settings
>>>>>>> main

class ChromaManager:
    def __init__(self, chroma_db_dir: str):
        self.chroma_db_dir = chroma_db_dir
        self.client = chromadb.PersistentClient(path=self.chroma_db_dir)

    def get_all_projects(self):
        # Return all ChromaDB collection names (not directory names)
        return [col.name for col in self.client.list_collections()]

    def get_collection(self, project_name: str, project_dir: str = None):
        """Get or create a collection. If creating, set project_dir as metadata."""
        if project_dir is not None:
<<<<<<< HEAD
            return self.client.get_or_create_collection(
                name=project_name,
                metadata={"project_dir": os.path.abspath(project_dir)},
            )
=======
            return self.client.get_or_create_collection(name=project_name, metadata={"project_dir": os.path.abspath(project_dir)})
>>>>>>> main
        else:
            return self.client.get_or_create_collection(name=project_name)

    def get_project_metadata(self, project_name: str):
        collection = self.get_collection(project_name)
        return getattr(collection, "metadata", {})

<<<<<<< HEAD

=======
>>>>>>> main
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Explore ChromaDB collections.")
<<<<<<< HEAD
    parser.add_argument(
        "--db_dir", type=str, required=True, help="Path to ChromaDB directory"
    )
    parser.add_argument("--list", action="store_true", help="List all collections")
    parser.add_argument(
        "--preview", type=str, help="Preview documents in a collection (by name)"
    )
    parser.add_argument(
        "--limit", type=int, default=5, help="Limit of documents to preview"
    )
=======
    parser.add_argument("--db_dir", type=str, required=True, help="Path to ChromaDB directory")
    parser.add_argument("--list", action="store_true", help="List all collections")
    parser.add_argument("--preview", type=str, help="Preview documents in a collection (by name)")
    parser.add_argument("--limit", type=int, default=5, help="Limit of documents to preview")
>>>>>>> main
    parser.add_argument("--delete", type=str, help="Delete a collection by name")
    args = parser.parse_args()

    manager = ChromaManager(chroma_db_dir=args.db_dir)

    if args.list:
        collections = manager.client.list_collections()
        if collections:
            print("Collections:")
            for col in collections:
                print(f" - {col.name}")
        else:
            print("No collections found.")

    elif args.preview:
        try:
            col = manager.client.get_collection(name=args.preview)
            data = col.get(limit=args.limit)
            print(f"Previewing up to {args.limit} documents from '{args.preview}':")
            for i, doc in enumerate(data["documents"]):
                print(f"\n--- Document {i + 1} ---")
                print(doc)
                print("Metadata:", data["metadatas"][i])
        except Exception as e:
            print(f"Error reading collection: {e}")

    elif args.delete:
        try:
            manager.client.delete_collection(name=args.delete)
            print(f"Deleted collection: {args.delete}")
        except Exception as e:
            print(f"Failed to delete collection: {e}")

    else:
        print("No action specified. Use --list, --preview <name>, or --delete <name>.")
