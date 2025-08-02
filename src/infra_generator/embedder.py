import os
import uuid
from typing import Any, Dict, List

import requests
from langchain_core.documents import Document
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter
from tqdm import tqdm

from .chroma_manager import ChromaManager
from .utils import get_language_from_extension, get_project_name, load_config


class Embedder:
    def __init__(self, config: dict, chroma_manager: ChromaManager):
        self.config = config
        self.chroma_manager = chroma_manager
        self.ollama_base_url = config["ollama_base_url"]
        self.embedding_model = config["models"]["embedding_model"]
        self.supported_languages = config["supported_languages"]

    def _get_embedding(self, text: str) -> List[float]:
        url = f"{self.ollama_base_url}/api/embeddings"
        payload = {"model": self.embedding_model, "prompt": text}
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()["embedding"]

    def _split_code_into_chunks(self, code: str, language: str) -> List[str]:
        if language == "python":
            splitter = RecursiveCharacterTextSplitter.from_language(
                language=Language.PYTHON,
                chunk_size=self.config.get("chunk_size", 2000),
                chunk_overlap=self.config.get("chunk_overlap", 200),
            )
        elif language == "javascript":
            splitter = RecursiveCharacterTextSplitter.from_language(
                language=Language.JS,
                chunk_size=self.config.get("chunk_size", 2000),
                chunk_overlap=self.config.get("chunk_overlap", 200),
            )
        elif language == "typescript":
            splitter = RecursiveCharacterTextSplitter.from_language(
                language=Language.TS,
                chunk_size=self.config.get("chunk_size", 2000),
                chunk_overlap=self.config.get("chunk_overlap", 200),
            )
        elif language == "go":
            splitter = RecursiveCharacterTextSplitter.from_language(
                language=Language.GO,
                chunk_size=self.config.get("chunk_size", 2000),
                chunk_overlap=self.config.get("chunk_overlap", 200),
            )
        else:
            # Fallback for unsupported languages or plain text
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.config.get("chunk_size", 2000),
                chunk_overlap=self.config.get("chunk_overlap", 200),
            )
        return splitter.split_text(code)

    def embed_project(self, project_path: str, project_name: str = None):
        project_name = project_name or get_project_name(project_path)
        collection = self.chroma_manager.get_collection(project_name, project_path)

        documents = []
        metadatas = []
        ids = []

        # Filter files based on supported languages and exclude patterns
        all_files = []
        for root, _, files in os.walk(project_path):
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, project_path)
                # Check against exclude patterns
                if any(
                    fnmatch.fnmatch(relative_path, pattern)
                    for pattern in self.config.get("exclude_patterns", [])
                ):
                    continue
                all_files.append(file_path)

        print(f"Source files found: {len(all_files)}")
        print(f"Source files: {all_files}")

        print(f"Embedding {len(all_files)} files in project '{project_name}'")
        for file_path in tqdm(all_files, desc=f"Embedding code for {project_name}"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    code = f.read()

                language = get_language_from_extension(
                    file_path, self.supported_languages
                )
                chunks = self._split_code_into_chunks(code, language)

                for i, chunk in enumerate(chunks):
                    documents.append(chunk)
                    metadatas.append(
                        {
                            "file_path": os.path.relpath(file_path, project_path),
                            "project": project_name,
                            "language": language,
                            "chunk_index": i,
                        }
                    )
                    ids.append(f"{project_name}-{os.path.relpath(file_path, project_path)}-{i}")

            except Exception as e:
                print(f"Error processing {file_path}: {e}")

        if documents:
            # ChromaDB can handle batching internally, but for very large projects
            # you might want to add explicit batching here.
            collection.add(documents=documents, metadatas=metadatas, ids=ids)
            print(f"Embedding complete for project '{project_name}'.")
        else:
            print(f"No documents to embed for project '{project_name}'.")
