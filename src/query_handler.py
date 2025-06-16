import requests

class QueryHandler:
    def __init__(self, config, retriever):
        self.config = config
        self.retriever = retriever

    def build_context(self, query, k=5, project=None):
        chunks_by_project = self.retriever.retrieve_chunks(query, k, project)
        context = ""
        for proj, chunks in chunks_by_project.items():
            for chunk in chunks:
                context += f"# Project: {proj}\n# File: {chunk['file_path']} [{chunk['start_line']}:{chunk['end_line']}]\n{chunk['code']}\n\n"
        return context

    def ask(self, query, k=5, project=None):
        context = self.build_context(query, k, project)
        prompt = (
            f"You are a codebase assistant. Here is relevant code context from the selected project(s):\n\n"
            f"{context}\n\n"
            f"Question: {query}\n"
            f"Answer:"
        )
        url = f"{self.config['ollama_base_url']}/api/generate"
        payload = {
            "model": self.config['models']['qna_model'],
            "prompt": prompt,
            "stream": False,
        }
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()['response']

