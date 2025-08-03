<<<<<<< HEAD
import fnmatch
import os
=======
import os
import uuid
from typing import Any, Dict, List
>>>>>>> main

import requests
from langchain_core.documents import Document
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter
from tqdm import tqdm

from .chroma_manager import ChromaManager
<<<<<<< HEAD
from .utils import get_language_from_extension, get_project_name, list_source_files

EXT_TO_LANGUAGE = {
    ".py": Language.PYTHON,
    ".js": Language.JS,
    ".jsx": Language.JS,
    ".ts": Language.JS,
    ".tsx": Language.JS,
    ".java": Language.JAVA,
    ".go": Language.GO,
    ".cpp": Language.CPP,
    ".hpp": Language.CPP,
    ".c": Language.CPP,
    ".h": Language.CPP,
    ".md": Language.MARKDOWN,
}


def get_langchain_language(file_path):
    for ext, lang in EXT_TO_LANGUAGE.items():
        if file_path.endswith(ext):
            return lang
    return None


def should_exclude(path, exclude_patterns):
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(os.path.basename(path), pattern) or fnmatch.fnmatch(
            path, pattern
        ):
            return True
    return False


def get_line_offsets(text):
    """Return a list of character offsets for the start of each line in text."""
    offsets = [0]
    for idx, char in enumerate(text):
        if char == "\n":
            offsets.append(idx + 1)
    return offsets


def get_chunk_line_numbers(chunk_text, file_text, start_search=0):
    """Return (start_line, end_line) for chunk_text within file_text."""
    # Find the chunk in the file
    idx = file_text.find(chunk_text, start_search)
    if idx == -1:
        return -1, -1
    line_offsets = get_line_offsets(file_text)
    # Find start line
    start_line = 0
    for i, offset in enumerate(line_offsets):
        if offset > idx:
            start_line = i
            break
    else:
        start_line = len(line_offsets)
    # Find end line
    end_idx = idx + len(chunk_text)
    end_line = 0
    for i, offset in enumerate(line_offsets):
        if offset > end_idx:
            end_line = i
            break
    else:
        end_line = len(line_offsets)
    return start_line, end_line
=======
from .utils import get_language_from_extension, get_project_name, load_config
>>>>>>> main


class Embedder:
    def __init__(self, config: dict, chroma_manager: ChromaManager):
        self.config = config
        self.chroma_manager = chroma_manager
<<<<<<< HEAD

    def chunk_code(self, file_path: str, source_code: str):
        language = get_langchain_language(file_path)
        if language:
            splitter = RecursiveCharacterTextSplitter.from_language(
                language=language, chunk_size=500, chunk_overlap=50
            )
        else:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000, chunk_overlap=100
            )

        docs = [Document(page_content=source_code, metadata={"file_path": file_path})]
        split_docs = splitter.split_documents(docs)
        # Add start_line and end_line to each chunk's metadata using helper
        for doc in split_docs:
            start_line, end_line = get_chunk_line_numbers(doc.page_content, source_code)
            doc.metadata["start_line"] = start_line
            doc.metadata["end_line"] = end_line
        return split_docs

    def embed_code(self, text):
        url = f"{self.config['ollama_base_url']}/api/embeddings"
        payload = {"model": self.config["models"]["embed_model"], "prompt": text}
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()["embedding"]

    def embed_project(self, project_dir, project_name=None, exclude=None):
        # Always use exclude_patterns from config for central management
        exclude = self.config.get("exclude_patterns", [])
        project_name = project_name or get_project_name(project_dir)
        source_files = [
            f
            for f in list_source_files(project_dir, self.config["extensions"].values())
            if not should_exclude(f, exclude)
            and not should_exclude(os.path.relpath(f, project_dir), exclude)
        ]
        print(f"Source files found: {len(source_files)}")
        print(f"Source files: {source_files}")
        print(f"Embedding {len(source_files)} files in project '{project_name}'")

        collection = self.chroma_manager.get_collection(
            project_name, project_dir=project_dir
        )
        collection.modify(metadata={"project_dir": os.path.abspath(project_dir)})
        for file_path in tqdm(source_files, desc=f"Embedding code for {project_name}"):
            rel_path = os.path.relpath(file_path, project_dir)
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()

            if not code.strip():
                continue

            split_docs = self.chunk_code(rel_path, code)

            for i, doc in enumerate(split_docs):
                if len(doc.page_content.strip()) < 10:
                    continue

                embedding = self.embed_code(doc.page_content)
                doc.metadata.update(
                    {
                        "file_path": rel_path,
                        "language": get_language_from_extension(file_path, self.config),
                        "project": project_name,
                        "chunk_id": f"chunk_{i}",
                        # start_line and end_line are already set by chunk_code
                    }
                )

                doc_id = f"{project_name}:{rel_path}:{i}"
                collection.add(
                    documents=[doc.page_content],
                    metadatas=[doc.metadata],
                    embeddings=[embedding],
                    ids=[doc_id],
                )

        print(f"Embedding complete for project '{project_name}'.")
=======
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
>>>>>>> main
