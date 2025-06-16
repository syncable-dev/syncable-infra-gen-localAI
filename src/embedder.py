import os
from tqdm import tqdm
import requests
import uuid
import fnmatch

from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from langchain_core.documents import Document

from .utils import list_source_files, get_language_from_extension, get_project_name
from .chroma_manager import ChromaManager


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
        if fnmatch.fnmatch(os.path.basename(path), pattern) or fnmatch.fnmatch(path, pattern):
            return True
    return False


def get_line_offsets(text):
    """Return a list of character offsets for the start of each line in text."""
    offsets = [0]
    for idx, char in enumerate(text):
        if char == '\n':
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


class Embedder:
    def __init__(self, config: dict, chroma_manager: ChromaManager):
        self.config = config
        self.chroma_manager = chroma_manager

    def chunk_code(self, file_path: str, source_code: str):
        language = get_langchain_language(file_path)
        if language:
            splitter = RecursiveCharacterTextSplitter.from_language(
                language=language,
                chunk_size=500,
                chunk_overlap=50
            )
        else:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=100
            )

        docs = [Document(page_content=source_code, metadata={"file_path": file_path})]
        split_docs = splitter.split_documents(docs)
        # Add start_line and end_line to each chunk's metadata using helper
        for doc in split_docs:
            start_line, end_line = get_chunk_line_numbers(doc.page_content, source_code)
            doc.metadata['start_line'] = start_line
            doc.metadata['end_line'] = end_line
        return split_docs

    def embed_code(self, text):
        url = f"{self.config['ollama_base_url']}/api/embeddings"
        payload = {
            "model": self.config['models']['embed_model'],
            "prompt": text
        }
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()['embedding']

    def embed_project(self, project_dir, project_name=None, exclude=None):
        exclude = exclude or ['.git', '__pycache__', '*.pyc', '*.log', 'node_modules', 'venv', '.env']
        project_name = project_name or get_project_name(project_dir)
        source_files = [
            f for f in list_source_files(project_dir, self.config['extensions'].values())
            if not should_exclude(f, exclude) and not should_exclude(os.path.relpath(f, project_dir), exclude)
        ]
        print(f"Source files found: {len(source_files)}")
        print(f"Source files: {source_files}")
        print(f"Embedding {len(source_files)} files in project '{project_name}'")

        collection = self.chroma_manager.get_collection(project_name)

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
                doc.metadata.update({
                    "file_path": rel_path,
                    "language": get_language_from_extension(file_path, self.config),
                    "project": project_name,
                    "chunk_id": f"chunk_{i}",
                    # start_line and end_line are already set by chunk_code
                })

                doc_id = f"{project_name}:{rel_path}:{i}"
                collection.add(
                    documents=[doc.page_content],
                    metadatas=[doc.metadata],
                    embeddings=[embedding],
                    ids=[doc_id]
                )

        print(f"Embedding complete for project '{project_name}'.")
